# Step 1 Verification Test Suite

## Overview

This test suite (`test_step1_verification.py`) comprehensively verifies that Step 1 of the v2 storage refactor is correctly implemented. All tests are deterministic, fast (<15s), and run in complete isolation using temporary directories.

## Running the Tests

### Using pytest (recommended)
```bash
pytest -q tests/step1/test_step1_verification.py
```

### Using the runner script
```bash
python scripts/verify_step1.py
```

### Using Makefile
```bash
make test-step1
# or
make verify-step1
```

## Test Coverage

### Test A: Unified DB Schema
- ✅ Single `rag.db` file created in temp directory
- ✅ All required tables exist: `documents`, `doc_versions`, `chunks`, `embeddings`, `manifests`
- ✅ No legacy DB files (`registry.db`, `metadata.db`) created
- ✅ Tables have correct column structure

### Test B: No JSON Mapping File
- ✅ `faiss.index.mapping.json` is NOT created during indexing
- ✅ No mapping JSON files exist anywhere in temp directory

### Test C: Stable Vector IDs
- ✅ Indexing creates chunks and embeddings in DB
- ✅ `vector_id` in embeddings table equals `chunk_id` (stable mapping)
- ✅ Search returns valid chunk IDs that exist in DB
- ✅ Retrieval joins correctly (can fetch chunks by vector_id)

### Test D: Idempotency
- ✅ Running index twice on same files doesn't duplicate chunks
- ✅ Embedding counts remain stable on re-index

### Test E: Incremental Update
- ✅ Modifying a file creates a new `doc_version` row
- ✅ Unchanged files don't get duplicated
- ✅ Only changed/new chunks get new embeddings

### Test F: Atomic FAISS Persistence
- ✅ FAISS index file exists after indexing
- ✅ No `.tmp` files remain after normal indexing
- ✅ Index can be loaded successfully after saving

### Test G: Manifest
- ✅ Manifest exists in DB after indexing
- ✅ Manifest contains all required fields
- ✅ Manifest values match actual config
- ✅ Manifest can detect config mismatches

## How Tests Avoid Ollama

Tests use a `MockEmbeddings` class that generates **deterministic** embeddings from text hashes:

```python
class MockEmbeddings:
    def embed(self, text: str) -> np.ndarray:
        # Uses SHA256 hash of text to generate deterministic vector
        # Normalized to unit vector for cosine similarity
```

This ensures:
- Tests are deterministic (same text → same embedding)
- No network calls to Ollama
- Fast execution (<15s total)

## How Tests Avoid ~/.rag_data

Tests use pytest fixtures to create temporary directories:

```python
@pytest.fixture
def temp_data_dir(tmp_path):
    """Create temporary data directory."""
    data_dir = tmp_path / ".rag_data"
    data_dir.mkdir()
    return data_dir

@pytest.fixture
def test_config(temp_data_dir):
    """Create test configuration with temp data directory."""
    config = RAGConfig(
        data_dir=temp_data_dir,
        db_path=temp_data_dir / "rag.db",
        index_path=temp_data_dir / "faiss.index",
    )
    return config
```

All tests use `test_config` which points to the temporary directory, never touching `~/.rag_data`.

## Test Corpus

Tests use a minimal deterministic corpus:
- `a.txt`: "This is a test sentence for indexing."
- `b.py`: Simple function returning "world"

This is sufficient to verify all Step 1 requirements without requiring large datasets.

## Internal Indexing Function

The test suite uses `rag.indexing.index_folder()` which is an internal function that can be called programmatically (used by both CLI and tests). This allows tests to:

- Call indexing directly without spawning subprocesses
- Inject mock embeddings for deterministic testing
- Control configuration precisely

## Expected Output

When all tests pass, you should see:

```
tests/step1/test_step1_verification.py::TestA_UnifiedDBSchema::test_db_created_in_temp_dir PASSED
tests/step1/test_step1_verification.py::TestA_UnifiedDBSchema::test_required_tables_exist PASSED
...
tests/step1/test_step1_verification.py::TestG_Manifest::test_manifest_detects_config_mismatch PASSED
tests/step1/test_step1_verification.py::test_step1_complete PASSED

========== X passed in Y.YYs ==========
```

## Troubleshooting

### Import Errors
If you see import errors, ensure you're running from the project root:
```bash
cd /path/to/localai-engine
pytest -q tests/step1/test_step1_verification.py
```

### FAISS Import Errors
Ensure `faiss-cpu` is installed:
```bash
pip install faiss-cpu
```

### Test Failures
If a test fails, check:
1. Are you using the latest code? (Step 1 must be fully implemented)
2. Is the temp directory being cleaned up properly?
3. Are there any file permission issues?

## Acceptance Criteria

✅ All tests pass without errors
✅ Tests complete in <15 seconds
✅ No files created in `~/.rag_data`
✅ No network calls to Ollama
✅ Tests are deterministic (same results on every run)
