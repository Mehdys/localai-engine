"""File scanning and discovery with ignore patterns."""
import os
import hashlib
import fnmatch
from pathlib import Path
from typing import List, Set, Optional, Tuple, Dict
from dataclasses import dataclass
from datetime import datetime


@dataclass
class FileInfo:
    """File metadata for registry."""
    path: Path
    size: int
    mtime: float
    sha256: str
    file_type: str  # 'text', 'code', or 'pdf'
    
    def to_dict(self):
        return {
            "path": str(self.path),
            "size": self.size,
            "mtime": self.mtime,
            "sha256": self.sha256,
            "file_type": self.file_type,
        }
    
    @classmethod
    def from_dict(cls, d: dict):
        return cls(
            path=Path(d["path"]),
            size=d["size"],
            mtime=d["mtime"],
            sha256=d["sha256"],
            file_type=d["file_type"],
        )


@dataclass
class ScanStatistics:
    """Statistics about a directory scan."""
    total_files: int = 0
    ignored_files: int = 0
    unsupported_files: int = 0
    indexable_by_type: Dict[str, int] = None
    error_files: int = 0
    
    def __post_init__(self):
        if self.indexable_by_type is None:
            self.indexable_by_type = {}
    
    def get_total_indexable(self) -> int:
        """Get total number of indexable files."""
        return sum(self.indexable_by_type.values())
    
    def verify_sum(self) -> bool:
        """Verify that the sum matches total files."""
        calculated_total = (
            self.ignored_files + 
            self.unsupported_files + 
            self.get_total_indexable() +
            self.error_files
        )
        return calculated_total == self.total_files


