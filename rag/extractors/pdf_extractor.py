"""PDF extraction (stub for v2)."""
from pathlib import Path
from typing import List
from rag.types import Segment


class PDFExtractor:
    """Extract text from PDF files (v2 - not implemented)."""
    
    def extract(self, file_path: Path) -> List[Segment]:
        """
        Stub implementation - returns empty list.
        
        PDF extraction is planned for Step 3. This ensures indexing
        doesn't crash when encountering PDF files.
        """
        # Return empty list - indexing will skip this file
        return []

