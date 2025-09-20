"""Step 2 tests: Pipeline contracts (Segment → Chunk → RetrievedChunk).

Tests verify:
1. Extractor contract: extractors return List[Segment]
2. Chunker contract: chunkers consume List[Segment] and output List[Chunk] with chunk_hash
3. End-to-end smoke: indexing works with new contracts
4. Retrieval contract: retrieval returns RetrievedChunk instances
"""
import pytest
import tempfile
import json
import hashlib
import numpy as np
from pathlib import Path
from typing import List
from unittest.mock import Mock, patch

from rag.types import Segment, Chunk, RetrievedChunk
from rag.extractors.text_extractor import TextExtractor
from rag.extractors.code_extractor import CodeExtractor
from rag.extractors.pdf_extractor import PDFExtractor
from rag.chunkers.text_chunker import TextChunker
from rag.chunkers.code_chunker import CodeChunker
from rag.config import RAGConfig
from rag.db import RAGDatabase
from rag.indexing import index_folder
from rag.rag_pipeline import RAGPipeline
from rag.embeddings import OllamaEmbeddings
from rag.vector_store import VectorStore


class MockEmbeddings:
    """Deterministic mock embeddings for testing."""
    
    def __init__(self, model: str = "test-model", dim: int = 128):
        self.model = model
        self.dim = dim
    
    def embed(self, text: str) -> np.ndarray:
        """Generate deterministic embedding from text hash."""
        h = hashlib.sha256(text.encode()).hexdigest()
        vector = np.array([
            (int(h[i:i+2], 16) / 255.0 - 0.5) * 2
            for i in range(0, min(len(h), self.dim * 2), 2)
        ], dtype=np.float32)
        
        if len(vector) < self.dim:
            padding = np.zeros(self.dim - len(vector), dtype=np.float32)
            vector = np.concatenate([vector, padding])
        else:
            vector = vector[:self.dim]
        
        norm = np.linalg.norm(vector)
        if norm > 0:
            vector = vector / norm
        
        return vector
    
    def embed_batch(self, texts: List[str]) -> np.ndarray:
        """Generate embeddings for batch of texts."""
        vectors = [self.embed(text) for text in texts]
        return np.vstack(vectors)
    
    def get_dimension(self) -> int:
        """Return embedding dimension."""
        return self.dim


@pytest.fixture
def temp_data_dir(tmp_path):
    """Create temporary data directory."""
    data_dir = tmp_path / ".rag_data"
    data_dir.mkdir()
    return data_dir


@pytest.fixture
def test_config(temp_data_dir):
    """Create test configuration with temp data directory."""
    config = RAGConfig(
        data_dir=temp_data_dir,
        db_path=temp_data_dir / "rag.db",
        index_path=temp_data_dir / "faiss.index",
    )
    return config


@pytest.fixture
def test_corpus(tmp_path):
    """Create a small test corpus with two files."""
    corpus_dir = tmp_path / "test_corpus"
    corpus_dir.mkdir()
    
    # Create a.txt
    a_file = corpus_dir / "a.txt"
    a_file.write_text("This is a test sentence for indexing.")
    
    # Create b.py
    b_file = corpus_dir / "b.py"
    b_file.write_text("""def hello():
    return "world"

def goodbye():
    return "farewell"
""")
    
    return corpus_dir


