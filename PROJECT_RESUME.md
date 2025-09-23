# LocalAI Engine - Project Resume

## Project Overview

**LocalAI Engine** is a production-ready, local-first RAG (Retrieval-Augmented Generation) system designed for macOS. It enables users to index their files and documents locally and query them using natural language questions. The entire system runs locally using Ollama for both embeddings and LLM inference, ensuring complete privacy and no dependency on external APIs.

### Key Characteristics
- **100% Local Processing**: All data and computation happens on your machine
- **Incremental Indexing**: Only re-indexes changed files for efficiency
- **Smart Chunking**: Code-aware and text-aware chunking strategies
- **Fast Search**: FAISS-based vector store with HNSW indexing
- **Production-Ready**: Clean architecture with modular design

---

## V2 Refactoring Plan

### Non-Negotiable Constraints

1. **Backward Compatible CLI Behavior**
   - Existing commands (`rag ingest`, `rag index`, `rag ask`, `rag stats`) must work unchanged
   - No breaking changes to user-facing interfaces
   - Preserve all existing functionality

2. **No External APIs**
   - Everything must remain 100% local using Ollama
   - No cloud services or external dependencies

3. **Each Step Must Keep the App Runnable**
   - Incremental refactoring approach
   - System must be functional after each step
   - No "big bang" refactoring

4. **Add Tests + Manual Test Plan**
   - Pytest baseline tests (fast)
   - Manual test plan with step-by-step commands
   - Tests must pass at each step

5. **Prefer Small Commits/PR-Sized Steps**
   - Each step should be independently reviewable
   - Clear boundaries between steps
   - Easy to rollback if needed

---

## Step-by-Step Refactoring Plan

### Step 0 — Safety Net First ⚠️ **START HERE**

**Goal**: Add diagnostic and debugging tools before refactoring begins.

#### 0.1 Add `rag validate` Command

**Purpose**: Health check and diagnostics before/after refactoring.

**Checks**:
- ✅ Check Ollama reachability (ping base_url)
- ✅ Verify embedding model exists (check Ollama models list)
- ✅ Verify LLM model exists
- ✅ Detect embedding dimension (by embedding a test string)
- ✅ Show index type (HNSW/Flat) and vector counts for both indexes
- ✅ **Integrity SQL checks**:
  - Orphan chunks (doc_version missing)
  - Orphan embeddings (chunk missing)
  - Missing vectors referenced by DB (FAISS search sanity check)
- ✅ Verify manifest matches current config (if exists)

**Output Format**:
```
✓ Ollama reachable at http://localhost:11434
✓ Embedding model 'nomic-embed-text' found (768 dim)
✓ LLM model 'llama3' found
✓ Documents index: HNSW with 1,234 vectors
✓ Memory index: Flat with 56 vectors
✓ Database integrity: OK
  - No orphan chunks
  - No orphan embeddings
  - All vector_ids found in FAISS indexes
⚠ Manifest mismatch: embedding model changed (run 'rag reembed')
```

#### 0.2 Add `rag explain "<question>"` Command

**Purpose**: Debug retrieval and prompt construction.

**Output**:
- Print retrieved document chunks (top_k) with:
  - Raw score (from FAISS, can be -1 to 1)
  - Display score (normalized 0-1: `(raw_score + 1) / 2`)
  - Citation (formatted: `path:lines a-b` or `path:p.X-Y`)
  - Chunk text preview (first 200 chars)
- (Later) Print memory hits if session enabled
- Show prompt length in characters
- Show which chunks were selected and why

**Example Output**:
```
Retrieved Documents (top 5):
  1. score: 0.847 (raw: 0.694) | src/rag_pipeline.py:lines 26-45
     "class RAGPipeline: ..."
  2. score: 0.812 (raw: 0.624) | docs/README.md:lines 12-28
     "The RAG system supports..."
  
Prompt length: 2,456 characters
Memory hits: 0 (no session)
```

#### 0.3 Add Pytest Baseline Tests (Fast)

**Location**: `tests/test_baseline.py`

**Tests**:
1. **DB Init Test**
   - Create new DB, verify schema exists
   - Verify all tables are created
   - Test basic CRUD operations

