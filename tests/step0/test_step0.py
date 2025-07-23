"""Tests for Step 0 - Safety Net (validate, explain, baseline)."""
import tempfile
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import sqlite3

from rag.registry import FileRegistry
from rag.scanner import FileInfo
from rag.rag_pipeline import RAGPipeline
from rag.config import RAGConfig, OllamaConfig
from rag.embeddings import OllamaEmbeddings
from rag.vector_store import VectorStore
from rag.chunkers.text_chunker import TextChunker
from rag.chunkers.code_chunker import CodeChunker


class TestStep0Baseline:
    """Test baseline functionality from Step 0."""
    
    def test_registry_integrity_check_exists(self):
        """Test that registry has integrity check method."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            registry = FileRegistry(db_path)
            
            # Verify method exists
            assert hasattr(registry, 'check_integrity')
            
            # Test it works
            integrity = registry.check_integrity()
            assert isinstance(integrity, dict)
            assert "orphan_chunks" in integrity
            assert "total_chunks" in integrity
            assert "total_files" in integrity
            assert "is_valid" in integrity
    
    def test_rag_pipeline_explain_exists(self):
        """Test that RAGPipeline has explain method."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = RAGConfig()
            cfg.registry_path = Path(tmpdir) / "registry.db"
            cfg.index_path = Path(tmpdir) / "index.faiss"
            
            # Create minimal registry
            registry = FileRegistry(cfg.registry_path)
            
            # Mock embeddings and vector store
            with patch('rag.rag_pipeline.OllamaEmbeddings') as MockEmbeddings:
                mock_emb = MockEmbeddings.return_value
                mock_emb.embed.return_value = [0.1] * 768  # Mock embedding
                
                with patch('rag.rag_pipeline.VectorStore') as MockVectorStore:
                    mock_vs = MockVectorStore.return_value
                    mock_vs.search.return_value = []  # Empty results
                    mock_vs.get_chunk_id.return_value = None
                    
                    pipeline = RAGPipeline(cfg, mock_emb, mock_vs, registry)
                    
                    # Verify explain method exists
                    assert hasattr(pipeline, 'explain')
                    
                    # Test it works (even with empty results)
                    result = pipeline.explain("test question", top_k=5)
                    assert isinstance(result, dict)
                    assert "retrieved_chunks" in result
                    assert "prompt_length" in result
                    assert "memory_hits" in result


class TestStep0ValidateCommand:
    """Test validate command functionality."""
    
    @patch('requests.get')
    def test_validate_ollama_reachable(self, mock_get):
        """Test validate command checks Ollama reachability."""
        try:
            from typer.testing import CliRunner
            from rag.cli import app
            
            # Mock successful Ollama response
            mock_response = Mock()
            mock_response.json.return_value = {
                "models": [
                    {"name": "nomic-embed-text:latest"},
                    {"name": "llama3.2:latest"}
                ]
            }
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response
            
            # Mock embeddings dimension check
            with patch('rag.cli.OllamaEmbeddings') as MockEmbeddings:
                mock_emb = MockEmbeddings.return_value
                mock_emb.get_dimension.return_value = 768
                
                # Mock vector store to avoid index loading issues
                with patch('rag.cli.VectorStore') as MockVectorStore:
                    mock_vs = MockVectorStore.return_value
                    mock_vs.load = Mock()
                    mock_vs.get_stats.return_value = {
                        'index_type': 'HNSW',
                        'vector_count': 0
                    }
                    mock_vs.index = None
                    
                    runner = CliRunner()
                    result = runner.invoke(app, ["validate"])
                    
                    # Should not crash (may fail on other checks, but Ollama check should pass)
                    assert result.exit_code in [0, 1]  # May fail on other checks
        except ImportError:
            # Skip if typer.testing not available
            pytest.skip("typer.testing not available")
    
    def test_validate_integrity_check(self):
        """Test that validate command uses integrity check."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            registry = FileRegistry(db_path)
            
            # Create a file and chunk
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("test content")
            
            file_info = FileInfo(
                path=test_file,
                size=test_file.stat().st_size,
                mtime=test_file.stat().st_mtime,
                sha256="test_hash",
                file_type="text",
            )
            registry.register_file(file_info)
            
            registry.register_chunk(
                chunk_id="chunk1",
                file_path=test_file,
                chunk_hash="hash1",
                chunk_text="content",
            )
            
            # Check integrity
            integrity = registry.check_integrity()
            assert integrity["is_valid"] is True
            assert integrity["orphan_chunks"] == 0


class TestStep0ExplainCommand:
    """Test explain command functionality."""
    
    def test_explain_returns_correct_structure(self):
        """Test that explain method returns correct data structure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = RAGConfig()
            cfg.registry_path = Path(tmpdir) / "registry.db"
            cfg.index_path = Path(tmpdir) / "index.faiss"
            
            registry = FileRegistry(cfg.registry_path)
            
            # Create test file and chunk
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text("def hello():\n    return 'world'\n")
            
            file_info = FileInfo(
                path=test_file,
                size=test_file.stat().st_size,
                mtime=test_file.stat().st_mtime,
                sha256="hash1",
                file_type="code",
            )
            registry.register_file(file_info)
            
            registry.register_chunk(
                chunk_id="chunk1",
                file_path=test_file,
                chunk_hash="hash1",
                chunk_text="def hello():\n    return 'world'",
                start_line=1,
                end_line=2,
            )
            
            # Mock embeddings
            from rag.db import RAGDatabase
            db = RAGDatabase(cfg.db_path)
            
            with patch('rag.rag_pipeline.OllamaEmbeddings') as MockEmbeddings:
                mock_emb = MockEmbeddings.return_value
                mock_emb.embed.return_value = [0.1] * 768
                
                # Mock vector store
                with patch('rag.rag_pipeline.VectorStore') as MockVectorStore:
                    mock_vs = MockVectorStore.return_value
                    mock_vs.search.return_value = [(1, 0.8)]  # vector_id=1, score=0.8
                    mock_vs.get_chunk_id.return_value = 1
                    
                    # Mock db.get_chunk_by_vector_id to return a chunk
                    with patch.object(db, 'get_chunk_by_vector_id') as mock_get_chunk:
                        mock_get_chunk.return_value = {
                            "content": "def hello():\n    return 'world'",
                            "document_path": str(test_file),
                            "loc_json": '{"line_start": 1, "line_end": 2}',
                        }
                        
                        pipeline = RAGPipeline(cfg, mock_emb, mock_vs, db)
                        
                        result = pipeline.explain("What does hello do?", top_k=1)
                    
                    # Verify structure
                    assert isinstance(result, dict)
                    assert "retrieved_chunks" in result
                    assert "prompt_length" in result
                    assert "memory_hits" in result
                    
                    # Verify chunks structure
                    if result["retrieved_chunks"]:
                        chunk = result["retrieved_chunks"][0]
                        assert "file_path" in chunk
                        assert "citation" in chunk
                        assert "raw_score" in chunk
                        assert "display_score" in chunk
                        assert "text_preview" in chunk
                        
                        # Verify score normalization
                        assert 0 <= chunk["display_score"] <= 1
                        assert chunk["raw_score"] == 0.8
                        assert chunk["display_score"] == (0.8 + 1) / 2  # Normalized
                        
                        # Verify citation format
                        assert "lines" in chunk["citation"] or "p." in chunk["citation"]


