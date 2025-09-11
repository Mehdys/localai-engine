"""Code-aware chunking."""
from typing import List
import json
import hashlib
from rag.types import Segment, Chunk
from rag.chunkers.text_chunker import TextChunker


class CodeChunker:
    """Chunk code with preference for function/class boundaries."""
    
    def __init__(self, chunk_size: int = 800, overlap: int = 100):
        self.chunk_size = chunk_size
        self.overlap = overlap
        self.fallback_chunker = TextChunker(chunk_size, overlap)
    
    def chunk(self, segments: List[Segment]) -> List[Chunk]:
        """
        Chunk code segments, preferring function/class boundaries.
        
        Args:
            segments: List of Segment objects (from code extractor)
        
        Returns:
            List of Chunk objects with chunk_hash
        """
        all_chunks = []
        
        for segment in segments:
            text = segment.text
            base_loc = segment.loc.copy() if segment.loc else {}
            
            # If segment has line_start/line_end, prefer code chunking
            if "line_start" in base_loc and "line_end" in base_loc:
                # Code segment: chunk preserving line boundaries
                chunks = self._chunk_code_segment(segment)
                all_chunks.extend(chunks)
            else:
                # Fallback to text chunking
                chunks = self.fallback_chunker.chunk([segment])
                all_chunks.extend(chunks)
        
        return all_chunks
    
    def _chunk_code_segment(self, segment: Segment) -> List[Chunk]:
        """Chunk a code segment that has line_start/line_end."""
        text = segment.text
        base_loc = segment.loc.copy()
        line_start = base_loc.get("line_start", 1)
        line_end = base_loc.get("line_end", line_start)
        
        lines = text.split("\n")
        
        if len(text) <= self.chunk_size:
            # Single chunk
            loc = {
                "line_start": line_start,
                "line_end": line_end,
            }
            chunk_hash = self._compute_chunk_hash(text, loc)
            return [Chunk(text=text, loc=loc, chunk_hash=chunk_hash)]
        
        # Multi-chunk: try to preserve function boundaries
        chunks = []
        current_chunk_lines = []
        current_size = 0
        current_start_line = line_start
        
        for i, line in enumerate(lines):
            line_size = len(line) + 1  # +1 for newline
            current_chunk_lines.append(line)
            current_size += line_size
            
            # If chunk is too large, finalize it
            if current_size >= self.chunk_size:
                chunk_text = "\n".join(current_chunk_lines)
                current_end_line = current_start_line + len(current_chunk_lines) - 1
                
                loc = {
                    "line_start": current_start_line,
                    "line_end": current_end_line,
                }
                chunk_hash = self._compute_chunk_hash(chunk_text, loc)
                chunks.append(Chunk(
                    text=chunk_text,
                    loc=loc,
                    chunk_hash=chunk_hash,
                ))
                
                # Start new chunk with overlap
                overlap_lines = max(1, min(len(current_chunk_lines), self.overlap // 50))  # Approximate overlap
                current_chunk_lines = current_chunk_lines[-overlap_lines:]
                current_start_line = current_end_line - overlap_lines + 1
                current_size = sum(len(l) + 1 for l in current_chunk_lines)
        
        # Add remaining lines as final chunk
        if current_chunk_lines:
            chunk_text = "\n".join(current_chunk_lines)
            current_end_line = current_start_line + len(current_chunk_lines) - 1
            
            loc = {
                "line_start": current_start_line,
                "line_end": current_end_line,
            }
            chunk_hash = self._compute_chunk_hash(chunk_text, loc)
            chunks.append(Chunk(
                text=chunk_text,
                loc=loc,
                chunk_hash=chunk_hash,
            ))
        
        return chunks if chunks else self.fallback_chunker.chunk([segment])
    
    def _compute_chunk_hash(self, text: str, loc: dict) -> str:
        """Compute SHA256 hash of (text + canonical_json(loc))."""
        # Canonical JSON: sort keys, no whitespace
        loc_json = json.dumps(loc, sort_keys=True, separators=(',', ':'))
        content = text + loc_json
        return hashlib.sha256(content.encode()).hexdigest()

