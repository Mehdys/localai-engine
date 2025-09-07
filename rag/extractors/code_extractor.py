"""Code file extraction with structure awareness."""
from pathlib import Path
from typing import List
import re
from rag.types import Segment


class CodeExtractor:
    """Extract code from code files with structure awareness."""
    
    # Patterns for different languages
    FUNCTION_PATTERNS = {
        ".py": [
            r"^def\s+\w+.*?:",
            r"^class\s+\w+.*?:",
            r"^async\s+def\s+\w+.*?:",
        ],
        ".js": [
            r"^(export\s+)?(async\s+)?function\s+\w+.*?\{",
            r"^(export\s+)?const\s+\w+\s*=\s*(async\s+)?\(.*?\)\s*=>\s*\{",
            r"^(export\s+)?class\s+\w+.*?\{",
        ],
        ".ts": [
            r"^(export\s+)?(async\s+)?function\s+\w+.*?\{",
            r"^(export\s+)?const\s+\w+\s*[:=]\s*(async\s+)?\(.*?\)\s*[:=]\s*\{",
            r"^(export\s+)?(abstract\s+)?class\s+\w+.*?\{",
            r"^(export\s+)?interface\s+\w+.*?\{",
        ],
    }
    
    def extract(self, file_path: Path) -> List[Segment]:
        """
        Extract code from file.
        
        Returns:
            List[Segment] with one segment per function/class when structure is detected,
            or single segment with empty loc as fallback
        """
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                code = f.read()
        except UnicodeDecodeError:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                code = f.read()
        except Exception as e:
            raise IOError(f"Failed to extract code from {file_path}: {e}")
        
        # Extract structure information
        structure = self._extract_structure(code, file_path.suffix)
        
        if not structure:
            # Fallback: single segment with empty loc
            return [Segment(text=code, loc={})]
        
        # Create one segment per function/class
        lines = code.split("\n")
        segments = []
        
        # Sort structure by line number
        structure_sorted = sorted(structure, key=lambda x: x["line"])
        
        for i, item in enumerate(structure_sorted):
            line_start = item["line"]
            # Find line_end: next structure item or end of file
            if i + 1 < len(structure_sorted):
                line_end = structure_sorted[i + 1]["line"] - 1
            else:
                line_end = len(lines)
            
            # Extract text for this segment
            segment_lines = lines[line_start - 1:line_end]
            segment_text = "\n".join(segment_lines)
            
            segments.append(Segment(
                text=segment_text,
                loc={"line_start": line_start, "line_end": line_end}
            ))
        
        return segments if segments else [Segment(text=code, loc={})]
    
    def _extract_structure(self, code: str, extension: str) -> List[dict]:
        """Extract function/class boundaries."""
        patterns = self.FUNCTION_PATTERNS.get(extension.lower(), [])
        if not patterns:
            return []
        
        lines = code.split("\n")
        structure = []
        
        for pattern in patterns:
            for i, line in enumerate(lines, 1):
                if re.match(pattern, line.strip()):
                    # Try to find the name
                    name_match = re.search(r"(?:def|class|function|const|interface)\s+(\w+)", line)
                    name = name_match.group(1) if name_match else f"unnamed_{i}"
                    
                    structure.append({
                        "type": "function" if "def" in pattern or "function" in pattern else "class",
                        "name": name,
                        "line": i,
                    })
        
        return structure