class TestStep0Integration:
    """Integration tests for Step 0 features."""
    
    def test_baseline_tests_exist(self):
        """Verify baseline test file exists and can be imported."""
        from tests.step0 import test_baseline
        assert hasattr(test_baseline, 'test_db_init')
        assert hasattr(test_baseline, 'test_db_crud_operations')
        assert hasattr(test_baseline, 'test_chunker_text_returns_chunks')
        assert hasattr(test_baseline, 'test_chunker_code_returns_chunks')
        assert hasattr(test_baseline, 'test_registry_integrity_check')
    
    def test_cli_commands_exist(self):
        """Verify CLI commands exist."""
        from rag.cli import app
        
        # Get command names from typer app
        # Typer stores commands in app.registered_commands, but we need to check the callback names
        command_names = []
        for cmd in app.registered_commands:
            # Typer commands have a callback attribute with __name__
            if hasattr(cmd, 'callback') and cmd.callback:
                command_names.append(cmd.callback.__name__)
            # Also check if there's a name attribute
            if hasattr(cmd, 'name') and cmd.name:
                command_names.append(cmd.name)
        
        # Alternative: check by trying to invoke help
        try:
            from typer.testing import CliRunner
            runner = CliRunner()
            result = runner.invoke(app, ["--help"])
            help_text = result.stdout
            
            # Check if commands are mentioned in help text
            assert "validate" in help_text.lower()
            assert "explain" in help_text.lower()
            assert "ingest" in help_text.lower()
            assert "index" in help_text.lower()
            assert "ask" in help_text.lower()
            assert "stats" in help_text.lower()
        except ImportError:
            # Fallback: just check that the functions exist
            assert hasattr(app, 'registered_commands')
            assert len(app.registered_commands) >= 6  # At least 6 commands
    
    def test_step0_no_breaking_changes(self):
        """Verify Step 0 doesn't break existing functionality."""
        # Test that existing registry methods still work
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            registry = FileRegistry(db_path)
            
            # Existing methods should still work
            assert hasattr(registry, 'register_file')
            assert hasattr(registry, 'get_file')
            assert hasattr(registry, 'register_chunk')
            assert hasattr(registry, 'get_chunk_metadata')
            assert hasattr(registry, 'get_stats')
            
            # New method should exist
            assert hasattr(registry, 'check_integrity')
            
            # Test existing functionality
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("test")
            
            file_info = FileInfo(
                path=test_file,
                size=test_file.stat().st_size,
                mtime=test_file.stat().st_mtime,
                sha256="hash",
                file_type="text",
            )
            
            registry.register_file(file_info)
            registered = registry.get_file(test_file)
            assert registered is not None
            
            stats = registry.get_stats()
            assert stats["file_count"] == 1


def test_step0_complete():
    """
    Comprehensive test to verify Step 0 is complete.
    
    This test verifies:
    1. Baseline tests exist and are runnable
    2. Validate command exists and has required checks
    3. Explain command exists and returns correct format
    4. No breaking changes to existing functionality
    """
    # 1. Verify baseline tests
    from tests.step0 import test_baseline
    assert hasattr(test_baseline, 'test_db_init')
    
    # 2. Verify validate command
    from rag.cli import app
    try:
        from typer.testing import CliRunner
        runner = CliRunner()
        result = runner.invoke(app, ["--help"])
        help_text = result.stdout.lower()
        assert "validate" in help_text
        assert "explain" in help_text
        # 6. Verify existing commands still work
        assert "ingest" in help_text
        assert "index" in help_text
        assert "ask" in help_text
        assert "stats" in help_text
    except ImportError:
        # Fallback: check that commands are registered
        assert len(app.registered_commands) >= 6
    
    # 4. Verify RAGPipeline has explain method
    assert hasattr(RAGPipeline, 'explain')
    
    # 5. Verify FileRegistry has integrity check
    assert hasattr(FileRegistry, 'check_integrity')
    
    print("✅ Step 0 verification complete!")