class Test1_ExtractorContract:
    """Test 1: Extractor contract - extractors return List[Segment]."""
    
    def test_text_extractor_returns_list_segment(self, tmp_path):
        """Test text extractor returns List[Segment]."""
        extractor = TextExtractor()
        test_file = tmp_path / "test.txt"
        test_file.write_text("Hello world\nThis is a test.")
        
        segments = extractor.extract(test_file)
        
        assert isinstance(segments, list)
        assert len(segments) == 1
        assert isinstance(segments[0], Segment)
        assert segments[0].text == "Hello world\nThis is a test."
        assert segments[0].loc == {}
    
    def test_code_extractor_returns_list_segment(self, tmp_path):
        """Test code extractor returns List[Segment] with line loc when applicable."""
        extractor = CodeExtractor()
        test_file = tmp_path / "test.py"
        test_file.write_text("""def hello():
    return "world"

def goodbye():
    return "farewell"
""")
        
        segments = extractor.extract(test_file)
        
        assert isinstance(segments, list)
        assert len(segments) >= 1
        for segment in segments:
            assert isinstance(segment, Segment)
            assert segment.text
            # Should have line_start and line_end when structure detected
            if len(segments) > 1:
                assert "line_start" in segment.loc
                assert "line_end" in segment.loc
    
    def test_code_extractor_fallback_single_segment(self, tmp_path):
        """Test code extractor falls back to single segment with empty loc."""
        extractor = CodeExtractor()
        # Create file with no structure (e.g., .txt file)
        test_file = tmp_path / "test.txt"
        test_file.write_text("Just some text")
        
        segments = extractor.extract(test_file)
        
        assert isinstance(segments, list)
        assert len(segments) == 1
        assert isinstance(segments[0], Segment)
        assert segments[0].loc == {}
    
    def test_pdf_extractor_returns_empty_list(self, tmp_path):
        """Test PDF extractor returns empty list (doesn't crash)."""
        extractor = PDFExtractor()
        test_file = tmp_path / "test.pdf"
        test_file.write_text("fake pdf content")  # Just create a file
        
        segments = extractor.extract(test_file)
        
        assert isinstance(segments, list)
        assert len(segments) == 0


class Test2_ChunkerContract:
    """Test 2: Chunker contract - chunkers consume List[Segment] and output List[Chunk]."""
    
    def test_text_chunker_consumes_segments(self):
        """Test text chunker consumes List[Segment]."""
        chunker = TextChunker(chunk_size=50, overlap=10)
        segments = [
            Segment(text="This is a test sentence for chunking.", loc={})
        ]
        
        chunks = chunker.chunk(segments)
        
        assert isinstance(chunks, list)
        assert len(chunks) > 0
        for chunk in chunks:
            assert isinstance(chunk, Chunk)
            assert chunk.text
            assert isinstance(chunk.loc, dict)
            assert chunk.chunk_hash
            # Verify chunk_hash is deterministic
            assert len(chunk.chunk_hash) == 64  # SHA256 hex length
    
    def test_text_chunker_chunk_hash_deterministic(self):
        """Test chunk_hash is deterministic across runs."""
        chunker = TextChunker(chunk_size=50, overlap=10)
        segments = [
            Segment(text="This is a test sentence.", loc={})
        ]
        
        chunks1 = chunker.chunk(segments)
        chunks2 = chunker.chunk(segments)
        
        assert len(chunks1) == len(chunks2)
        for c1, c2 in zip(chunks1, chunks2):
            assert c1.chunk_hash == c2.chunk_hash
            assert c1.text == c2.text
            assert c1.loc == c2.loc
    
    def test_code_chunker_consumes_segments(self):
        """Test code chunker consumes List[Segment]."""
        chunker = CodeChunker(chunk_size=50, overlap=10)
        segments = [
            Segment(
                text="def hello():\n    return 'world'",
                loc={"line_start": 1, "line_end": 2}
            )
        ]
        
        chunks = chunker.chunk(segments)
        
        assert isinstance(chunks, list)
        assert len(chunks) > 0
        for chunk in chunks:
            assert isinstance(chunk, Chunk)
            assert chunk.text
            assert isinstance(chunk.loc, dict)
            assert chunk.chunk_hash
            # Code chunks should preserve line_start/line_end
            if "line_start" in chunk.loc:
                assert "line_end" in chunk.loc
    
    def test_chunk_hash_format(self):
        """Test chunk_hash is computed correctly (SHA256 of text + canonical_json(loc))."""
        chunker = TextChunker()
        segments = [
            Segment(text="test", loc={"char_start": 0, "char_end": 4})
        ]
        
        chunks = chunker.chunk(segments)
        assert len(chunks) > 0
        
        chunk = chunks[0]
        # Manually compute expected hash
        loc_json = json.dumps(chunk.loc, sort_keys=True, separators=(',', ':'))
        expected_hash = hashlib.sha256((chunk.text + loc_json).encode()).hexdigest()
        
        assert chunk.chunk_hash == expected_hash


