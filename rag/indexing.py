"""Internal indexing functions for programmatic use (CLI and tests)."""
import json
import hashlib
import time
from pathlib import Path
from typing import List, Optional, Dict
from rag.config import RAGConfig
from rag.scanner import FileScanner, FileInfo
from rag.db import RAGDatabase, EXTRACTOR_VERSION, CHUNKER_VERSION
from rag.registry import FileRegistry
from rag.extractors.text_extractor import TextExtractor
from rag.extractors.code_extractor import CodeExtractor
from rag.chunkers.text_chunker import TextChunker
from rag.chunkers.code_chunker import CodeChunker
from rag.embeddings import OllamaEmbeddings
from rag.vector_store import VectorStore


def index_folder(
    roots: List[Path],
    config: RAGConfig,
    embeddings: Optional[OllamaEmbeddings] = None,
) -> Dict[str, int]:
    """
    Index files in given folders.
    
    Args:
        roots: List of root directories to index
        config: RAG configuration
        embeddings: Optional embeddings instance (for dependency injection in tests)
    
    Returns:
        Dict with indexing statistics
    """
    # Initialize components
    db = RAGDatabase(config.db_path)
    registry = FileRegistry(db)
    
    scanner = FileScanner(
        text_extensions=config.text_extensions,
        code_extensions=config.code_extensions,
        ignore_patterns=config.ignore_patterns,
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
    
    if not changed_files:
        return {
            "total_files": len(all_files),
            "changed_files": 0,
            "chunks_indexed": 0,
        }
    
    # Initialize extractors and chunkers
    text_extractor = TextExtractor()
    code_extractor = CodeExtractor()
    text_chunker = TextChunker(
        chunk_size=config.chunking.text_chunk_size,
        overlap=config.chunking.text_overlap,
    )
    code_chunker = CodeChunker(
        chunk_size=config.chunking.code_chunk_size,
        overlap=config.chunking.code_overlap,
    )
    
    # Initialize embeddings (use provided or create new)
    if embeddings is None:
        embeddings = OllamaEmbeddings(config.ollama)
    dimension = embeddings.get_dimension()
    
    vector_store = VectorStore(
        config.index_path,
        config.indexing,
        dimension,
        db,
        embeddings.model,
        "documents",
    )
    
    # Load existing index if it exists
    vector_store.load()
    
    # Compute chunking config hash for manifest
    chunking_config_str = json.dumps({
        "text_chunk_size": config.chunking.text_chunk_size,
        "text_overlap": config.chunking.text_overlap,
        "code_chunk_size": config.chunking.code_chunk_size,
        "code_overlap": config.chunking.code_overlap,
    }, sort_keys=True)
    chunking_config_hash = hashlib.sha256(chunking_config_str.encode()).hexdigest()[:16]
    
    # Process files
    total_chunks = 0
    
    for file_info in changed_files:
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
            
            # Delete old chunks for this version
            db.delete_doc_version_chunks(doc_version_id)
            
            # Extract segments
            segments = []
            if file_info.file_type == "text":
                segments = text_extractor.extract(file_info.path)
            elif file_info.file_type == "code":
                segments = code_extractor.extract(file_info.path)
            else:
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
            
            for chunk in chunks:
                # Use chunk.loc and chunk.chunk_hash directly
                loc_json = chunk.loc
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
                    continue
                
                # Add to batch
                batch_vectors.append(chunk.text)
                batch_chunk_ids.append(chunk_id)
                
                # Process batch when full
                if len(batch_vectors) >= config.indexing.batch_size:
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
                    batch_vectors = []
                    batch_chunk_ids = []
            
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
            continue
    
    # Save vector store atomically
    vector_store.save()
    
    # Update manifest
    faiss_type = "HNSW" if config.indexing.use_hnsw else "Flat"
    manifest = {
        "embedding_model": embeddings.model,
        "embedding_dim": dimension,
        "chunking_config_hash": chunking_config_hash,
        "extractor_version": EXTRACTOR_VERSION,
        "chunker_version": CHUNKER_VERSION,
        "faiss_type": faiss_type,
        "faiss_params": {
            "use_hnsw": config.indexing.use_hnsw,
            "hnsw_m": config.indexing.hnsw_m if config.indexing.use_hnsw else None,
            "hnsw_ef_construction": config.indexing.hnsw_ef_construction if config.indexing.use_hnsw else None,
        },
        "created_at": time.time(),
        "updated_at": time.time(),
    }
    db.set_manifest("index_manifest", manifest)
    
    return {
        "total_files": len(all_files),
        "changed_files": len(changed_files),
        "chunks_indexed": total_chunks,
    }

# 