2. **Chunker Test**
   - Text chunker returns non-empty chunks
   - Code chunker returns non-empty chunks
   - Chunks have valid loc_json

3. **Vector Store Test**
   - `add_vectors()` returns vector_ids
   - `search()` returns results with scores
   - Scores are in valid range (-1 to 1 for cosine)

4. **Extractor Test**
   - Text extractor returns segments
   - Code extractor returns segments
   - Segments have valid loc dicts

**Run**: `pytest tests/test_baseline.py -v` (should complete in < 5 seconds)

---

### Step 1 — Single DB Backbone + Manifest

**Goal**: Replace fragmented storage with unified SQLite database.

#### 1.0 Add `.ragignore` Support

**Location**: `rag/scanner.py`

**Implementation**:
- Read `.ragignore` files (similar to `.gitignore` syntax)
- Support patterns in:
  - Root directory `.ragignore`
  - Per-directory `.ragignore` files
- **Strong default ignores** (always applied):
  - `.git/`
  - `node_modules/`
  - `.venv/`, `venv/`
  - `dist/`, `build/`
  - `__pycache__/`
  - `.DS_Store`
  - `*.pyc`, `*.pyo`
  - `*.lock`
  - `*.log`
- Merge `.ragignore` patterns with config ignore patterns
- Apply before file type detection

#### 1.1 Create Unified Database Schema

**Location**: `rag/db.py`

**Database Path**: `~/.rag_data/rag.db` (single file)

**Schema**:

```sql
-- Core document tracking
CREATE TABLE documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    path TEXT UNIQUE NOT NULL,
    doc_type TEXT NOT NULL,  -- 'text', 'code', 'pdf'
    size_bytes INTEGER NOT NULL,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);

-- Document versioning (for change detection)
CREATE TABLE doc_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER NOT NULL,
    sha256 TEXT NOT NULL,
    mtime REAL NOT NULL,
    extractor_version TEXT,  -- e.g., '1.0'
    chunker_version TEXT,     -- e.g., '1.0'
    created_at REAL NOT NULL,
    UNIQUE(document_id, sha256),
    FOREIGN KEY(document_id) REFERENCES documents(id)
);

-- Chunks (output of chunkers)
CREATE TABLE chunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_version_id INTEGER NOT NULL,
    chunk_hash TEXT NOT NULL,
    content TEXT NOT NULL,
    loc_json TEXT NOT NULL,  -- JSON: standardized range-only format
    created_at REAL NOT NULL,
    UNIQUE(doc_version_id, chunk_hash),
    FOREIGN KEY(doc_version_id) REFERENCES doc_versions(id)
);
-- loc_json format:
--   PDF: always {page_start, page_end}
--   code: always {line_start, line_end}
--   text fallback: {char_start, char_end}

-- Embeddings (links chunks to vectors)
CREATE TABLE embeddings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chunk_id INTEGER NOT NULL,
    model TEXT NOT NULL,      -- e.g., 'nomic-embed-text'
    dim INTEGER NOT NULL,     -- e.g., 768
    vector_id INTEGER NOT NULL,  -- Stable FAISS index ID (chunks.id)
    index_name TEXT NOT NULL DEFAULT 'documents',  -- Always 'documents' for doc chunks
    created_at REAL NOT NULL,
    UNIQUE(chunk_id, model, index_name),  -- Enforce uniqueness per index
    FOREIGN KEY(chunk_id) REFERENCES chunks(id)
);

-- Manifest (index metadata)
CREATE TABLE manifests (
    key TEXT UNIQUE NOT NULL,
    value_json TEXT NOT NULL  -- JSON value
);

-- Sessions (for conversation memory)
CREATE TABLE sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    created_at REAL NOT NULL
);

-- Messages (conversation history)
CREATE TABLE messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    role TEXT NOT NULL,  -- 'user' or 'assistant'
    content TEXT NOT NULL,
    created_at REAL NOT NULL,
    FOREIGN KEY(session_id) REFERENCES sessions(id)
);

-- Message embeddings (for memory retrieval - separate from document embeddings)
CREATE TABLE message_embeddings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id INTEGER NOT NULL,
    model TEXT NOT NULL,
    dim INTEGER NOT NULL,
    vector_id INTEGER NOT NULL,  -- Stable FAISS memory index ID (messages.id)
    created_at REAL NOT NULL,
    UNIQUE(message_id, model),  -- Keep separate from document embeddings
    FOREIGN KEY(message_id) REFERENCES messages(id)
);
```

