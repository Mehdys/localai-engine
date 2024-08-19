"""Step 3 tests: Real PDF Support."""
import pytest
from pathlib import Path
from rag.extractors.pdf_extractor import PDFExtractor
from rag.types import Segment


@pytest.fixture
def pdf_extractor():
    """Create a PDF extractor instance."""
    return PDFExtractor()


    def test_extract_multi_page_pdf(self, pdf_extractor, tmp_path):
        """Test extracting text from a multi-page PDF."""
        pdf_path = tmp_path / "multi_page.pdf"
        writer = PdfWriter()
        for _ in range(3):
            writer.add_blank_page(width=612, height=792)
        with open(pdf_path, "wb") as f:
            writer.write(f)
        
        segments = pdf_extractor.extract(pdf_path)
        assert isinstance(segments, list)
        for segment in segments:
            assert isinstance(segment, Segment)
            assert "page" in segment.loc


    def test_extract_empty_pdf(self, pdf_extractor, tmp_path):
        """Test extracting from an empty PDF (no pages)."""
        pdf_path = tmp_path / "empty.pdf"
        writer = PdfWriter()
        with open(pdf_path, "wb") as f:
            writer.write(f)
        
        segments = pdf_extractor.extract(pdf_path)
        assert isinstance(segments, list)
        assert len(segments) == 0
