"""Baseline tests for Step 0 - Safety Net."""
import tempfile
import sqlite3
from pathlib import Path
from rag.registry import FileRegistry
from rag.scanner import FileInfo
from rag.chunkers.text_chunker import TextChunker
from rag.chunkers.code_chunker import CodeChunker


def test_db_init():
    """Test database initialization and schema."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        registry = FileRegistry(db_path)
        
        # Verify database file exists
        assert db_path.exists()
        
        # Verify all tables are created
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check documents table (Step 1 schema)
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='documents'
        """)
        assert cursor.fetchone() is not None
        
        # Check chunks table
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='chunks'
        """)
        assert cursor.fetchone() is not None
        
        # Check indexes exist (Step 1 schema)
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='index' AND name LIKE 'idx_%'
        """)
        indexes = [row[0] for row in cursor.fetchall()]
        assert 'idx_documents_path' in indexes
        assert 'idx_chunks_chunk_hash' in indexes
        
        conn.close()


def test_db_crud_operations():
    """Test basic CRUD operations on database."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        registry = FileRegistry(db_path)
        
        # Create test file
        test_file = Path(tmpdir) / "test.txt"
        test_file.write_text("test content")
        
        file_info = FileInfo(
            path=test_file,
            size=test_file.stat().st_size,
            mtime=test_file.stat().st_mtime,
            sha256="test_hash_123",
            file_type="text",
        )
        
        # CREATE: Register file
        registry.register_file(file_info)
        
        # READ: Get file
        registered = registry.get_file(test_file)
        assert registered is not None
        # Note: sha256 is stored in doc_versions, not in document directly in Step 1
        assert registered["file_type"] == "text"
        
        # UPDATE: Update file with new hash (creates new doc_version)
        updated_file_info = FileInfo(
            path=test_file,
            size=test_file.stat().st_size,
            mtime=test_file.stat().st_mtime,
            sha256="new_hash_456",
            file_type="text",
        )
        registry.register_file(updated_file_info)
        
        updated = registry.get_file(test_file)
        assert updated is not None
        assert updated["file_type"] == "text"
        
        # Register chunk using DB directly (Step 1 schema)
        from rag.db import RAGDatabase, EXTRACTOR_VERSION, CHUNKER_VERSION
        db = RAGDatabase(db_path)
        doc = db.get_document(test_file)
        assert doc is not None
        
        # Create doc_version
        doc_version_id = db.create_doc_version(
            document_id=doc["id"],
            sha256=updated_file_info.sha256,
            mtime=updated_file_info.mtime,
            extractor_version=EXTRACTOR_VERSION,
            chunker_version=CHUNKER_VERSION,
        )
        
        # Create chunk
        chunk_id = db.create_chunk(
            doc_version_id=doc_version_id,
            chunk_hash="chunk_hash_1",
            content="chunk content",
            loc_json={"line_start": 1, "line_end": 5},
        )
        assert chunk_id is not None
        
        # READ: Get chunk
        chunk_meta = registry.get_chunk_metadata(str(chunk_id))
        assert chunk_meta is not None
        assert chunk_meta["file_path"] == str(test_file)
        assert chunk_meta["start_line"] == 1
        
        # DELETE: Delete chunks for file
        registry.delete_file_chunks(test_file)
        chunk_meta_after = registry.get_chunk_metadata(str(chunk_id))
        # Note: delete_file_chunks removes chunks, so chunk should be gone
        assert chunk_meta_after is None


def test_chunker_text_returns_chunks():
    """Test that text chunker returns non-empty chunks."""
    from rag.types import Segment
    chunker = TextChunker(chunk_size=100, overlap=20)
    text = "This is a test sentence. " * 10  # ~250 chars
    segments = [Segment(text=text, loc={})]
    chunks = chunker.chunk(segments)
    
    assert len(chunks) > 0
    assert all(len(chunk.text) > 0 for chunk in chunks)
    assert all(chunk.chunk_hash for chunk in chunks)


def test_chunker_code_returns_chunks():
    """Test that code chunker returns non-empty chunks."""
    from rag.types import Segment
    chunker = CodeChunker(chunk_size=100, overlap=20)
    code = "def hello():\n    return 'world'\n" * 5
    segments = [Segment(text=code, loc={})]
    chunks = chunker.chunk(segments)
    
    assert len(chunks) > 0
    assert all(len(chunk.text) > 0 for chunk in chunks)
    assert all(chunk.chunk_hash for chunk in chunks)


def test_registry_integrity_check():
    """Test registry integrity check."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        registry = FileRegistry(db_path)
        
        # Initially should be valid (empty)
        integrity = registry.check_integrity()
        assert integrity["is_valid"] is True
        assert integrity["orphan_chunks"] == 0
        
        # Create a file and chunk
        test_file = Path(tmpdir) / "test.txt"
        test_file.write_text("test")
        
        file_info = FileInfo(
            path=test_file,
            size=test_file.stat().st_size,
            mtime=test_file.stat().st_mtime,
            sha256="hash1",
            file_type="text",
        )
        registry.register_file(file_info)
        
        # Register chunk using DB directly (Step 1 schema)
        from rag.db import RAGDatabase, EXTRACTOR_VERSION, CHUNKER_VERSION
        db = RAGDatabase(db_path)
        doc = db.get_document(test_file)
        assert doc is not None
        
        # Create doc_version
        doc_version_id = db.create_doc_version(
            document_id=doc["id"],
            sha256=file_info.sha256,
            mtime=file_info.mtime,
            extractor_version=EXTRACTOR_VERSION,
            chunker_version=CHUNKER_VERSION,
        )
        
        # Create chunk
        chunk_id = db.create_chunk(
            doc_version_id=doc_version_id,
            chunk_hash="chunk_hash_1",
            content="content",
            loc_json={"char_start": 0, "char_end": 7},
        )
        assert chunk_id is not None
        
        # Should still be valid
        integrity = registry.check_integrity()
        assert integrity["is_valid"] is True
        assert integrity["total_chunks"] == 1
        assert integrity["total_files"] == 1
