"""PDF extraction with multi-page support."""
from pathlib import Path
from typing import List
import re
from rag.types import Segment


class PDFExtractor:
    """Extract text from PDF files with multi-page support."""
    
    def extract(self, file_path: Path) -> List[Segment]:
        """
        Extract text from PDF file.
        
        Args:
            file_path: Path to PDF file
            
        Returns:
            List[Segment] with one segment per page containing text and page range in loc (page_start, page_end)
            
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
                    try:
                        text = page.extract_text()
                        if not text or not text.strip():
                            continue
                        text = self._normalize_text(text)
                        segments.append(
                            Segment(
                                text=text,
                                loc={"page_start": page_num, "page_end": page_num}  # Range format
                            )
                        )
                    except Exception:
                        continue
                
                if not segments:
                    return []
                
                return segments
                
        except FileNotFoundError:
            raise IOError(f"PDF file not found: {file_path}")
        except PermissionError:
            raise IOError(f"Permission denied reading PDF file: {file_path}")
        except Exception as e:
            raise ValueError(f"Failed to extract text from PDF {file_path}: {e}")
    
    def _normalize_text(self, text: str) -> str:
        """
        Normalize extracted PDF text.
        
        Removes excessive whitespace while preserving paragraph structure.
        Handles Unicode text properly.
        
        Args:
            text: Raw extracted text
            
        Returns:
            Normalized text string
        """
        if not text:
            return ""
        
        lines = text.split("\n")
        normalized_lines = []
        
        for line in lines:
            line = line.strip()
            if line:
                normalized_lines.append(line)
            else:
                if normalized_lines and normalized_lines[-1]:
                    normalized_lines.append("")
        
        result = "\n".join(normalized_lines)
        result = re.sub(r"\n{3,}", "\n\n", result)
        return result.strip()
