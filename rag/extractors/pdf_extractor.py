"""PDF extraction with multi-page support."""
from pathlib import Path
from typing import List
from rag.types import Segment


class PDFExtractor:
    """Extract text from PDF files with multi-page support."""
    
    def extract(self, file_path: Path) -> List[Segment]:
        """
        Extract text from PDF file.
        
        Args:
            file_path: Path to PDF file
            
        Returns:
            List[Segment] with one segment per page containing text and page number in loc
            
        Raises:
            IOError: If file cannot be read or is not a valid PDF
            ValueError: If PDF is corrupted or unreadable
        """
        try:
            from pypdf import PdfReader
        except ImportError:
            raise ImportError(
                "pypdf is required for PDF extraction. Install it with: pip install pypdf"
            )
        
        if not file_path.exists():
            raise IOError(f"PDF file does not exist: {file_path}")
        
        if not file_path.is_file():
            raise IOError(f"Path is not a file: {file_path}")
        
        try:
            with open(file_path, "rb") as f:
                reader = PdfReader(f)
                
                if len(reader.pages) == 0:
                    return []
                
                segments = []
                for page_num, page in enumerate(reader.pages, start=1):
                    text = page.extract_text()
                    if text and text.strip():
                        segments.append(
                            Segment(
                                text=text,
                                loc={"page": page_num}
                            )
                        )
                
                return segments
                
        except FileNotFoundError:
            raise IOError(f"PDF file not found: {file_path}")
        except PermissionError:
            raise IOError(f"Permission denied reading PDF file: {file_path}")
        except Exception as e:
            raise ValueError(f"Failed to extract text from PDF {file_path}: {e}")
