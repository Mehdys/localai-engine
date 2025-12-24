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
        # Compatibility layer returns None for sha256 (it's in doc_versions now)
        assert registered["sha256"] is None
        
        # Check change detection
        # Note: is_file_changed relies on doc_versions which are NOT created by register_file in the compatibility layer
        # so this will return True (changed) because no doc_version exists
        assert registry.is_file_changed(file_info) is True