**Indexes**:
- `CREATE INDEX idx_doc_versions_document_id ON doc_versions(document_id)`
- `CREATE INDEX idx_chunks_doc_version_id ON chunks(doc_version_id)`
- `CREATE INDEX idx_embeddings_chunk_id ON embeddings(chunk_id)`
- `CREATE INDEX idx_embeddings_vector_id ON embeddings(vector_id)`
- `CREATE INDEX idx_messages_session_id ON messages(session_id)`
- `CREATE INDEX idx_message_embeddings_message_id ON message_embeddings(message_id)`

#### 1.2 Version Constants and Manifest

**Define Version Constants** (`rag/constants.py` or in `rag/__init__.py`):

```python
# Version constants - bump when behavior changes
EXTRACTOR_VERSION = "1.0"
CHUNKER_VERSION = "1.0"
```

**Store in `manifests` table**:

```json
{
  "embedding_model": "nomic-embed-text",
  "embedding_dim": 768,
  "chunking_config_hash": "sha256_of_chunking_config",
  "extractor_version": "1.0",
  "chunker_version": "1.0",
  "faiss_type": "HNSW",
  "faiss_params": {
    "m": 32,
    "ef_construction": 200
  }
}
```

**Write Versions**:
- Store `extractor_version` and `chunker_version` in `doc_versions` table
- Store versions in manifest
- Bump constants when extractor/chunker behavior changes

**On Mismatch**:
- Print actionable guidance: `⚠ Manifest mismatch: embedding model changed. Run 'rag reembed' to update embeddings.`
- Or: `⚠ Manifest mismatch: chunking config changed. Run 'rag rebuild' to reindex.`
- Or: `⚠ Manifest mismatch: extractor_version changed. Run 'rag rebuild' to reindex.`

#### 1.3 Vector Mapping with Stable IDs

**Remove**: `faiss.index.mapping.json`

**Use Stable Vector IDs**: Implement FAISS indexes using `faiss.IndexIDMap2(base_index)`

**Implementation**:
- **For document chunks**: Use `chunks.id` as stable vector ID
- **For memory messages**: Use `messages.id` as stable vector ID
- Wrap base index: `index = faiss.IndexIDMap2(base_index)`
- Add vectors: `index.add_with_ids(vectors, ids)` where `ids` are stable DB IDs
- **Do not rely on implicit sequential FAISS IDs**
- Store `vector_id` in `embeddings` table (which equals `chunks.id`)
- When searching, `vector_id` from FAISS directly maps to `chunk_id` in DB
- No JSON mapping file needed

**Separate Indexes**:
- `faiss_docs.index`: Document embeddings (uses `chunks.id` as vector_id)
- `faiss_memory.index`: Memory embeddings (uses `messages.id` as vector_id)

#### 1.4 Persistence Robustness

**Atomic FAISS Save** (for both indexes):
```python
# Write to temp file first
temp_path = index_path.with_suffix('.tmp')
faiss.write_index(index, str(temp_path))
# Atomic rename
temp_path.replace(index_path)
```

**DB Transactions**:
- Wrap all indexing updates in transactions
- Rollback on error
- Commit only after successful vector store save

**Optional File Lock**:
- Use `fcntl` (Unix) or `msvcrt` (Windows) to prevent concurrent index runs
- Lock file: `~/.rag_data/.index.lock`
- Release on completion or error

**Separate Index Files**:
- `~/.rag_data/faiss_docs.index`: Document embeddings
- `~/.rag_data/faiss_memory.index`: Memory embeddings

#### 1.5 Migration from v1

**Command**: `rag migrate [--yes]`

**Process** (Non-interactive by default):
1. Check for old files:
   - `~/.rag_data/registry.db`
   - `~/.rag_data/metadata.db`
   - `~/.rag_data/faiss.index.mapping.json`
