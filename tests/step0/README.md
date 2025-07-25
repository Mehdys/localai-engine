# Step 0 Testing Guide

This guide helps you verify that Step 0 implementation is working correctly.

## Quick Test

Run the automated test script:

```bash
# Make sure you're in the project root
cd /Users/mehdigribaa/Desktop/Projects/NotFinishedYet/localai-engine

# Run the manual test script
./tests/step0/test_step0_manual.sh
```

Or run pytest directly:

```bash
# Run all Step 0 tests
pytest tests/step0/test_step0.py -v

# Run baseline tests
pytest tests/step0/test_baseline.py -v

# Run comprehensive Step 0 verification
pytest tests/step0/test_step0.py::test_step0_complete -v
```

## Manual Verification Checklist

### ✅ 1. Baseline Tests Pass

```bash
pytest tests/step0/test_baseline.py -v
```

**Expected**: All 5 tests pass:
- `test_db_init` - Database initialization
- `test_db_crud_operations` - CRUD operations
- `test_chunker_text_returns_chunks` - Text chunker
- `test_chunker_code_returns_chunks` - Code chunker
- `test_registry_integrity_check` - Integrity checking

### ✅ 2. CLI Commands Exist

```bash
rag --help
```

**Expected**: Should show:
- `validate` - Validate system health
- `explain` - Explain retrieval process
- `ingest` - (existing)
- `index` - (existing)
- `ask` - (existing)
- `stats` - (existing)

### ✅ 3. Validate Command Works

```bash
rag validate
```

**Expected Output** (if Ollama is running):
```
🔍 Running system validation...

✓ Ollama reachable at http://localhost:11434
✓ Embedding model 'nomic-embed-text' found (768 dim)
✓ LLM model 'llama3.2' found
⚠ No index found (run 'rag index' to create one)
✓ Database integrity: OK
  - No orphan chunks
  - Total files: 0
  - Total chunks: 0

✅ Validation complete!
```

**Note**: If Ollama is not running, it will show errors - that's expected. The command should still run without crashing.

### ✅ 4. Explain Command Works

```bash
rag explain "test question"
```

**Expected Output** (if no index exists):
```
Question: test question

Error: No index found. Run 'rag index' first.
```

**Expected Output** (if index exists):
```
Question: test question

Retrieved Documents (top 5):
  1. score: 0.847 (raw: 0.694) | path/to/file.py:lines 1-10
     "def hello(): ..."

Prompt length: 1,234 characters
Memory hits: 0 (no session)
```

### ✅ 5. Existing Commands Still Work

```bash
# These should all work without errors
rag ingest --help
rag index --help
rag ask --help
rag stats --help
```

### ✅ 6. Integrity Check Works

```python
# Run this in Python
from rag.registry import FileRegistry
from pathlib import Path
import tempfile

with tempfile.TemporaryDirectory() as tmpdir:
    db_path = Path(tmpdir) / "test.db"
    registry = FileRegistry(db_path)
    
    integrity = registry.check_integrity()
    print(integrity)
    # Should show: {'orphan_chunks': 0, 'total_chunks': 0, 'total_files': 0, 'is_valid': True}
```

### ✅ 7. Explain Method Works

```python
# Run this in Python (with mocked dependencies)
from rag.rag_pipeline import RAGPipeline
from rag.config import RAGConfig
from pathlib import Path
import tempfile

# This is tested in test_step0.py
# The explain method should return:
# {
#     "retrieved_chunks": [...],
#     "prompt_length": int,
#     "memory_hits": int
# }
```

## Full Integration Test

To do a full integration test with real Ollama:

```bash
# 1. Start Ollama (if not running)
ollama serve

# 2. Ensure models are available
ollama pull nomic-embed-text
ollama pull llama3.2

# 3. Create test data
mkdir -p ~/rag-test-step0
echo "def hello(): return 'world'" > ~/rag-test-step0/test.py
echo "This is a test document." > ~/rag-test-step0/test.txt

# 4. Index the test data
rag index ~/rag-test-step0

# 5. Run validate
rag validate
# Should show index with vectors

# 6. Run explain
rag explain "What does hello do?"
# Should show retrieved chunks with scores

# 7. Verify stats
rag stats
# Should show indexed files and chunks
```

## Test Results

After running all tests, you should see:

- ✅ All baseline tests pass
- ✅ All Step 0 tests pass
- ✅ `rag validate` command exists and runs
- ✅ `rag explain` command exists and runs
- ✅ Existing commands (`ingest`, `index`, `ask`, `stats`) still work
- ✅ No breaking changes to existing functionality

## Troubleshooting

### Tests fail with "typer.testing not available"

This is OK - the test will skip that part. The important thing is that the commands exist and can be called directly.

### Validate fails with "Ollama not reachable"

This is expected if Ollama is not running. The command should still complete and show other checks.

### Explain fails with "No index found"

This is expected if you haven't indexed anything yet. Create a test index first with `rag index`.

## Success Criteria

Step 0 is complete when:

1. ✅ All baseline tests pass
2. ✅ `rag validate` command exists and performs all required checks
3. ✅ `rag explain` command exists and shows retrieval details
4. ✅ No existing functionality is broken
5. ✅ Integrity check method exists in FileRegistry
6. ✅ Explain method exists in RAGPipeline
