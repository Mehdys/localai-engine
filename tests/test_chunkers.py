"""Tests for chunkers."""
import pytest
from rag.chunkers.text_chunker import TextChunker
from rag.chunkers.code_chunker import CodeChunker
from rag.types import Segment


def test_text_chunker_basic():
    """Test basic text chunking."""
    chunker = TextChunker(chunk_size=100, overlap=20)
    text = "This is a test. " * 20  # ~300 chars
    segment = Segment(text=text, loc={})
    chunks = chunker.chunk([segment])
    
    assert len(chunks) > 1
    assert all(len(chunk.text) <= 100 for chunk in chunks)
    # Check new loc format
    assert chunks[0].loc["char_start"] == 0


def test_text_chunker_small_text():
    """Test chunking small text (single chunk)."""
    chunker = TextChunker(chunk_size=1000, overlap=100)
    text = "Short text"
    segment = Segment(text=text, loc={})
    chunks = chunker.chunk([segment])
    
    assert len(chunks) == 1
    assert chunks[0].text == text


def test_code_chunker_fallback():
    """Test code chunker falls back to text chunking."""
    chunker = CodeChunker(chunk_size=100, overlap=20)
    code = "def test():\n    pass\n" * 10
    segment = Segment(text=code, loc={})
    chunks = chunker.chunk([segment])
    
    assert len(chunks) > 0
    assert all(len(chunk.text) <= 150 for chunk in chunks)  # Allow some overflow