2. If found:
   - **Create backup**: `~/.rag_data/v1_backup/` (timestamped)
   - Copy old files to backup
   - Migrate data:
     - Copy files → documents
     - Copy chunks → chunks (with loc_json conversion to range-only format)
     - Copy vector mappings → embeddings table (with stable IDs)
   - **Never silently drop data**
   - Clear log messages: `Migrated 123 files, 456 chunks from v1 database`
   - Log backup location: `Backup saved to ~/.rag_data/v1_backup/2024-12-12T10-30-00/`

**Default Behavior**:
- **Non-interactive by default**: Auto-migrate with backups and logs
- If confirmation needed (e.g., large migration), use `--yes` flag to skip prompts
- Always create backups before migration
- Log all migration steps

---

### Step 2 — Pipeline Contracts (Segment/Chunk Types)

**Goal**: Standardize data flow with typed contracts.

#### 2.1 Create `rag/types.py`

**Data Classes**:

```python
@dataclass
class Segment:
    """Output of extractors, input to chunkers."""
    text: str
    loc: dict  # Location metadata

@dataclass
class Chunk:
    """Output of chunkers, stored in database."""
    text: str
    loc: dict  # Standardized location
    chunk_hash: str  # SHA256 of (text + loc_json)

@dataclass
class RetrievedChunk:
    """Search results with metadata."""
    chunk_id: str
    text: str
    loc: dict
    path: str
    score: float  # Raw score (-1 to 1)
    display_score: float  # Normalized (0 to 1)
```

#### 2.2 Update Extractors

**Contract**: Must return `List[Segment]`

**Text Extractor**:
- Return 1 segment with entire text
- `loc`: `{}` (no location info at extraction time)

**Code Extractor**:
- Return segments per function/class (if structure detected)
- `loc`: `{line_start: N, line_end: M}` when available (range format)
- Fallback: 1 segment with `{}` if no structure

**PDF Extractor** (Step 3):
- Return segments per page
- `loc`: `{page_start: N, page_end: N}` for each page (range format)

#### 2.3 Update Chunkers

**Contract**: Consume `List[Segment]`, output `List[Chunk]`

**Standardize `loc_json` to Range-Only Format**:

**Text Chunker**:
- Chunk segments with overlap
- `loc_json`: `{line_start, line_end}` if line numbers known, else `{char_start, char_end}` (fallback)
- Compute `chunk_hash` from `text + json.dumps(loc, sort_keys=True)`

**Code Chunker**:
- Prefer structural boundaries
- `loc_json`: **Always** `{line_start, line_end}` (required for code)
- Fallback to text chunker if line numbers unavailable

**PDF Chunker** (Step 3):
- `loc_json`: **Always** `{page_start, page_end}` (required for PDF)
- Can chunk across pages (e.g., `{page_start: 1, page_end: 2}`)
- Single page: `{page_start: 1, page_end: 1}`

**Format Rules**:
- PDF: **always** `{page_start, page_end}` (never `{page: N}`)
- Code: **always** `{line_start, line_end}` (never single `line`)
- Text fallback: `{char_start, char_end}` (when line numbers unknown)

#### 2.4 Backward Compatibility

**Strategy**: Keep old behavior working internally while refactoring.

- Old extractors return `(text, metadata)` → wrap in `Segment`
- Old chunkers return `Chunk` objects → convert to new `Chunk` format
- Gradually migrate to new contracts

---

### Step 3 — Real PDF Support (Must Ship)

**Goal**: Implement working PDF extraction and indexing.

#### 3.1 Implement PDF Extractor

**Location**: `rag/extractors/pdf_extractor.py`

**Library**: `pypdf` (add to `requirements.txt`)

**Implementation**:
```python
def extract(self, file_path: Path) -> List[Segment]:
    """Extract text per page, return segments with range format."""
    segments = []
    with open(file_path, 'rb') as f:
        pdf = PdfReader(f)
        for i, page in enumerate(pdf.pages, 1):
            text = page.extract_text()
            # Strip excessive whitespace
            text = re.sub(r'\s+', ' ', text).strip()
            # Skip empty pages
            if text:
                segments.append(Segment(
                    text=text,
                    loc={'page_start': i, 'page_end': i}  # Range format
                ))
    return segments
```

