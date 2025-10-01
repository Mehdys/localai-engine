"""Text file extraction."""
from pathlib import Path
from typing import List
from rag.types import Segment


class TextExtractor:
    """Extract text from text files."""
    
    def extract(self, file_path: Path) -> List[Segment]:
        """
        Extract text from file.
        
        Returns:
            List[Segment] with one segment containing full text and empty loc
        """
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                text = f.read()
        except UnicodeDecodeError:
            # Try with error handling
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                text = f.read()
        except Exception as e:
            raise IOError(f"Failed to extract text from {file_path}: {e}")
        
        # Return one segment with full text and empty loc
        return [Segment(text=text, loc={})]


# 