class FileScanner:
    """Scans directories and filters files based on patterns."""
    
    # Strong default ignores (always applied)
    DEFAULT_IGNORES = [
        ".git/",
        "node_modules/",
        ".venv/",
        "venv/",
        "dist/",
        "build/",
        "__pycache__/",
        ".DS_Store",
        "*.pyc",
        "*.pyo",
        "*.lock",
        "*.log",
    ]
    
    def __init__(
        self,
        text_extensions: List[str],
        code_extensions: List[str],
        ignore_patterns: List[str],
    ):
        self.text_extensions = set(text_extensions)
        self.code_extensions = set(code_extensions)
        # Merge default ignores with config ignores
        self.ignore_patterns = self.DEFAULT_IGNORES + ignore_patterns
        # Cache for .ragignore files per directory
        self._ragignore_cache: Dict[Path, List[str]] = {}
    
    def _read_ragignore(self, directory: Path) -> List[str]:
        """Read .ragignore file from directory if it exists."""
        if directory in self._ragignore_cache:
            return self._ragignore_cache[directory]
        
        ragignore_path = directory / ".ragignore"
        patterns = []
        
        if ragignore_path.exists() and ragignore_path.is_file():
            try:
                with open(ragignore_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        # Skip empty lines and comments
                        if not line or line.startswith("#"):
                            continue
                        patterns.append(line)
            except (IOError, UnicodeDecodeError):
                # If we can't read it, just skip it
                pass
        
        self._ragignore_cache[directory] = patterns
        return patterns
    
    def _get_ignore_patterns_for_path(self, path: Path) -> List[str]:
        """Get all ignore patterns that apply to a given path.
        
        Includes:
        - Default ignores
        - Config ignores
        - .ragignore patterns from root and all parent directories
        """
        all_patterns = list(self.ignore_patterns)
        
        # Collect .ragignore patterns from root and all parent directories
        current = path if path.is_dir() else path.parent
        root = path.anchor  # Get root of filesystem
        
        while current != current.parent:  # Stop at filesystem root
            ragignore_patterns = self._read_ragignore(current)
            all_patterns.extend(ragignore_patterns)
            
            if current == root:
                break
            current = current.parent
        
        return all_patterns
    
    def should_ignore(self, path: Path, root: Optional[Path] = None) -> bool:
        """Check if path matches any ignore pattern.
        
        Args:
            path: Path to check
            root: Root directory being scanned (for .ragignore lookup)
        """
        # Get all patterns that apply to this path
        if root is not None:
            # Use root-relative patterns
            all_patterns = list(self.ignore_patterns)
            # Collect .ragignore from root and path's parent chain
            current = path.parent
            while current != root.parent and current != current.parent:
                ragignore_patterns = self._read_ragignore(current)
                all_patterns.extend(ragignore_patterns)
                if current == root:
                    break
                current = current.parent
        else:
            all_patterns = self._get_ignore_patterns_for_path(path)
        
        path_str = str(path)
        path_parts = path.parts
        
        for pattern in all_patterns:
            # Handle directory patterns (ending with /)
            if pattern.endswith("/"):
                pattern_dir = pattern.rstrip("/")
                if pattern_dir in path_parts:
                    return True
                # Check if any part matches
                if any(fnmatch.fnmatch(part, pattern_dir) for part in path_parts):
                    return True
            # Handle file patterns
            elif fnmatch.fnmatch(path.name, pattern):
                return True
            elif fnmatch.fnmatch(path_str, pattern):
                return True
        
        return False
    
    def get_file_type(self, path: Path) -> Optional[str]:
        """Determine file type from extension."""
        ext = path.suffix.lower()
        if ext in self.text_extensions:
            return "text"
        elif ext in self.code_extensions:
            return "code"
        # PDF support for v2
        elif ext == ".pdf":
            return "pdf"
        return None
    
    def compute_file_hash(self, path: Path) -> str:
        """Compute SHA256 hash of file."""
        sha256 = hashlib.sha256()
        try:
            with open(path, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    sha256.update(chunk)
            return sha256.hexdigest()
        except Exception as e:
            raise IOError(f"Failed to hash {path}: {e}")
    
    def scan_directory(
        self,
        root: Path,
        dry_run: bool = False,
    ) -> Tuple[List[FileInfo], ScanStatistics]:
        """Scan directory and return list of indexable files and statistics."""
        files = []
        stats = ScanStatistics()
        root = Path(root).resolve()
        
        if not root.exists():
            raise ValueError(f"Root directory does not exist: {root}")
        
        if not root.is_dir():
            raise ValueError(f"Path is not a directory: {root}")
        
        dir_count = 0
        for dirpath, dirnames, filenames in os.walk(root):
            dirpath = Path(dirpath)
            dir_count += 1
            
            # Print progress every 100 directories
            if dir_count % 100 == 0:
                print(f"  📂 Scanned {dir_count:,} directories | Found {len(files):,} files", end="\r")
            
            # Print current directory being scanned (every 200 directories to reduce spam)
            if dir_count % 200 == 0:
                # Truncate long paths for readability
                display_path = str(dirpath)
                if len(display_path) > 60:
                    display_path = "..." + display_path[-57:]
                print(f"\n  🔍 Scanning: {display_path}")
            
            # Filter out ignored directories (use root for .ragignore lookup)
            ignored_dirs = [d for d in dirnames if self.should_ignore(dirpath / d, root)]
            
            dirnames[:] = [
                d for d in dirnames
                if not self.should_ignore(dirpath / d, root)
            ]
            
            for filename in filenames:
                filepath = dirpath / filename
                stats.total_files += 1
                
                # Check if file should be ignored (use root for .ragignore lookup)
                if self.should_ignore(filepath, root):
                    stats.ignored_files += 1
                    continue
                
                # Check if file type is supported
                file_type = self.get_file_type(filepath)
                if file_type is None:
                    stats.unsupported_files += 1
                    continue
                
                try:
                    stat = filepath.stat()
                    size = stat.st_size
                    mtime = stat.st_mtime
                    
                    # Compute hash only if not dry run
                    if dry_run:
                        sha256 = "dry-run"
                    else:
                        sha256 = self.compute_file_hash(filepath)
                    
                    files.append(
                        FileInfo(
                            path=filepath,
                            size=size,
                            mtime=mtime,
                            sha256=sha256,
                            file_type=file_type,
                        )
                    )
                    
                    # Track by file type
                    stats.indexable_by_type[file_type] = stats.indexable_by_type.get(file_type, 0) + 1
                    
                    # Print every 100 files found (less frequent to reduce output)
                    if len(files) % 100 == 0:
                        print(f"\n  ✅ Found {len(files):,} indexable files so far...", end="\r")
                        
                except (OSError, IOError) as e:
                    # Skip files we can't read
                    stats.error_files += 1
                    print(f"  [Warning] Skipping {filepath}: {e}")
                    continue
        
        print(f"\n  ✅ Complete! Scanned {dir_count:,} directories, found {len(files):,} indexable files")
        return files, stats


# 