#### 3.2 PDF Chunking

**Strategy**: Preserve page ranges in `loc_json` (range-only format).

- If chunk spans pages: `{page_start: 1, page_end: 2}`
- If chunk is single page: `{page_start: 1, page_end: 1}` (always range format)
- **Never use** `{page: N}` format

#### 3.3 Testing

**Fixture**: `tests/fixtures/sample.pdf`
- Create a simple PDF with known text on page 1
- Example: "This is a test PDF for LocalAI Engine."

**Tests**:
1. **Extractor Test**: `test_pdf_extractor_returns_segments()`
   - Verify segments have `loc['page']`
   - Verify text is extracted correctly

2. **Indexing Test**: `test_pdf_indexing_retrievable()`
   - Index PDF
   - Query with `rag ask`
   - Verify citation includes `p.1-1` (range format)

3. **Citation Test**: `test_pdf_citation_format()`
   - Verify citation is `path:p.X-Y` not `path:lines X-Y`

---

### Step 4 — Conversation Memory + Session Chat

**Goal**: Add conversation continuity as separate retrieval stream.

#### 4.1 Memory Design

**Key Principle**: Memory is a **separate retrieval stream**, not mixed with documents.

**Storage**:
- Sessions and messages in DB (already in schema)
- Embed selected messages (at least user messages)
- **Separate FAISS indexes**:
  - `faiss_docs.index`: Document embeddings (uses `chunks.id` as vector_id)
  - `faiss_memory.index`: Memory embeddings (uses `messages.id` as vector_id)
- Keep indexes completely separate (not mixed)

**Retrieval Flow**:
1. Given query + session_id
2. Embed query
3. Search `faiss_memory.index` for top-k relevant past messages (using `messages.id` as vector_id)
4. Inject into prompt in "Relevant memory" section **before** "Retrieved documents"

**Summarization**:
- Every 10 turns, generate summary of conversation
- Store as assistant "summary" message
- Helps control memory growth

#### 4.2 Implementation (`rag/memory.py`)

**Functions**:
```python
def get_or_create_session(name: str) -> int:
    """Get or create session, return session_id."""

def append_message(session_id: int, role: str, content: str) -> int:
    """Append message, return message_id."""

def embed_message(message_id: int, embeddings_client) -> int:
    """Embed message and store in message_embeddings, return vector_id."""

def retrieve_memory(query_embedding, session_id: int, top_k: int) -> List[RetrievedChunk]:
    """Retrieve relevant past messages for session."""
```

#### 4.3 CLI Commands

**New Commands**:

1. **`rag chat --session <name>`**
   - REPL loop for continuous conversation
   - Exit with `:q`
   - Shows context from previous messages
   - Example:
     ```
     $ rag chat --session myproject
     Session: myproject
     > What is the main function?
     [Answer with memory + documents]
     > How does it work?
     [Answer with memory of previous question + documents]
     > :q
     ```

2. **`rag sessions`**
   - List all sessions
   - Show session name, created_at, message count

3. **`rag session show <name> --last N`**
   - Show last N messages in session
   - Format: `[user/assistant] message content`

**Extended Commands**:

4. **`rag ask "... " --session <name>`**
   - Optional session flag
   - If provided, include memory retrieval
   - Otherwise, no memory (backward compatible)

5. **`rag explain "... " --session <name>`**
   - Show memory hits if session enabled
   - Display which past messages were retrieved

#### 4.4 RAG Pipeline Integration

**Prompt Structure**:
```
Relevant memory from previous conversation:
[Retrieved past messages]

Retrieved documents:
[Retrieved document chunks]

Question: {question}

Answer:
```

**Memory Retrieval**:
- Only if `session_id` provided
- Retrieve top-k messages (default: 3)
- Include in prompt before documents

---

### Step 5 — Operational Commands

**Goal**: Add maintenance and migration tools.

#### 5.1 `rag migrate [--yes]`

**Purpose**: Migrate from v1 database structure to v2.

**Process** (Non-interactive by default):
1. Check for old files:
   - `registry.db`
   - `metadata.db`
   - `faiss.index.mapping.json`
