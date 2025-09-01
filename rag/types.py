"""Core data types for RAG pipeline."""
from dataclasses import dataclass
from typing import Dict, Optional, Any


@dataclass
class Segment:
    """A segment of extracted text with location metadata.
    
    Segments are the output of extractors and input to chunkers.
    """
    text: str
    loc: Dict[str, Any]  # Location metadata: {line_start, line_end} or {page: N} or {char_start, char_end}


@dataclass
class Chunk:
    """A chunk of text with location and hash.
    
    Chunks are the output of chunkers and are stored in the database.
    """
    text: str
    loc: Dict[str, Any]  # Location metadata as JSON-serializable dict
    chunk_hash: str  # SHA256 hash of (text + canonical_json(loc))


@dataclass
class RetrievedChunk:
    """A retrieved chunk with metadata for display.
    
    Used when returning search results.
    """
    chunk_id: int  # DB chunk ID (FAISS vector_id)
    text: str
    loc: Dict[str, Any]
    path: str  # File path
    score: float  # Raw similarity score (can be -1 to 1 for cosine)
    display_score: Optional[float] = None  # Optional 0-1 normalized score for UI
    
    def __post_init__(self):
        """Compute display_score if not provided."""
        if self.display_score is None:
            # Normalize from [-1, 1] to [0, 1] for display
            self.display_score = (self.score + 1) / 2
    
    def format_citation(self) -> str:
        """Format citation string based on location type.
        
        Returns:
            code/text: path:lines a-b
            pdf: path:p.X-Y
        """
        if "page_start" in self.loc or "page" in self.loc:
            # PDF citation
            if "page_start" in self.loc and "page_end" in self.loc:
                start = self.loc["page_start"]
                end = self.loc["page_end"]
                return f"{self.path}:p.{start}-{end}"
            elif "page" in self.loc:
                page = self.loc["page"]
                return f"{self.path}:p.{page}"
            else:
                return self.path
        elif "line_start" in self.loc or "line_end" in self.loc:
            # Code/text citation
            start = self.loc.get("line_start", "?")
            end = self.loc.get("line_end", "?")
            return f"{self.path}:lines {start}-{end}"
        else:
            # Fallback
            return self.path
