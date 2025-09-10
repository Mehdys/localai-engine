"""Text chunking with overlap."""
from typing import List
import json
import hashlib
from rag.types import Segment, Chunk


class TextChunker:
    """Chunk text with configurable size and overlap."""
    
    def __init__(self, chunk_size: int = 900, overlap: int = 150):
        self.chunk_size = chunk_size
        self.overlap = overlap
    
    def chunk(self, segments: List[Segment]) -> List[Chunk]:
        """
        Chunk segments into overlapping chunks.
        
        Args:
            segments: List of Segment objects to chunk
        
        Returns:
            List of Chunk objects with chunk_hash
        """
        all_chunks = []
        
        for segment in segments:
            text = segment.text
            base_loc = segment.loc.copy() if segment.loc else {}
            
            if len(text) <= self.chunk_size:
                # Single chunk for small texts
                # Use char_start/char_end for fallback loc
                loc = {
                    "char_start": 0,
                    "char_end": len(text),
                }
                # Preserve any existing loc keys
                loc.update(base_loc)
                
                chunk_hash = self._compute_chunk_hash(text, loc)
                all_chunks.append(Chunk(
                    text=text,
                    loc=loc,
                    chunk_hash=chunk_hash,
                ))
                continue
            
            # Pre-compute line offsets for line number tracking
            line_offsets = self._compute_line_offsets(text)
            offset = 0
            
            while offset < len(text):
                # Determine chunk boundaries
                chunk_end = min(offset + self.chunk_size, len(text))
                
                # Try to break at sentence or paragraph boundary
                if chunk_end < len(text):
                    # Look for sentence endings
                    for i in range(chunk_end, max(offset + self.chunk_size - 200, offset), -1):
                        if text[i] in ".!?\n":
                            chunk_end = i + 1
                            break
                
                chunk_text = text[offset:chunk_end]
                
                # Build loc: prefer char_start/char_end for text chunks
                loc = {
                    "char_start": offset,
                    "char_end": chunk_end,
                }
                # Preserve any existing loc keys (e.g., from code segments)
                loc.update(base_loc)
                
                chunk_hash = self._compute_chunk_hash(chunk_text, loc)
                all_chunks.append(Chunk(
                    text=chunk_text,
                    loc=loc,
                    chunk_hash=chunk_hash,
                ))
                
                # If we've reached the end of the text, break
                if chunk_end >= len(text):
                    break
                
                # Move to next chunk with overlap
                offset = chunk_end - self.overlap
                
                # Prevent infinite loop: ensure offset always advances
                if offset >= chunk_end:
                    offset = chunk_end
        
        return all_chunks
    
    def _compute_line_offsets(self, text: str) -> List[int]:
        """Compute offset of each line start."""
        offsets = [0]
        for i, char in enumerate(text):
            if char == "\n":
                offsets.append(i + 1)
        return offsets
    
    def _offset_to_line(self, offset: int, line_offsets: List[int]) -> int:
        """Convert character offset to line number."""
        for i, line_offset in enumerate(line_offsets):
            if line_offset > offset:
                return max(1, i)
        return len(line_offsets)
    
    def _compute_chunk_hash(self, text: str, loc: dict) -> str:
        """Compute SHA256 hash of (text + canonical_json(loc))."""
        # Canonical JSON: sort keys, no whitespace
        loc_json = json.dumps(loc, sort_keys=True, separators=(',', ':'))
        content = text + loc_json
        return hashlib.sha256(content.encode()).hexdigest()

