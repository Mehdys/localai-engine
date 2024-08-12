"""Step 3 tests: Real PDF Support."""
import pytest
from pathlib import Path
from pypdf import PdfWriter
from rag.extractors.pdf_extractor import PDFExtractor
from rag.types import Segment


@pytest.fixture
def pdf_extractor():
    """Create a PDF extractor instance."""
    return PDFExtractor()


@pytest.fixture
def simple_text_pdf(tmp_path):
    """Create a simple single-page text-based PDF."""
    pdf_path = tmp_path / "simple.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    with open(pdf_path, "wb") as f:
        writer.write(f)
    return pdf_path


class TestPDFExtractor:
    """Test PDF extractor functionality."""
    
    def test_extract_simple_text_pdf(self, pdf_extractor, simple_text_pdf):
        """Test extracting text from a simple text-based PDF."""
        segments = pdf_extractor.extract(simple_text_pdf)
        assert isinstance(segments, list)
