"""CLI interface for RAG system."""
import typer
import sqlite3
import json
import hashlib
import time
from pathlib import Path
from typing import List, Optional
from rag.config import load_config, RAGConfig
from rag.scanner import FileScanner, ScanStatistics
from rag.registry import FileRegistry
from rag.db import RAGDatabase, EXTRACTOR_VERSION, CHUNKER_VERSION
from rag.extractors.text_extractor import TextExtractor
from rag.extractors.code_extractor import CodeExtractor
from rag.chunkers.text_chunker import TextChunker
from rag.chunkers.code_chunker import CodeChunker
from rag.embeddings import OllamaEmbeddings
from rag.vector_store import VectorStore
from rag.rag_pipeline import RAGPipeline


app = typer.Typer(help="Local-first RAG system using Ollama")


@app.command()
def ingest(
    roots: List[str] = typer.Argument(..., help="Root directories to scan"),
    config: Optional[Path] = typer.Option(None, "--config", "-c", help="Config file path"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Print what would be indexed"),
):
    """Scan directories and identify indexable files."""
    typer.echo("Loading configuration...")
    cfg = load_config(config)
    typer.echo(f"Configuration loaded. Ignore patterns: {len(cfg.ignore_patterns)}")
    
    scanner = FileScanner(
        text_extensions=cfg.text_extensions,
        code_extensions=cfg.code_extensions,
        ignore_patterns=cfg.ignore_patterns,
    )
    
    all_files = []
    all_stats = ScanStatistics()
    
    for root in roots:
        root_path = Path(root)
        if not root_path.exists():
            typer.echo(f"Warning: {root_path} does not exist, skipping", err=True)
            continue
        
        typer.echo(f"\n🔍 Scanning: {root_path}")
        typer.echo("   (This may take a while for large directories...)\n")
        files, stats = scanner.scan_directory(root_path, dry_run=dry_run)
        all_files.extend(files)
        
        # Accumulate statistics
        all_stats.total_files += stats.total_files
        all_stats.ignored_files += stats.ignored_files
        all_stats.unsupported_files += stats.unsupported_files
        all_stats.error_files += stats.error_files
        for file_type, count in stats.indexable_by_type.items():
            all_stats.indexable_by_type[file_type] = all_stats.indexable_by_type.get(file_type, 0) + count
        
        typer.echo(f"\n   ✓ Found {len(files):,} indexable files in {root_path}")
    
    # Display comprehensive statistics
    typer.echo(f"\n{'='*70}")
    typer.echo("📊 SCAN STATISTICS")
    typer.echo(f"{'='*70}")
    typer.echo(f"\n📁 Total files scanned: {all_stats.total_files:,}")
    typer.echo(f"\n✅ Indexable files by type:")
    for file_type in sorted(all_stats.indexable_by_type.keys()):
        count = all_stats.indexable_by_type[file_type]
        typer.echo(f"   • {file_type}: {count:,}")
    
    total_indexable = all_stats.get_total_indexable()
    typer.echo(f"\n   Total indexable: {total_indexable:,}")
    
    typer.echo(f"\n❌ Non-indexable files:")
    typer.echo(f"   • Ignored (by patterns): {all_stats.ignored_files:,}")
    typer.echo(f"   • Unsupported extension: {all_stats.unsupported_files:,}")
    typer.echo(f"   • Errors (unreadable): {all_stats.error_files:,}")
    
    total_non_indexable = (
        all_stats.ignored_files + 
        all_stats.unsupported_files + 
        all_stats.error_files
    )
    typer.echo(f"\n   Total non-indexable: {total_non_indexable:,}")
    
    typer.echo(f"\n{'─'*70}")
    typer.echo(f"Verification: {total_indexable:,} + {total_non_indexable:,} = {all_stats.total_files:,}")
    
    # Verify the sum
    if all_stats.verify_sum():
        typer.echo(f"✓ Sum verified: All files accounted for!")
    else:
        typer.echo(f"⚠ Warning: Sum mismatch detected!", err=True)
    
    typer.echo(f"{'='*70}\n")
    
    if not dry_run:
        # Update registry using new DB
        typer.echo("Updating registry...")
        db = RAGDatabase(cfg.db_path)
        registry = FileRegistry(db)
        changed_files = registry.get_changed_files(all_files)
        
        typer.echo(f"Changed files: {len(changed_files)}")
        
        typer.echo("Registering files in registry...")
        for i, file_info in enumerate(all_files, 1):
            registry.register_file(file_info)
            if i % 100 == 0:
                typer.echo(f"  Registered {i}/{len(all_files)} files...")
        
        typer.echo(f"✓ Registry updated: {cfg.db_path}")
    else:
        # Dry-run mode - just show statistics (no file list)
        typer.echo("📋 DRY-RUN MODE - No files were registered")
        typer.echo("💡 Tip: Run without --dry-run to register all files")


@app.command()
def index(
    roots: List[str] = typer.Argument(..., help="Root directories to scan"),
    config: Optional[Path] = typer.Option(None, "--config", "-c", help="Config file path"),
):
    """Index files: extract, chunk, embed, and store."""
    import sys
    
    cfg = load_config(config)
    
    # Check for lock file (Unix/Linux/macOS only)
    lock_path = cfg.data_dir / ".index.lock"
    lock_file = None
    
    if sys.platform != "win32":
        try:
            import fcntl
            if lock_path.exists():
                typer.echo("⚠ Another indexing process may be running. If not, delete:", err=True)
                typer.echo(f"   {lock_path}", err=True)
                raise typer.Exit(1)
            
            # Create lock file
            lock_file = open(lock_path, "w")
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (IOError, OSError, ImportError):
            typer.echo("⚠ Could not acquire lock. Another indexing process may be running.", err=True)
            raise typer.Exit(1)
    
    try:
        # Initialize components
        db = RAGDatabase(cfg.db_path)
        registry = FileRegistry(db)
        
        scanner = FileScanner(
            text_extensions=cfg.text_extensions,
            code_extensions=cfg.code_extensions,
            ignore_patterns=cfg.ignore_patterns,
        )
        
        # Scan for files
        all_files = []
        for root in roots:
            root_path = Path(root)
            if not root_path.exists():
                continue
            files, _ = scanner.scan_directory(root_path, dry_run=False)
            all_files.extend(files)
        
        # Filter to changed files
        changed_files = registry.get_changed_files(all_files)
        typer.echo(f"Indexing {len(changed_files)} changed files...")
        
        if not changed_files:
            typer.echo("No files to index.")
            return
        
        # Initialize extractors and chunkers
        text_extractor = TextExtractor()
        code_extractor = CodeExtractor()
        text_chunker = TextChunker(
            chunk_size=cfg.chunking.text_chunk_size,
            overlap=cfg.chunking.text_overlap,
        )
        code_chunker = CodeChunker(
            chunk_size=cfg.chunking.code_chunk_size,
            overlap=cfg.chunking.code_overlap,
        )
        
        # Initialize embeddings and vector store
        embeddings = OllamaEmbeddings(cfg.ollama)
        dimension = embeddings.get_dimension()
        typer.echo(f"Embedding dimension: {dimension}")
        
        vector_store = VectorStore(
            cfg.index_path,
            cfg.indexing,
            dimension,
            db,
            embeddings.model,
            "documents",
        )
        
        # Compute chunking config hash for manifest
        chunking_config_str = json.dumps({
            "text_chunk_size": cfg.chunking.text_chunk_size,
            "text_overlap": cfg.chunking.text_overlap,
            "code_chunk_size": cfg.chunking.code_chunk_size,
            "code_overlap": cfg.chunking.code_overlap,
        }, sort_keys=True)
        chunking_config_hash = hashlib.sha256(chunking_config_str.encode()).hexdigest()[:16]
        
        # Process files in transaction
        total_chunks = 0
        
        for i, file_info in enumerate(changed_files, 1):
            typer.echo(f"[{i}/{len(changed_files)}] Processing {file_info.path.name}...")
            
            try:
                # Create or update document
                doc_id = db.create_or_update_document(
                    path=file_info.path,
                    doc_type=file_info.file_type,
                    size_bytes=file_info.size,
                )
                
                # Create document version
                doc_version_id = db.create_doc_version(
                    document_id=doc_id,
                    sha256=file_info.sha256,
                    mtime=file_info.mtime,
                    extractor_version=EXTRACTOR_VERSION,
                    chunker_version=CHUNKER_VERSION,
                )
                
                # Get old chunk IDs before deleting (for FAISS cleanup)
                old_chunk_ids = db.get_doc_version_chunk_ids(doc_version_id)
                
                # Remove old vectors from FAISS if any exist
                if old_chunk_ids:
                    vector_store.remove_vectors(old_chunk_ids)
                
                # Delete old chunks from DB
                db.delete_doc_version_chunks(doc_version_id)
                
                # Extract segments
                segments = []
                if file_info.file_type == "text":
                    segments = text_extractor.extract(file_info.path)
                elif file_info.file_type == "code":
                    segments = code_extractor.extract(file_info.path)
                else:
                    typer.echo(f"  Skipping unsupported type: {file_info.file_type}")
                    continue
                
                if not segments:
                    continue
                
                # Chunk segments
                if file_info.file_type == "text":
                    chunks = text_chunker.chunk(segments)
                elif file_info.file_type == "code":
                    chunks = code_chunker.chunk(segments)
                else:
                    continue
                
                # Process chunks
                batch_vectors = []
                batch_chunk_ids = []
                batch_chunk_objs = []
                
                for chunk in chunks:
                    # Use location from chunk (already in correct format)
                    # Chunk.loc is already a dict with line_start/line_end or char_start/char_end
                    loc_json = chunk.loc.copy() if chunk.loc else {}
                    
                    # Compute chunk hash (consistent with DB schema)
                    # Use the chunk_hash from the chunker (already computed)
                    chunk_hash = chunk.chunk_hash
                    
                    # Check if chunk already exists
                    if db.chunk_exists(doc_version_id, chunk_hash):
                        continue
                    
                    # Create chunk in DB
                    chunk_id = db.create_chunk(
                        doc_version_id=doc_version_id,
                        chunk_hash=chunk_hash,
                        content=chunk.text,
                        loc_json=loc_json,
                    )
                    
                    if chunk_id is None:
                        # Chunk already exists, skip
                        continue
                    
                    # Add to batch
                    batch_vectors.append(chunk.text)
                    batch_chunk_ids.append(chunk_id)
                    batch_chunk_objs.append((chunk_id, chunk.text))
                    
                    # Process batch when full
                    if len(batch_vectors) >= cfg.indexing.batch_size:
                        embeddings_batch = embeddings.embed_batch(batch_vectors)
                        vector_store.add_vectors(embeddings_batch, batch_chunk_ids)
                        
                        # Store embeddings in DB
                        for chunk_id, vector in zip(batch_chunk_ids, embeddings_batch):
                            db.create_embedding(
                                chunk_id=chunk_id,
                                model=embeddings.model,
                                dim=dimension,
                                index_name="documents",
                                vector_id=chunk_id,  # Use chunk_id as vector_id
                            )
                        
                        total_chunks += len(batch_vectors)
                        batch_vectors = []
                        batch_chunk_ids = []
                        batch_chunk_objs = []
                
                # Process remaining batch
                if batch_vectors:
                    embeddings_batch = embeddings.embed_batch(batch_vectors)
                    vector_store.add_vectors(embeddings_batch, batch_chunk_ids)
                    
                    # Store embeddings in DB
                    for chunk_id, vector in zip(batch_chunk_ids, embeddings_batch):
                        db.create_embedding(
                            chunk_id=chunk_id,
                            model=embeddings.model,
                            dim=dimension,
                            index_name="documents",
                            vector_id=chunk_id,
                        )
                    
                    total_chunks += len(batch_vectors)
                
            except Exception as e:
                typer.echo(f"  Error processing {file_info.path}: {e}", err=True)
                import traceback
                traceback.print_exc()
                continue
        
        # Save vector store atomically
        vector_store.save()
        
        # Update manifest
        faiss_type = "HNSW" if cfg.indexing.use_hnsw else "Flat"
        manifest = {
            "embedding_model": embeddings.model,
            "embedding_dim": dimension,
            "chunking_config_hash": chunking_config_hash,
            "extractor_version": EXTRACTOR_VERSION,
            "chunker_version": CHUNKER_VERSION,
            "faiss_type": faiss_type,
            "faiss_params": {
                "use_hnsw": cfg.indexing.use_hnsw,
                "hnsw_m": cfg.indexing.hnsw_m if cfg.indexing.use_hnsw else None,
                "hnsw_ef_construction": cfg.indexing.hnsw_ef_construction if cfg.indexing.use_hnsw else None,
            },
            "created_at": time.time(),
            "updated_at": time.time(),
        }
        db.set_manifest("index_manifest", manifest)
        
        typer.echo(f"\n✓ Indexed {total_chunks} new chunks")
        typer.echo(f"✓ Vector store saved: {cfg.index_path}")
        typer.echo(f"✓ Database updated: {cfg.db_path}")
    finally:
        # Release lock (Unix/Linux/macOS only)
        if lock_file is not None:
            try:
                import fcntl
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
                lock_file.close()
                if lock_path.exists():
                    lock_path.unlink()
            except (IOError, OSError, ImportError):
                pass


@app.command()
def ask(
    question: str = typer.Argument(..., help="Question to ask"),
    top_k: int = typer.Option(5, "--top-k", "-k", help="Number of chunks to retrieve"),
    use_general: bool = typer.Option(None, "--use-general/--no-general", help="Allow LLM to use general knowledge (default: from config)"),
    threshold: float = typer.Option(None, "--threshold", "-t", help="Similarity threshold (0-1) for considering context relevant (default: from config)"),
    config: Optional[Path] = typer.Option(None, "--config", "-c", help="Config file path"),
):
    """Ask a question using the RAG system."""
    cfg = load_config(config)
    
    # Initialize components
    db = RAGDatabase(cfg.db_path)
    embeddings = OllamaEmbeddings(cfg.ollama)
    dimension = embeddings.get_dimension()
    vector_store = VectorStore(
        cfg.index_path,
        cfg.indexing,
        dimension,
        db,
        embeddings.model,
        "documents",
    )
    
    # Check if index exists (but allow general knowledge even without index)
    has_index = cfg.index_path.exists()
    if not has_index and use_general is False:
        typer.echo("Error: No index found. Run 'rag index' first, or use --use-general to allow general knowledge.", err=True)
        raise typer.Exit(1)
    
    # Load index if it exists
    if has_index:
        vector_store.load()
    
    # Create pipeline
    pipeline = RAGPipeline(cfg, embeddings, vector_store, db)
    
    # Query
    typer.echo(f"Question: {question}\n")
    result = pipeline.query(
        question, 
        top_k=top_k,
        use_general_knowledge=use_general,
        similarity_threshold=threshold
    )
    
    # Display answer with source indicator
    typer.echo("Answer:")
    answer_source = result.get("answer_source", "unknown")
    relevance_score = result.get("relevance_score", 0.0)
    
    if answer_source == "general_knowledge":
        typer.echo(f"📚 [Using general knowledge - relevance score: {relevance_score:.2f}]")
    elif answer_source == "indexed_low_relevance":
        typer.echo(f"⚠️  [Low relevance context - score: {relevance_score:.2f}]")
    elif answer_source == "indexed":
        typer.echo(f"📄 [Using indexed content - relevance: {relevance_score:.2f}]")
    elif answer_source == "none":
        typer.echo(f"❌ [No indexed content available]")
    
    typer.echo(result["answer"])
    
    # Display sources if available
    if result.get("sources"):
        typer.echo("\nSources:")
        for i, source in enumerate(result["sources"], 1):
            line_info = f" (lines {source['line_range']})" if source.get("line_range") else ""
            typer.echo(f"  {i}. {source['file_path']}{line_info} (score: {source['score']:.3f})")
            typer.echo(f"     {source['text']}")
    elif answer_source == "general_knowledge":
        typer.echo("\n💡 Note: Answer generated from general knowledge (no indexed sources)")


@app.command()
def chat(
    config: Optional[Path] = typer.Option(None, "--config", "-c", help="Config file path"),
    top_k: int = typer.Option(5, "--top-k", "-k", help="Number of chunks to retrieve"),
    use_general: bool = typer.Option(None, "--use-general/--no-general", help="Allow LLM to use general knowledge (default: from config)"),
    threshold: float = typer.Option(None, "--threshold", "-t", help="Similarity threshold (0-1) for considering context relevant (default: from config)"),
):
    """Start an interactive chat session."""
    import sys
    
    cfg = load_config(config)
    
    # Initialize components (once)
    typer.echo("Initializing RAG system...")
    try:
        db = RAGDatabase(cfg.db_path)
        embeddings = OllamaEmbeddings(cfg.ollama)
        dimension = embeddings.get_dimension()
        vector_store = VectorStore(
            cfg.index_path,
            cfg.indexing,
            dimension,
            db,
            embeddings.model,
            "documents",
        )
        
        # Check index
        has_index = cfg.index_path.exists()
        if not has_index and use_general is False:
            typer.echo("Error: No index found. Run 'rag index' first or allow general knowledge.", err=True)
            raise typer.Exit(1)
            
        if has_index:
            vector_store.load()
            typer.echo(f"✓ Index loaded ({vector_store.index.ntotal} vectors)")
        else:
            typer.echo("⚠ No index found. Using general knowledge only.")
            
        pipeline = RAGPipeline(cfg, embeddings, vector_store, db)
        
    except Exception as e:
        typer.echo(f"Error initializing system: {e}", err=True)
        raise typer.Exit(1)
    
    typer.echo("\n💬 RAG Chat Session")
    typer.echo("Type 'exit', 'quit', or ':q' to end session.")
    typer.echo("-" * 40)
    
    while True:
        try:
            # Get input
            question = typer.prompt("\n> ", prompt_suffix="")
            question = question.strip()
            
            if not question:
                continue
                
            if question.lower() in ("exit", "quit", ":q"):
                typer.echo("Bye! 👋")
                break
            
            # Run query
            typer.echo("Thinking...", nl=False)
            
            # Simple spinning animation or just carriage return could go here, 
            # but for now we just run it.
            # Using \r to overwrite "Thinking..." when done if terminal supports it
            sys.stdout.write("\r" + " " * 20 + "\r") 
            
            result = pipeline.query(
                question, 
                top_k=top_k,
                use_general_knowledge=use_general,
                similarity_threshold=threshold
            )
            
            # Display answer
            answer_source = result.get("answer_source", "unknown")
            relevance_score = result.get("relevance_score", 0.0)
            
            if answer_source == "general_knowledge":
                typer.echo(f"📚 [General Knowledge (score: {relevance_score:.2f})]")
            elif answer_source == "indexed_low_relevance":
                typer.echo(f"⚠️  [Low Relevance (score: {relevance_score:.2f})]")
            elif answer_source == "indexed":
                typer.echo(f"📄 [Indexed Content (score: {relevance_score:.2f})]")
            
            typer.echo(f"\n{result['answer']}\n")
            
            # Display sources nicely
            if result.get("sources"):
                typer.echo("Sources:")
                for i, source in enumerate(result["sources"], 1):
                    loc = f" (L{source['line_range']})" if source.get("line_range") else ""
                    # Truncate path to last 2 components for readability
                    path_obj = Path(source['file_path'])
                    short_path = str(Path(*path_obj.parts[-2:])) if len(path_obj.parts) > 1 else source['file_path']
                    
                    typer.echo(f"  {i}. {short_path}{loc} ({source['score']:.2f})")
            
        except (KeyboardInterrupt, EOFError):
            typer.echo("\nBye! 👋")
            break
        except Exception as e:
            typer.echo(f"\nError: {e}", err=True)



@app.command()
def stats(
    config: Optional[Path] = typer.Option(None, "--config", "-c", help="Config file path"),
):
    """Print statistics about the index."""
    cfg = load_config(config)
    
    db = RAGDatabase(cfg.db_path)
    registry = FileRegistry(db)
    reg_stats = registry.get_stats()
    
    typer.echo("Database Statistics:")
    typer.echo(f"  Indexed files: {reg_stats['file_count']}")
    typer.echo(f"  Total chunks: {reg_stats['chunk_count']}")
    if reg_stats.get("last_indexed"):
        from datetime import datetime
        last_time = datetime.fromtimestamp(reg_stats["last_indexed"])
        typer.echo(f"  Last indexed: {last_time}")
    
    # Vector store stats
    if cfg.index_path.exists():
        embeddings = OllamaEmbeddings(cfg.ollama)
        dimension = embeddings.get_dimension()
        vector_store = VectorStore(
            cfg.index_path,
            cfg.indexing,
            dimension,
            db,
            embeddings.model,
            "documents",
        )
        vector_store.load()
        vec_stats = vector_store.get_stats()
        
        typer.echo("\nVector Store Statistics:")
        typer.echo(f"  Vectors: {vec_stats['vector_count']}")
        typer.echo(f"  Dimension: {vec_stats['dimension']}")
        typer.echo(f"  Index type: {vec_stats['index_type']}")
    else:
        typer.echo("\nVector Store: Not initialized")


@app.command()
def validate(
    config: Optional[Path] = typer.Option(None, "--config", "-c", help="Config file path"),
):
    """Validate system health and integrity."""
    import requests
    
    cfg = load_config(config)
    
    typer.echo("🔍 Running system validation...\n")
    
    # 1. Check Ollama reachability
    try:
        response = requests.get(f"{cfg.ollama.base_url}/api/tags", timeout=5)
        response.raise_for_status()
        typer.echo(f"✓ Ollama reachable at {cfg.ollama.base_url}")
    except Exception as e:
        typer.echo(f"✗ Ollama not reachable at {cfg.ollama.base_url}: {e}", err=True)
        typer.echo("  Make sure Ollama is running: ollama serve", err=True)
        raise typer.Exit(1)
    
    # 2. Verify embedding model exists
    try:
        response = requests.get(f"{cfg.ollama.base_url}/api/tags", timeout=5)
        models = [model["name"] for model in response.json().get("models", [])]
        
        embedding_model_found = False
        for model in models:
            if cfg.ollama.embedding_model in model:
                embedding_model_found = True
                break
        
        if embedding_model_found:
            # Get embedding dimension
            embeddings = OllamaEmbeddings(cfg.ollama)
            dimension = embeddings.get_dimension()
            typer.echo(f"✓ Embedding model '{cfg.ollama.embedding_model}' found ({dimension} dim)")
        else:
            typer.echo(f"✗ Embedding model '{cfg.ollama.embedding_model}' not found", err=True)
            typer.echo(f"  Available models: {', '.join(models[:5])}{'...' if len(models) > 5 else ''}", err=True)
            typer.echo(f"  Pull the model: ollama pull {cfg.ollama.embedding_model}", err=True)
            raise typer.Exit(1)
    except Exception as e:
        typer.echo(f"✗ Failed to check embedding model: {e}", err=True)
        raise typer.Exit(1)
    
    # 3. Verify LLM model exists
    try:
        response = requests.get(f"{cfg.ollama.base_url}/api/tags", timeout=5)
        models = [model["name"] for model in response.json().get("models", [])]
        
        llm_model_found = False
        for model in models:
            if cfg.ollama.llm_model in model:
                llm_model_found = True
                break
        
        if llm_model_found:
            typer.echo(f"✓ LLM model '{cfg.ollama.llm_model}' found")
        else:
            typer.echo(f"✗ LLM model '{cfg.ollama.llm_model}' not found", err=True)
            typer.echo(f"  Available models: {', '.join(models[:5])}{'...' if len(models) > 5 else ''}", err=True)
            typer.echo(f"  Pull the model: ollama pull {cfg.ollama.llm_model}", err=True)
            raise typer.Exit(1)
    except Exception as e:
        typer.echo(f"✗ Failed to check LLM model: {e}", err=True)
        raise typer.Exit(1)
    
    # 4. Check index status and manifest
    db = RAGDatabase(cfg.db_path)
    
    if cfg.index_path.exists():
        try:
            embeddings = OllamaEmbeddings(cfg.ollama)
            dimension = embeddings.get_dimension()
            vector_store = VectorStore(
                cfg.index_path,
                cfg.indexing,
                dimension,
                db,
                embeddings.model,
                "documents",
            )
            vector_store.load()
            
            stats = vector_store.get_stats()
            typer.echo(f"✓ Documents index: {stats['index_type']} with {stats['vector_count']:,} vectors")
            
            # Check manifest
            manifest = db.get_manifest("index_manifest")
            if manifest:
                # Check for mismatches
                warnings = []
                
                if manifest.get("embedding_model") != embeddings.model:
                    warnings.append(
                        f"⚠ Embedding model changed: index uses '{manifest.get('embedding_model')}', "
                        f"config uses '{embeddings.model}'. Run 'rag reembed' (not implemented yet)."
                    )
                
                if manifest.get("embedding_dim") != dimension:
                    warnings.append(
                        f"⚠ Embedding dimension changed: index uses {manifest.get('embedding_dim')}, "
                        f"config uses {dimension}. Run 'rag reembed' (not implemented yet)."
                    )
                
                # Check chunking config
                chunking_config_str = json.dumps({
                    "text_chunk_size": cfg.chunking.text_chunk_size,
                    "text_overlap": cfg.chunking.text_overlap,
                    "code_chunk_size": cfg.chunking.code_chunk_size,
                    "code_overlap": cfg.chunking.code_overlap,
                }, sort_keys=True)
                chunking_config_hash = hashlib.sha256(chunking_config_str.encode()).hexdigest()[:16]
                
                if manifest.get("chunking_config_hash") != chunking_config_hash:
                    warnings.append(
                        "⚠ Chunking config changed. Run 'rag rebuild' (not implemented yet)."
                    )
                
                if warnings:
                    typer.echo("\n⚠ Manifest warnings:", err=True)
                    for warning in warnings:
                        typer.echo(f"  {warning}", err=True)
                else:
                    typer.echo("✓ Manifest: OK (no config mismatches)")
            else:
                typer.echo("⚠ No manifest found (index may be from v1)")
        except Exception as e:
            typer.echo(f"⚠ Index exists but failed to load: {e}", err=True)
    else:
        typer.echo("⚠ No index found (run 'rag index' to create one)")
    
    # 5. Check database integrity
    registry = FileRegistry(db)
    integrity = registry.check_integrity()
    
    if integrity["is_valid"]:
        typer.echo("✓ Database integrity: OK")
        typer.echo(f"  - No orphan chunks/embeddings/versions")
        typer.echo(f"  - Total files: {integrity['total_files']:,}")
        typer.echo(f"  - Total chunks: {integrity['total_chunks']:,}")
    else:
        typer.echo("✗ Database integrity issues found:", err=True)
        if integrity.get("orphan_chunks", 0) > 0:
            typer.echo(f"  - Orphan chunks: {integrity['orphan_chunks']:,}", err=True)
        if integrity.get("orphan_embeddings", 0) > 0:
            typer.echo(f"  - Orphan embeddings: {integrity['orphan_embeddings']:,}", err=True)
        if integrity.get("orphan_versions", 0) > 0:
            typer.echo(f"  - Orphan versions: {integrity['orphan_versions']:,}", err=True)
    
    # 6. Check for missing vectors (sanity check)
    if cfg.index_path.exists():
        try:
            embeddings = OllamaEmbeddings(cfg.ollama)
            dimension = embeddings.get_dimension()
            vector_store = VectorStore(
                cfg.index_path,
                cfg.indexing,
                dimension,
                db,
                embeddings.model,
                "documents",
            )
            vector_store.load()
            
            if vector_store.index is None or vector_store.index.ntotal == 0:
                typer.echo("⚠ Index is empty (no vectors)")
            else:
                # Get all chunk IDs from DB embeddings
                with db.connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        SELECT DISTINCT vector_id FROM embeddings
                        WHERE model = ? AND index_name = ?
                    """, (embeddings.model, "documents"))
                    db_vector_ids = set(row[0] for row in cursor.fetchall())
                
                # Get all vector IDs from FAISS
                faiss_vector_ids = set()
                if vector_store.index.ntotal > 0:
                    # For IndexIDMap2, we can't easily enumerate IDs, so we'll check
                    # by querying the DB for each vector_id
                    # This is a simplified check - in practice, we trust the DB
                    pass
                
                # Check if all DB vector_ids have corresponding chunks
                missing_chunks = 0
                with db.connection() as conn:
                    cursor = conn.cursor()
                    for vector_id in list(db_vector_ids)[:100]:  # Sample check
                        cursor.execute("SELECT 1 FROM chunks WHERE id = ?", (vector_id,))
                        if cursor.fetchone() is None:
                            missing_chunks += 1
                
                if missing_chunks > 0:
                    typer.echo(f"⚠ Found {missing_chunks} embeddings with missing chunks (sampled)", err=True)
                else:
                    typer.echo("✓ Vector ID integrity: OK (sampled check)")
        except Exception as e:
            typer.echo(f"⚠ Could not verify vector index integrity: {e}", err=True)
    
    typer.echo("\n✅ Validation complete!")


@app.command()
def explain(
    question: str = typer.Argument(..., help="Question to explain"),
    top_k: int = typer.Option(5, "--top-k", "-k", help="Number of chunks to retrieve"),
    config: Optional[Path] = typer.Option(None, "--config", "-c", help="Config file path"),
):
    """Explain retrieval process for debugging."""
    cfg = load_config(config)
    
    # Initialize components
    db = RAGDatabase(cfg.db_path)
    embeddings = OllamaEmbeddings(cfg.ollama)
    dimension = embeddings.get_dimension()
    vector_store = VectorStore(
        cfg.index_path,
        cfg.indexing,
        dimension,
        db,
        embeddings.model,
        "documents",
    )
    
    # Check if index exists
    if not cfg.index_path.exists():
        typer.echo("Error: No index found. Run 'rag index' first.", err=True)
        raise typer.Exit(1)
    
    # Load index
    vector_store.load()
    
    # Create pipeline
    pipeline = RAGPipeline(cfg, embeddings, vector_store, db)
    
    # Get explanation
    typer.echo(f"Question: {question}\n")
    result = pipeline.explain(question, top_k=top_k)
    
    # Display results
    typer.echo(f"Retrieved Documents (top {len(result['retrieved_chunks'])}):")
    for i, chunk in enumerate(result["retrieved_chunks"], 1):
        typer.echo(f"\n  {i}. score: {chunk['display_score']:.3f} (raw: {chunk['raw_score']:.3f}) | {chunk['citation']}")
        typer.echo(f"     \"{chunk['text_preview']}\"")
    
    typer.echo(f"\nPrompt length: {result['prompt_length']:,} characters")
    typer.echo(f"Memory hits: {result['memory_hits']} (no session)")


@app.command()
def migrate(
    config: Optional[Path] = typer.Option(None, "--config", "-c", help="Config file path"),
    yes: bool = typer.Option(False, "--yes", help="Skip confirmation prompt"),
):
    """Migrate v1 data (registry.db, metadata.db, faiss.index.mapping.json) to v2 unified DB."""
    import shutil
    from datetime import datetime
    
    cfg = load_config(config)
    
    # Check for v1 artifacts
    v1_artifacts = []
    if cfg.registry_path.exists():
        v1_artifacts.append(("registry", cfg.registry_path))
    if cfg.metadata_path.exists():
        v1_artifacts.append(("metadata", cfg.metadata_path))
    
    mapping_path = cfg.index_path.with_suffix(".mapping.json")
    if mapping_path.exists():
        v1_artifacts.append(("mapping", mapping_path))
    
    if not v1_artifacts:
        typer.echo("✓ No v1 artifacts found. Nothing to migrate.")
        return
    
    typer.echo("⚠ Legacy v1 data detected:")
    for name, path in v1_artifacts:
        typer.echo(f"  - {name}: {path}")
    
    if not yes:
        typer.echo("\nThis will:")
        typer.echo("  1. Create a backup in ~/.rag_data/v1_backup/")
        typer.echo("  2. Migrate data to the new unified DB schema")
        typer.echo("  3. Keep v1 files for safety (you can delete them later)")
        
        confirm = typer.confirm("\nProceed with migration?")
        if not confirm:
            typer.echo("Migration cancelled.")
            raise typer.Exit(0)
    
    # Create backup directory
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    backup_dir = cfg.data_dir / "v1_backup" / timestamp
    backup_dir.mkdir(parents=True, exist_ok=True)
    
    typer.echo(f"\n📦 Creating backup in {backup_dir}...")
    for name, path in v1_artifacts:
        if path.exists():
            shutil.copy2(path, backup_dir / path.name)
            typer.echo(f"  ✓ Backed up {name}")
    
    # Initialize v2 DB
    db = RAGDatabase(cfg.db_path)
    
    typer.echo("\n🔄 Migrating data...")
    
    # Try to migrate from registry.db
    if cfg.registry_path.exists():
        try:
            typer.echo("  Migrating from registry.db...")
            conn = sqlite3.connect(cfg.registry_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Migrate files
            cursor.execute("SELECT * FROM files")
            files = cursor.fetchall()
            typer.echo(f"    Found {len(files)} files")
            
            for file_row in files:
                file_dict = dict(file_row)
                doc_id = db.create_or_update_document(
                    path=Path(file_dict["path"]),
                    doc_type=file_dict.get("file_type", "unknown"),
                    size_bytes=file_dict.get("size", 0),
                )
                
                # Create doc_version if we have sha256
                if file_dict.get("sha256"):
                    db.create_doc_version(
                        document_id=doc_id,
                        sha256=file_dict["sha256"],
                        mtime=file_dict.get("mtime", 0),
                    )
            
            # Migrate chunks (if schema exists)
            try:
                cursor.execute("SELECT * FROM chunks")
                chunks = cursor.fetchall()
                typer.echo(f"    Found {len(chunks)} chunks")
                
                # Note: We can't fully migrate chunks without doc_versions,
                # so we'll skip this for now and recommend reindexing
                if chunks:
                    typer.echo("    ⚠ Chunks found but cannot be fully migrated without doc_versions.")
                    typer.echo("    ⚠ Recommendation: Run 'rag index' to reindex files.")
            except sqlite3.OperationalError:
                # Chunks table might not exist
                pass
            
            conn.close()
            typer.echo("  ✓ Registry migration complete")
        except Exception as e:
            typer.echo(f"  ✗ Error migrating registry.db: {e}", err=True)
    
    # Try to migrate mapping.json (if it exists and index exists)
    if mapping_path.exists() and cfg.index_path.exists():
        try:
            typer.echo("  Migrating from mapping.json...")
            import json as json_module
            with open(mapping_path, "r") as f:
                mapping = json_module.load(f)
            
            typer.echo(f"    Found {len(mapping)} vector mappings")
            typer.echo("    ⚠ Note: Vector mappings are now stored in DB.")
            typer.echo("    ⚠ Recommendation: Run 'rag index' to rebuild index with stable IDs.")
        except Exception as e:
            typer.echo(f"  ✗ Error reading mapping.json: {e}", err=True)
    
    typer.echo("\n✅ Migration complete!")
    typer.echo(f"   Backup saved to: {backup_dir}")
    typer.echo("\n⚠ Important next steps:")
    typer.echo("   1. Run 'rag index <paths>' to rebuild the index with stable IDs")
    typer.echo("   2. Verify with 'rag validate'")
    typer.echo("   3. Once verified, you can delete v1 files if desired")


if __name__ == "__main__":
    app()


# 

# 
