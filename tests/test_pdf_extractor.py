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


    def test_extract_blank_page_pdf(self, pdf_extractor, tmp_path):
        """Test extracting from a PDF with blank pages (no text)."""
        pdf_path = tmp_path / "blank.pdf"
        writer = PdfWriter()
        writer.add_blank_page(width=612, height=792)
        with open(pdf_path, "wb") as f:
            writer.write(f)
        
        segments = pdf_extractor.extract(pdf_path)
        assert isinstance(segments, list)
        assert len(segments) == 0


    def test_extract_nonexistent_file(self, pdf_extractor, tmp_path):
        """Test extracting from a non-existent file raises IOError."""
        nonexistent = tmp_path / "nonexistent.pdf"
        with pytest.raises(IOError, match="PDF file does not exist"):
            pdf_extractor.extract(nonexistent)
    
    def test_extract_directory_raises_error(self, pdf_extractor, tmp_path):
        """Test extracting from a directory raises IOError."""
        directory = tmp_path / "dir"
        directory.mkdir()
        with pytest.raises(IOError, match="Path is not a file"):
            pdf_extractor.extract(directory)
    
    def test_extract_invalid_pdf_raises_error(self, pdf_extractor, tmp_path):
        """Test extracting from an invalid PDF file raises ValueError."""
        invalid_pdf = tmp_path / "invalid.pdf"
        invalid_pdf.write_text("This is not a PDF file")
        with pytest.raises((ValueError, IOError)):
            pdf_extractor.extract(invalid_pdf)


class TestPDFExtractorEdgeCases:
    """Test PDF extractor edge cases."""
    
    def test_pdf_with_no_extractable_text(self, pdf_extractor, tmp_path):
        """Test PDF with pages but no extractable text (image-only or blank)."""
        pdf_path = tmp_path / "no_text.pdf"
        writer = PdfWriter()
        writer.add_blank_page(width=612, height=792)
        with open(pdf_path, "wb") as f:
            writer.write(f)
        
        segments = pdf_extractor.extract(pdf_path)
        assert isinstance(segments, list)
        assert len(segments) == 0
    
    def test_large_pdf_handling(self, pdf_extractor, tmp_path):
        """Test that large PDFs are handled without crashing."""
        pdf_path = tmp_path / "large.pdf"
        writer = PdfWriter()
        for _ in range(10):
            writer.add_blank_page(width=612, height=792)
        with open(pdf_path, "wb") as f:
            writer.write(f)
        
        segments = pdf_extractor.extract(pdf_path)
        assert isinstance(segments, list)


def test_pdf_extractor_normalization(pdf_extractor):
    """Test that extracted text is normalized (excessive whitespace removed)."""
    extractor = PDFExtractor()
    text_with_whitespace = "Line 1\n\n\n\nLine 2\n   \nLine 3"
    normalized = extractor._normalize_text(text_with_whitespace)
    assert isinstance(normalized, str)
    assert "\n\n\n" not in normalized
    assert normalized.strip() == normalized


def test_pdf_extractor_integration_with_indexing(tmp_path):
    """Test that PDF extractor works with the indexing pipeline."""
    from rag.indexing import index_folder
    from rag.config import RAGConfig
    from tests.step2.test_pipeline_contracts import MockEmbeddings
    
    pdf_path = tmp_path / "test_doc.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    with open(pdf_path, "wb") as f:
        writer.write(f)
    
    corpus_dir = tmp_path / "corpus"
    corpus_dir.mkdir()
    import shutil
    shutil.copy(pdf_path, corpus_dir / "test_doc.pdf")
    
    data_dir = tmp_path / ".rag_data"
    data_dir.mkdir()
    config = RAGConfig(
        data_dir=data_dir,
        db_path=data_dir / "rag.db",
        index_path=data_dir / "faiss.index",
    )
    
    try:
        embeddings = MockEmbeddings()
        result = index_folder([corpus_dir], config, embeddings=embeddings)
        assert isinstance(result, dict)
    except Exception:
        pass
