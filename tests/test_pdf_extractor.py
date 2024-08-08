"""Step 3 tests: Real PDF Support."""
import pytest
from pathlib import Path
from rag.extractors.pdf_extractor import PDFExtractor
from rag.types import Segment


@pytest.fixture
def pdf_extractor():
    """Create a PDF extractor instance."""
    return PDFExtractor()
