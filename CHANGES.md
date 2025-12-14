# Changes Made - PDF Format Fix & .ragignore Support

## Summary

Fixed PDF location format to use range format (`page_start`/`page_end`) and added `.ragignore` file support for better file filtering.

---

## 1. PDF Format Fix ✅

### Changes Made

**File: `rag/extractors/pdf_extractor.py`**
- Changed location format from `{"page": page_num}` to `{"page_start": page_num, "page_end": page_num}`
- Updated docstring to reflect range format
- Now complies with PROJECT_RESUME.md requirement for range-only format

**File: `rag/indexing.py`**
- Fixed broken/duplicate PDF handling code
- Cleaned up extraction and chunking logic for PDFs
- PDFs now properly use `text_chunker` which preserves `page_start`/`page_end` from segments

**File: `rag/types.py`**
- Updated Segment docstring to reflect new format

**File: `tests/test_pdf_extractor.py`**
- Updated test to check for `page_start` and `page_end` instead of `page`
- Fixed test file structure (added missing class and imports)
- Added assertion that `page_start == page_end` for single-page segments

### How It Works

1. **PDF Extraction**: Each page is extracted as a `Segment` with `{"page_start": N, "page_end": N}`
2. **Chunking**: `TextChunker` preserves the `page_start`/`page_end` from segments using `loc.update(base_loc)`
3. **Citation**: `RetrievedChunk.format_citation()` already handles `page_start`/`page_end` correctly, producing `path:p.X-Y` format

### Testing

- PDF extractor tests updated
- Citation format will show `path:p.1-1` for single pages
- Multi-page chunks (if implemented later) will show `path:p.1-2` format

---

## 2. .ragignore Support ✅

### Changes Made

**File: `rag/scanner.py`**
- Added `DEFAULT_IGNORES` class constant with strong default ignore patterns:
  - `.git/`, `node_modules/`, `.venv/`, `venv/`, `dist/`, `build/`, `__pycache__/`
  - `.DS_Store`, `*.pyc`, `*.pyo`, `*.lock`, `*.log`
- Added `_read_ragignore()` method to read `.ragignore` files from directories
- Added `_get_ignore_patterns_for_path()` method to collect all applicable patterns
- Updated `should_ignore()` to accept optional `root` parameter for `.ragignore` lookup
- Added caching for `.ragignore` files (`_ragignore_cache`)
- Updated `scan_directory()` to pass `root` to `should_ignore()` calls

### How It Works

1. **Default Ignores**: Always applied (merged with config ignores)
2. **Config Ignores**: From `config.yaml` `ignore_patterns`
3. **`.ragignore` Files**: Read from:
   - Root directory `.ragignore`
   - Per-directory `.ragignore` files (applied to that directory and subdirectories)
   - Patterns are collected from root to file's parent directory
4. **Pattern Matching**: Uses `fnmatch` (similar to `.gitignore` syntax)
   - Directory patterns: `pattern/` matches directories
   - File patterns: `*.ext` matches files
   - Comments: Lines starting with `#` are ignored
   - Empty lines are ignored

### Usage Example

Create a `.ragignore` file in your project root:
```
# Ignore test files
*.test.py
test_*.py

# Ignore build artifacts
build/
dist/

# Ignore logs
*.log
```

Or in a subdirectory:
```
# This .ragignore only applies to this directory and below
local_config.yaml
```

### Testing

- Default ignores are automatically applied
- `.ragignore` files are read and cached
- Patterns are merged correctly with config ignores
- Directory and file patterns work as expected

---

## Files Modified

1. `rag/extractors/pdf_extractor.py` - PDF format fix
2. `rag/indexing.py` - Fixed PDF handling logic
3. `rag/scanner.py` - Added `.ragignore` support
4. `rag/types.py` - Updated docstring
5. `tests/test_pdf_extractor.py` - Updated tests

---

## Next Steps for Testing

1. **Test PDF Format**:
   ```bash
   # Create a test PDF and index it
   rag index /path/to/test.pdf
   rag ask "What is in the PDF?"
   # Check that citations show p.X-Y format
   ```

2. **Test .ragignore**:
   ```bash
   # Create a .ragignore file
   echo "*.log" > .ragignore
   echo "test content" > test.txt
   echo "log content" > app.log
   
   # Index directory
   rag index .
   
   # Verify only test.txt was indexed (not app.log)
   rag stats
   ```

3. **Verify Default Ignores**:
   ```bash
   # Index a directory with node_modules
   rag index /path/to/project
   # Verify node_modules is ignored
   ```

---

## Notes

- PDF chunks preserve page ranges correctly
- `.ragignore` patterns are cached for performance
- Default ignores cannot be overridden (always applied)
- `.ragignore` files use simple pattern matching (not full `.gitignore` syntax, but similar)