2. If found:
   - **Create timestamped backup**: `~/.rag_data/v1_backup/YYYY-MM-DDTHH-MM-SS/`
   - Copy all old files to backup
   - Migrate files → documents
   - Migrate chunks → chunks (convert loc format to range-only)
   - Migrate vector mappings → embeddings table (with stable IDs)
   - Update manifest with version constants
3. **Never silently drop data**
4. Print summary: `Migrated 123 files, 456 chunks, 456 embeddings`
5. Log backup location: `Backup saved to ~/.rag_data/v1_backup/2024-12-12T10-30-00/`

**Safety**:
- **Non-interactive by default**: Auto-migrate with backups and logs
- Use `--yes` flag to skip any confirmation prompts
- Always create backups first
- Verify migration success
- Log all steps

#### 5.2 `rag rebuild`

**Purpose**: Wipe and reindex everything.

**Process**:
1. Delete all chunks from DB
2. Delete all embeddings from DB
3. Delete `faiss_docs.index`
4. Delete `faiss_memory.index` (if exists)
5. Re-run indexing on all documents
6. Update manifest with current version constants

**Use Case**: After changing chunking config or embedding model.

#### 5.3 `rag reembed`

**Purpose**: Recompute embeddings for existing chunks.

**Process**:
1. Keep chunks stable (don't re-chunk)
2. Delete old embeddings from DB
3. Re-embed all chunks with current model
4. Update `faiss_docs.index` with stable IDs (`chunks.id`)
5. Update manifest (embedding model, dimension)

**Use Case**: After changing embedding model.

**Safety**:
- Verify embedding dimension matches
- Backup old index first

---

## Final Deliverables

### Code Deliverables

1. **Updated `rag/` directory structure**:
   ```
   rag/
   ├── __init__.py
   ├── types.py          # NEW: Segment, Chunk, RetrievedChunk
   ├── db.py             # NEW: Unified database
   ├── memory.py         # NEW: Session and memory management
   ├── config.py         # UPDATED: Config for new DB path
   ├── cli.py            # UPDATED: New commands + backward compatible
   ├── embeddings.py     # (unchanged)
   ├── vector_store.py   # UPDATED: Store mapping in DB
   ├── rag_pipeline.py   # UPDATED: Memory integration
   ├── scanner.py        # (unchanged)
   ├── extractors/
   │   ├── text_extractor.py   # UPDATED: Returns List[Segment]
   │   ├── code_extractor.py   # UPDATED: Returns List[Segment]
   │   └── pdf_extractor.py    # NEW: Real implementation
   └── chunkers/
       ├── text_chunker.py     # UPDATED: Consumes Segment, outputs Chunk
       └── code_chunker.py     # UPDATED: Consumes Segment, outputs Chunk
   ```

2. **Tests**:
   - `tests/test_baseline.py` (Step 0)
   - `tests/test_db.py` (DB schema and CRUD)
   - `tests/test_pdf.py` (PDF extraction and indexing)
   - `tests/test_memory.py` (Memory retrieval)
   - `tests/test_migration.py` (v1 → v2 migration)

3. **Updated `requirements.txt`**:
   - Add `pypdf`

### Documentation Deliverables

1. **Updated README.md**:
   - New commands section
   - Session chat usage
   - PDF support
   - Troubleshooting section (use `rag validate` and `rag explain`)

2. **Updated QUICKSTART.md**:
   - Include new commands
   - Show session chat example
   - Show PDF indexing example

3. **Manual Test Plan** (see below)

---

## Manual Test Plan

### Prerequisites
```bash
# 1. Activate virtual environment
source venv/bin/activate

# 2. Ensure Ollama is running
ollama serve

# 3. Install dependencies
pip install -r requirements.txt
```

### Test 1: Validation and Baseline
```bash
# Check system health
rag validate

# Should show:
# ✓ Ollama reachable
# ✓ Models found
# ✓ Documents index: HNSW with N vectors
# ✓ Memory index: Flat with M vectors (if exists)
# ✓ Database integrity: OK
#   - No orphan chunks
#   - No orphan embeddings
#   - All vector_ids found in FAISS indexes
```

### Test 2: Migration (if upgrading from v1)
```bash
# Migrate from old database (non-interactive, auto-backup)
rag migrate

# Or with explicit confirmation skip
rag migrate --yes

# Verify migration
rag stats
# Should show same file/chunk counts as before

# Check backup was created
ls ~/.rag_data/v1_backup/
# Should show timestamped backup directory
```

### Test 3: Indexing with PDF Support
```bash
# Create test directory with mixed files
mkdir -p ~/rag-test-v2
echo "This is a text file." > ~/rag-test-v2/test.txt
echo "def hello(): return 'world'" > ~/rag-test-v2/test.py
# Add a PDF file (sample.pdf)

# Index everything
rag index ~/rag-test-v2

# Verify PDF was indexed
rag stats
# Should show PDF in file count
```

### Test 4: Querying with Citations
```bash
# Ask question about code
rag ask "What does the hello function do?"

# Should show:
# - Answer
# - Sources with citations: test.py:lines 1-1
# - Scores (raw and display)

# Ask question about PDF (if indexed)
rag ask "What is on page 1 of the PDF?"

# Should show citation: sample.pdf:p.1-1 (range format)
```

### Test 5: Explain Command
```bash
# Debug a query
rag explain "What does the hello function do?"

# Should show:
# - Retrieved chunks with scores
# - Citations
# - Prompt length
```

### Test 6: Session Chat
```bash
# Start chat session
rag chat --session test-session

# In REPL:
> What files are indexed?
[Answer]
> Tell me more about the first file.
[Answer with memory of previous question]
> :q

# List sessions
rag sessions

# Show session history
rag session show test-session --last 5
```

### Test 7: Session with Ask
```bash
# Ask with session context
rag ask "What was the first file?" --session test-session

# Should include memory from previous chat
```

### Test 8: Operational Commands
```bash
# Rebuild index
rag rebuild

# Re-embed with new model (if changed)
rag reembed

# Validate after changes
rag validate
```

### Test 9: Backward Compatibility
```bash
# Verify old commands still work
rag ingest ~/rag-test-v2
rag index ~/rag-test-v2
rag ask "test question"
rag stats

# All should work without errors
```

### Test 10: Integrity Checks
```bash
# Run validate to check integrity
rag validate

# Should show:
# ✓ Database integrity: OK
#   - No orphan chunks (doc_version missing)
#   - No orphan embeddings (chunk missing)
#   - All vector_ids found in FAISS indexes (sanity check)
```

### Test 11: .ragignore Support
```bash
# Create test directory with .ragignore
mkdir -p ~/rag-test-ignore
echo "*.log" > ~/rag-test-ignore/.ragignore
echo "test content" > ~/rag-test-ignore/test.txt
echo "log content" > ~/rag-test-ignore/app.log

# Index (should ignore .log files)
rag index ~/rag-test-ignore

# Verify only test.txt was indexed
rag stats
# Should show 1 file (test.txt), not app.log
```

---

## Current System State (v1)

### ✅ Working Features

1. **File Indexing**
   - Recursive directory scanning
   - Multiple file type support (`.txt`, `.md`, `.py`, `.js`, `.ts`, `.json`, `.yaml`)
   - Ignore pattern filtering
   - Incremental indexing (only changed files)

2. **Smart Chunking**
   - Text-aware chunking with sentence boundaries
   - Code-aware chunking with function/class boundaries
   - Overlap support for context preservation
   - Line number tracking for citations

3. **Vector Search**
   - FAISS-based similarity search
   - HNSW index for performance
   - Cosine similarity (using inner product)
   - Top-k retrieval

4. **Query System**
   - Natural language question answering
   - Context-aware responses
   - Source citations with file paths and line numbers
   - Similarity scores for each result

5. **CLI Interface**
   - Complete command-line interface
   - Dry-run support
   - Statistics display
   - Config file support

### ⚠️ Known Issues (To Fix in V2)

1. **Scoring Range**: Assumes 0-1, but cosine can be -1 to 1
2. **Citation Format**: Inconsistent formats
3. **Database Fragmentation**: Multiple DB files + JSON mapping
4. **No Conversation Memory**: Each query is independent
5. **PDF Support**: Stub only, not implemented
6. **No Integrity Checks**: Potential for orphaned data
7. **No Atomic Operations**: Risk of corruption

---

## Dependencies

### Current
- **typer**: CLI framework
- **pydantic**: Configuration management
- **faiss-cpu**: Vector similarity search
- **numpy**: Numerical operations
- **requests**: HTTP client for Ollama API
- **pyyaml**: YAML configuration parsing

### To Add for V2
- **pypdf**: PDF text extraction

---

## Configuration

### Current Configuration (`config.yaml`)

```yaml
ollama:
  base_url: "http://localhost:11434"
  embedding_model: "nomic-embed-text"
  llm_model: "llama3"
  timeout: 300

chunking:
  text_chunk_size: 900
  text_overlap: 150
  code_chunk_size: 800
  code_overlap: 100

indexing:
  top_k: 5
  batch_size: 32
  use_hnsw: true
  hnsw_m: 32
  hnsw_ef_construction: 200
```

---

## Project Statistics

- **Total Files**: ~15 core Python modules
- **Lines of Code**: ~2000+ lines (will grow with v2)
- **Test Coverage**: Basic unit tests (will expand)
- **Documentation**: Comprehensive README, QUICKSTART, implementation docs
- **Dependencies**: 7 packages (will be 8 with pypdf)
- **Data Storage**: SQLite + FAISS + JSON → Unified SQLite + FAISS (v2)

---

---

## Key Implementation Details (Cursor Addendum)

### Database Schema Corrections

1. **Embeddings Uniqueness**: `UNIQUE(chunk_id, model, index_name)`
   - `index_name` strictly `"documents"` for doc chunks
   - Keep `message_embeddings` separate (different table)

2. **Stable Vector IDs**: Use `faiss.IndexIDMap2(base_index)`
   - Call `add_with_ids(vectors, ids)` where `ids` are stable DB IDs
   - Documents: use `chunks.id` as vector_id
   - Memory: use `messages.id` as vector_id
   - Do not rely on implicit sequential FAISS IDs

3. **Separate FAISS Indexes**:
   - `faiss_docs.index`: Document embeddings
   - `faiss_memory.index`: Memory embeddings
   - Keep completely separate (not mixed)

### Location Format Standardization

**Range-Only Format** (no single values):
- **PDF**: Always `{page_start, page_end}` (never `{page: N}`)
- **Code**: Always `{line_start, line_end}` (never single `line`)
- **Text fallback**: `{char_start, char_end}` (when line numbers unknown)

### Version Management

**Constants** (`rag/constants.py` or `rag/__init__.py`):
```python
EXTRACTOR_VERSION = "1.0"
CHUNKER_VERSION = "1.0"
```
- Store in `doc_versions` table
- Store in manifest
- Bump when behavior changes

### Migration Behavior

- **Non-interactive by default**: Auto-migrate with backups and logs
- Use `--yes` flag to skip confirmation prompts
- Always create timestamped backups: `~/.rag_data/v1_backup/YYYY-MM-DDTHH-MM-SS/`
- Never silently drop data

### Ignore Patterns

- **`.ragignore` support**: Read `.ragignore` files (like `.gitignore`)
- **Strong default ignores**: `.git/`, `node_modules/`, `.venv/`, `venv/`, `dist/`, `build/`, `__pycache__/`, `.DS_Store`
- Merge with config ignore patterns

### Integrity Checks

**SQL Checks in `rag validate`**:
1. Orphan chunks: `SELECT COUNT(*) FROM chunks WHERE doc_version_id NOT IN (SELECT id FROM doc_versions)`
2. Orphan embeddings: `SELECT COUNT(*) FROM embeddings WHERE chunk_id NOT IN (SELECT id FROM chunks)`
3. Missing vectors: For each `vector_id` in DB, verify it exists in FAISS index (sanity check)

---

**Last Updated**: December 12, 2024  
**Project Status**: ✅ v1 Fully Functional | 🚧 v2 Refactoring Planned  
**Next Steps**: Begin Step 0 (Safety Net) - Add `rag validate` and `rag explain` commands
