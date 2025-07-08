"""Tests for registry."""
import tempfile
from pathlib import Path
from rag.registry import FileRegistry
from rag.scanner import FileInfo


def test_registry_init():
    """Test registry initialization."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        registry = FileRegistry(db_path)
        
        assert db_path.exists()
        
        stats = registry.get_stats()
        assert stats["file_count"] == 0
        assert stats["chunk_count"] == 0


def test_registry_file_operations():
    """Test file registration and change detection."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        registry = FileRegistry(db_path)
        
        # Create a test file
        test_file = Path(tmpdir) / "test.txt"
        test_file.write_text("test content")
        
        file_info = FileInfo(
            path=test_file,
            size=test_file.stat().st_size,
            mtime=test_file.stat().st_mtime,
            sha256="test_hash",
            file_type="text",
        )
        
        # Register file
        registry.register_file(file_info)
        
        # Check it's registered
        registered = registry.get_file(test_file)
        assert registered is not None
        assert registered["sha256"] == "test_hash"
        
        # Check change detection
        assert registry.is_file_changed(file_info) is False
        
        # Change file
        new_file_info = FileInfo(
            path=test_file,
            size=test_file.stat().st_size,
            mtime=test_file.stat().st_mtime,
            sha256="new_hash",
            file_type="text",
        )
        assert registry.is_file_changed(new_file_info) is True


def test_registry_chunk_operations():
    """Test chunk registration."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        registry = FileRegistry(db_path)
        
        test_file = Path(tmpdir) / "test.txt"
        
        # Register chunk
        registry.register_chunk(
            chunk_id="chunk1",
            file_path=test_file,
            chunk_hash="hash1",
            start_line=1,
            end_line=10,
        )
        
        # Check chunk exists
        assert registry.chunk_exists("hash1") is True
        assert registry.chunk_exists("hash2") is False
        
        # Get chunk metadata
        meta = registry.get_chunk_metadata("chunk1")
        assert meta is not None
        assert meta["file_path"] == str(test_file)
        assert meta["start_line"] == 1