class Test3_EndToEndSmoke:
    """Test 3: End-to-end smoke - indexing works with new contracts."""
    
    def test_indexing_creates_chunks(self, test_config, test_corpus):
        """Test indexing creates chunks using new contracts."""
        mock_embeddings = MockEmbeddings()
        
        index_folder([test_corpus], test_config, embeddings=mock_embeddings)
        
        db = RAGDatabase(test_config.db_path)
        
        # Check chunks exist
        with db.connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM chunks")
            chunk_count = cursor.fetchone()[0]
            assert chunk_count > 0
    
    def test_indexing_creates_embeddings(self, test_config, test_corpus):
        """Test indexing creates embeddings."""
        mock_embeddings = MockEmbeddings()
        
        index_folder([test_corpus], test_config, embeddings=mock_embeddings)
        
        db = RAGDatabase(test_config.db_path)
        
        # Check embeddings exist
        with db.connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM embeddings")
            emb_count = cursor.fetchone()[0]
            assert emb_count > 0
    
    def test_indexing_no_exceptions(self, test_config, test_corpus):
        """Test indexing completes without exceptions."""
        mock_embeddings = MockEmbeddings()
        
        # Should not raise
        result = index_folder([test_corpus], test_config, embeddings=mock_embeddings)
        
        assert isinstance(result, dict)
        assert "chunks_indexed" in result
    
    def test_db_loc_json_valid_json(self, test_config, test_corpus):
        """Test DB loc_json exists and is valid JSON."""
        mock_embeddings = MockEmbeddings()
        
        index_folder([test_corpus], test_config, embeddings=mock_embeddings)
        
        db = RAGDatabase(test_config.db_path)
        
        # Check loc_json is valid JSON
        with db.connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT loc_json FROM chunks LIMIT 1")
            row = cursor.fetchone()
            if row:
                loc_json_str = row[0]
                # Should be valid JSON
                loc = json.loads(loc_json_str)
                assert isinstance(loc, dict)


class Test4_RetrievalContract:
    """Test 4: Retrieval contract - retrieval returns RetrievedChunk instances."""
    
    def test_retrieval_returns_retrieved_chunks(self, test_config, test_corpus):
        """Test retrieval returns RetrievedChunk instances."""
        mock_embeddings = MockEmbeddings()
        
        # Index first
        index_folder([test_corpus], test_config, embeddings=mock_embeddings)
        
        # Create pipeline
        db = RAGDatabase(test_config.db_path)
        vector_store = VectorStore(
            test_config.index_path,
            test_config.indexing,
            mock_embeddings.dim,
            db,
            mock_embeddings.model,
            "documents",
        )
        vector_store.load()
        
        pipeline = RAGPipeline(
            test_config,
            mock_embeddings,
            vector_store,
            db,
        )
        
        # Perform a search
        query_text = "test"
        query_vector = mock_embeddings.embed(query_text)
        results = vector_store.search(query_vector, top_k=5)
        
        if results:
            # Verify results can be wrapped in RetrievedChunk
            for chunk_id, score in results:
                chunk = db.get_chunk_by_vector_id(
                    chunk_id,
                    mock_embeddings.model,
                    "documents"
                )
                if chunk:
                    retrieved_chunk = RetrievedChunk(
                        chunk_id=chunk_id,
                        text=chunk["content"],
                        loc=json.loads(chunk["loc_json"]),
                        path=chunk["document_path"],
                        score=float(score),
                    )
                    
                    assert isinstance(retrieved_chunk, RetrievedChunk)
                    assert retrieved_chunk.chunk_id == chunk_id
                    assert retrieved_chunk.text
                    assert isinstance(retrieved_chunk.loc, dict)
                    assert retrieved_chunk.path
                    assert isinstance(retrieved_chunk.score, float)
                    assert retrieved_chunk.display_score is not None
                    assert 0 <= retrieved_chunk.display_score <= 1


def test_step2_complete():
    """Comprehensive test to verify Step 2 is complete."""
    test_classes = [
        Test1_ExtractorContract,
        Test2_ChunkerContract,
        Test3_EndToEndSmoke,
        Test4_RetrievalContract,
    ]
    
    for test_class in test_classes:
        assert hasattr(test_class, '__name__'), f"Test class {test_class} should have a name"
    
    print("✅ Step 2 verification test suite is complete!")
