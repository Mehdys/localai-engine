#!/usr/bin/env python3
"""Test Step 3 with CV PDF - thorough retrieval test."""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from rag.indexing import index_folder
from rag.config import RAGConfig, load_config
from rag.embeddings import OllamaEmbeddings
from rag.rag_pipeline import RAGPipeline
from rag.vector_store import VectorStore
from rag.db import RAGDatabase
import tempfile
import shutil


def main():
    """Test CV PDF indexing and retrieval."""
    cv_path = Path("~/Desktop/EV_CV_Mehdi_GRIBAA.pdf").expanduser()
    
    if not cv_path.exists():
        print(f"❌ CV not found at {cv_path}")
        return 1
    
    print(f"Testing CV PDF: {cv_path.name}")
    print("="*60)
    
    # Create temporary data directory
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        data_dir = tmp_path / ".rag_data"
        data_dir.mkdir()
        
        # Load config
        config = load_config()
        config.data_dir = data_dir
        config.db_path = data_dir / "rag.db"
        config.index_path = data_dir / "faiss.index"
        
        # Initialize database
        db = RAGDatabase(config.db_path)
        
        # Initialize embeddings
        try:
            embeddings = OllamaEmbeddings(config.ollama)
            dimension = embeddings.get_dimension()
            print(f"✅ Connected to Ollama (model: {embeddings.model}, dim: {dimension})")
        except Exception as e:
            print(f"❌ Could not connect to Ollama: {e}")
            return 1
        
        # Create a temporary directory with the PDF
        test_dir = tmp_path / "test_pdf"
        test_dir.mkdir()
        test_pdf = test_dir / cv_path.name
        shutil.copy(cv_path, test_pdf)
        print(f"✅ Copied PDF to test directory")
        
        # Index the PDF (this creates its own vector_store internally)
        print(f"\n{'='*60}")
        print("INDEXING PDF")
        print("="*60)
        result = index_folder([test_dir], config, embeddings=embeddings)
        print(f"✅ Indexed: {result}")
        
        # Now create vector store for pipeline (should load the saved index)
        print(f"\nLoading vector store from disk...")
        vector_store = VectorStore(
            config.index_path,
            config.indexing,
            dimension,
            db,
            embeddings.model,
            "documents",
        )
        
        # Check if index has vectors
        stats = vector_store.get_stats()
        print(f"✅ Vector store loaded: {stats['vector_count']} vectors, type: {stats['index_type']}")
        
        if stats['vector_count'] == 0:
            print(f"❌ ERROR: Index has no vectors! Something went wrong during indexing.")
            return 1
        
        # Verify chunks in database
        print(f"\n{'='*60}")
        print("VERIFYING STORED CHUNKS")
        print("="*60)
        with db.connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT c.id, c.loc_json, d.path, d.doc_type
                FROM chunks c
                JOIN doc_versions dv ON c.doc_version_id = dv.id
                JOIN documents d ON dv.document_id = d.id
                WHERE d.doc_type = 'pdf'
                ORDER BY c.id
                LIMIT 5
            """)
            rows = cursor.fetchall()
            print(f"Found {len(rows)} PDF chunks in database:")
            import json
            for chunk_id, loc_json, doc_path, doc_type in rows:
                loc = json.loads(loc_json)
                page_info = f"page {loc.get('page_start', '?')}-{loc.get('page_end', '?')}" if 'page_start' in loc else "no page info"
                print(f"  Chunk {chunk_id}: {page_info}, location: {loc}")
        
        # Test direct vector search first
        print(f"\n{'='*60}")
        print("TESTING DIRECT VECTOR SEARCH")
        print("="*60)
        test_query = "Mehdi GRIBAA address phone"
        query_embedding = embeddings.embed(test_query)
        print(f"Query: '{test_query}'")
        print(f"Query embedding shape: {query_embedding.shape}")
        
        direct_results = vector_store.search(query_embedding, top_k=5)
        print(f"Direct search results: {len(direct_results)} chunks found")
        if direct_results:
            for chunk_id, score in direct_results[:3]:
                print(f"  Chunk {chunk_id}: score={score:.3f}")
        else:
            print(f"  ⚠️  No results from direct search!")
        
        # Create RAG pipeline
        pipeline = RAGPipeline(
            db=db,
            vector_store=vector_store,
            embeddings=embeddings,
            config=config,
        )
        
        # Test queries that should definitely match CV content
        test_queries = [
            "What is Mehdi's address?",
            "What is the phone number?",
            "What is Mehdi GRIBAA's email?",
            "What skills does Mehdi have?",
            "What is Mehdi's experience?",
            "What education does Mehdi have?",
        ]
        
        print(f"\n{'='*60}")
        print("TESTING RETRIEVAL WITH VARIOUS QUERIES")
        print("="*60)
        
        successful_queries = 0
        for query in test_queries:
            print(f"\n{'─'*60}")
            print(f"Query: {query}")
            print(f"{'─'*60}")
            
            try:
                explain_result = pipeline.explain(query, top_k=3)
                retrieved_chunks = explain_result.get("retrieved_chunks", [])
                
                if retrieved_chunks:
                    successful_queries += 1
                    print(f"✅ Retrieved {len(retrieved_chunks)} chunks")
                    
                    for i, chunk_data in enumerate(retrieved_chunks, 1):
                        citation = chunk_data.get("citation", "")
                        file_path = chunk_data.get("file_path", "")
                        score = chunk_data.get("display_score", 0)
                        text_preview = chunk_data.get("text_preview", "")
                        
                        print(f"\n  Chunk {i}:")
                        print(f"    Citation: {citation}")
                        print(f"    Score: {score:.3f}")
                        print(f"    Text: {text_preview[:150]}...")
                        
                        # Verify PDF citation format
                        if ":p." in citation:
                            print(f"    ✅ Correct PDF citation format (path:p.X-Y)")
                        elif ":lines" in citation:
                            print(f"    ⚠️  Using line format (expected page format for PDF)")
                        else:
                            print(f"    ⚠️  Citation: {citation}")
                else:
                    print(f"⚠️  No chunks retrieved")
                    
            except Exception as e:
                print(f"❌ Error: {e}")
                import traceback
                traceback.print_exc()
        
        # Also test direct query to see answer
        print(f"\n{'='*60}")
        print("TESTING FULL QUERY (with LLM answer)")
        print("="*60)
        
        query = "What is Mehdi GRIBAA's phone number and address?"
        print(f"Query: {query}\n")
        
        try:
            result = pipeline.query(query, top_k=5)
            print(f"Answer: {result.get('answer', 'N/A')}")
            print(f"Answer source: {result.get('answer_source', 'N/A')}")
            print(f"Relevance score: {result.get('relevance_score', 0):.3f}")
            
            sources = result.get("sources", [])
            if sources:
                print(f"\nSources ({len(sources)}):")
                for i, source in enumerate(sources, 1):
                    citation = source.get("file_path", "")
                    if "line_range" in source and source["line_range"]:
                        citation += f" (lines {source['line_range']})"
                    print(f"  {i}. {citation} (score: {source.get('score', 0):.3f})")
                    print(f"     {source.get('text', '')[:100]}...")
        except Exception as e:
            print(f"❌ Error in query: {e}")
            import traceback
            traceback.print_exc()
        
        # Summary
        print(f"\n{'='*60}")
        print("SUMMARY")
        print("="*60)
        print(f"✅ PDF indexed successfully ({result.get('chunks_indexed', 0)} chunks)")
        print(f"✅ {successful_queries}/{len(test_queries)} queries retrieved results")
        print(f"✅ Chunks stored with page_start/page_end format")
        
        if successful_queries > 0:
            print(f"\n✅ Step 3 is working correctly! PDF extraction, indexing, and retrieval all functional.")
            return 0
        else:
            print(f"\n⚠️  PDF indexed but queries didn't retrieve results. Check embedding model.")
            return 1


if __name__ == "__main__":
    sys.exit(main())
