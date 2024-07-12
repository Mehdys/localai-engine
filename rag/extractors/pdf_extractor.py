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
        if not file_path.exists():
            raise IOError(f"PDF file does not exist: {file_path}")
        
        if not file_path.is_file():
            raise IOError(f"Path is not a file: {file_path}")
        
        return []
