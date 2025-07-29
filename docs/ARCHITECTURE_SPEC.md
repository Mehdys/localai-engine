# LocalAI Engine - Architecture Specification

**Version**: 1.5  
**Date**: December 2024  
**Architecture Style**: Clean Architecture / Ports & Adapters (Hexagonal Architecture)

---

## 1. Vision & Scope (V1.5)

### Core Mission
LocalAI Engine is a **local-first RAG (Retrieval-Augmented Generation) system** for macOS that enables users to:
- Index local files and documents (text, code, PDFs)
- Query indexed content using natural language
- Get answers with source citations
- Work entirely offline using Ollama for embeddings and LLM inference

### V1.5 Feature Set

#### ✅ Must Have
1. **Incremental Indexing**
   - SHA256-based change detection
   - Only re-index changed files
   - Chunk deduplication

2. **Multi-Format Support**
   - Text files (`.txt`, `.md`)
   - Code files (`.py`, `.js`, `.ts`, `.json`, `.yaml`, `.yml`)
   - PDF files with OCR fallback

3. **Smart Chunking**
   - Text-aware: sentence/paragraph boundaries
   - Code-aware: function/class boundaries
   - Configurable overlap

4. **Vector Search**
   - FAISS-based similarity search
   - HNSW or Flat index
   - Cosine similarity scoring (0-1 range)

5. **Query & Answer**
   - Natural language questions
   - Context-aware answers
   - Source citations with file paths and line numbers

6. **CLI Interface**
   - `ingest`: Scan and register files
   - `index`: Index files (extract, chunk, embed, store)
   - `ask`: Query with natural language
   - `stats`: Show index statistics
   - `repl`: Interactive REPL mode with short-term memory

7. **Workspace Support**
   - Per-workspace storage isolation
   - Workspace slug-based directory structure
   - Default workspace fallback

8. **REPL Memory**
   - In-memory conversation history (session-scoped)
   - Short-term context for follow-up questions
   - Not persisted across sessions

#### ❌ Out of Scope (V1.5)
- Web UI / API server
- Multi-user / authentication
- SaaS / cloud features
- Long-term conversation persistence
- Multi-workspace switching in single session
- Real-time file watching

---

## 2. Architectural Style and Design Principles

### Architecture Pattern: Clean Architecture / Ports & Adapters

```
┌─────────────────────────────────────────────────────────┐
│                    Application Layer                     │
│  (CLI Commands, REPL, Use Cases)                        │
└──────────────────────┬──────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────┐
│                    Domain Layer                          │
│  (Models, Port Interfaces, Business Logic)              │
│  - Document, Chunk, SearchResult, Answer                │
│  - FileStore, Extractor, Chunker, Embedder, etc.        │
└──────────────────────┬──────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────┐
│                Infrastructure Layer                      │
│  (Adapters: FAISS, SQLite, Ollama, File System)         │
└─────────────────────────────────────────────────────────┘
```

### Core Principles

1. **Dependency Inversion**
   - Core domain does NOT import adapters
   - Core defines interfaces (ports)
   - Adapters implement interfaces
   - Application layer wires dependencies

2. **Separation of Concerns**
   - **Domain**: Pure business logic, no I/O
   - **Application**: Use cases, orchestration
   - **Infrastructure**: External systems, persistence

3. **Testability**
   - Core domain is unit-testable without mocks
   - Ports enable easy mocking
   - Adapters can be integration-tested

4. **Workspace Isolation**
   - Each workspace has isolated storage
   - No cross-workspace data leakage
   - Workspace slug determines storage path

### Import Rules (STRICT)

```
✅ ALLOWED:
- Domain → Nothing (pure)
- Application → Domain only
- Infrastructure → Domain only
- CLI → Application + Infrastructure

❌ FORBIDDEN:
- Domain → Application
- Domain → Infrastructure
- Domain → CLI
- Application → Infrastructure (use dependency injection)
```

---

## 3. Final Repo Layout

```
localai-engine/
├── docs/
│   └── ARCHITECTURE_SPEC.md          # This file
│
├── rag/
│   ├── __init__.py
│   │
│   ├── domain/                       # CORE: Pure business logic
│   │   ├── __init__.py
│   │   ├── models.py                 # Document, Chunk, SearchResult, Answer
│   │   └── ports.py                   # All port interfaces
│   │
│   ├── application/                   # APPLICATION: Use cases
│   │   ├── __init__.py
│   │   ├── services.py                # IngestService, IndexService, QueryService, StatsService
│   │   └── memory.py                  # REPL conversation memory (in-memory)
│   │
│   ├── infrastructure/                # INFRASTRUCTURE: Adapters
│   │   ├── __init__.py
│   │   ├── storage/
│   │   │   ├── __init__.py
│   │   │   ├── file_store.py          # FileStore adapter (file system)
│   │   │   ├── registry_store.py      # Registry adapter (SQLite)
│   │   │   └── workspace.py            # Workspace path management
│   │   ├── extractors/
│   │   │   ├── __init__.py
│   │   │   ├── text_extractor.py      # TextExtractor adapter
│   │   │   ├── code_extractor.py      # CodeExtractor adapter
│   │   │   └── pdf_extractor.py       # PDFExtractor adapter (with OCR)
│   │   ├── chunkers/
│   │   │   ├── __init__.py
│   │   │   ├── text_chunker.py        # TextChunker adapter
│   │   │   └── code_chunker.py        # CodeChunker adapter
│   │   ├── embeddings/
│   │   │   ├── __init__.py
│   │   │   └── ollama_embedder.py     # Embedder adapter (Ollama)
│   │   ├── vector/
│   │   │   ├── __init__.py
│   │   │   └── faiss_index.py         # VectorIndex adapter (FAISS)
│   │   └── llm/
│   │       ├── __init__.py
│   │       └── ollama_llm.py          # LLM adapter (Ollama)
│   │
│   ├── cli/                           # CLI: User interface
│   │   ├── __init__.py
│   │   ├── commands.py                # CLI command handlers
│   │   ├── repl.py                    # REPL mode
│   │   └── config.py                  # Configuration loading
│   │
│   └── config.py                      # Configuration models (Pydantic)
│
├── tests/
│   ├── unit/
│   │   ├── domain/                    # Domain model tests
│   │   └── application/               # Service tests (with mocks)
│   ├── integration/
│   │   └── infrastructure/            # Adapter integration tests
│   └── fixtures/                      # Test data
│
├── setup.py
├── requirements.txt
├── README.md
└── config.example.yaml
```

### Directory Responsibilities

- **`domain/`**: Pure business logic, no external dependencies
  - Models: Value objects and entities
  - Ports: Interface definitions (ABC/protocols)

- **`application/`**: Use cases and orchestration
  - Services: Business workflows
  - Memory: Session-scoped conversation history

- **`infrastructure/`**: External system adapters
  - Storage: File system, SQLite, workspace management
  - Extractors: File content extraction
  - Chunkers: Text/code chunking strategies
  - Embeddings: Ollama embedding API
  - Vector: FAISS index management
  - LLM: Ollama LLM API

- **`cli/`**: Command-line interface
  - Commands: Typer-based CLI handlers
  - REPL: Interactive mode
  - Config: Configuration loading and validation

---

## 4. Domain Models

### Document

Represents a file that can be indexed.

```python
@dataclass(frozen=True)
class Document:
    """A document/file that can be indexed."""
    path: Path                    # Absolute file path
    file_type: str                # "text", "code", "pdf"
    content_hash: str             # SHA256 hash of file content
    size_bytes: int               # File size
    modified_at: float            # Unix timestamp
    line_count: Optional[int]     # For text/code files
```

### Chunk

Represents a chunk of text extracted from a document.

```python
@dataclass(frozen=True)
class Chunk:
    """A chunk of text from a document."""
    chunk_id: str                 # SHA1 hash of (path:start:end)
    document_path: Path           # Source document
    text: str                     # Chunk text content
    start_line: int               # Starting line number (1-indexed)
    end_line: int                 # Ending line number (1-indexed)
    start_offset: int             # Character offset in file
    end_offset: int               # Character offset in file
    chunk_hash: str               # SHA1 hash of text (for deduplication)
```

### SearchResult

Represents a search result from vector similarity search.

```python
@dataclass(frozen=True)
class SearchResult:
    """A search result with similarity score."""
    chunk: Chunk                  # The matched chunk
    score: float                  # Similarity score (0.0 to 1.0)
    vector_id: int                # FAISS vector ID
```

### Answer

Represents a query answer with sources.

```python
@dataclass(frozen=True)
class Answer:
    """An answer to a query with source citations."""
    text: str                     # Answer text from LLM
    sources: List[SearchResult]   # Source chunks used
    query: str                    # Original query
```

### Conversation Turn (for REPL)

```python
@dataclass(frozen=True)
class ConversationTurn:
    """A single turn in a conversation."""
    query: str                    # User question
    answer: Answer                # System answer
    timestamp: float              # Unix timestamp
```

---

## 5. Port Interfaces

All ports are defined in `rag/domain/ports.py` using `typing.Protocol` or `abc.ABC`.

### FileStore

Interface for file system operations.

```python
class FileStore(Protocol):
    """Interface for file system operations."""
    
    def scan_directory(
        self,
        root: Path,
        text_extensions: List[str],
        code_extensions: List[str],
        ignore_patterns: List[str],
    ) -> List[Document]:
        """Scan directory and return indexable documents."""
        ...
    
    def read_file(self, path: Path) -> bytes:
        """Read file content as bytes."""
        ...
    
    def compute_hash(self, path: Path) -> str:
        """Compute SHA256 hash of file content."""
        ...
    
    def get_file_info(self, path: Path) -> Dict[str, Any]:
        """Get file metadata (size, mtime, etc.)."""
        ...
```

### Extractor

Interface for extracting text from documents.

```python
class Extractor(Protocol):
    """Interface for extracting text from documents."""
    
    def extract(self, document: Document) -> Tuple[str, Dict[str, Any]]:
        """
        Extract text from document.
        
        Returns:
            Tuple of (text_content, metadata_dict)
        """
        ...
    
    def can_extract(self, document: Document) -> bool:
        """Check if this extractor can handle the document type."""
        ...
```

### Chunker

Interface for chunking text into smaller pieces.

```python
class Chunker(Protocol):
    """Interface for chunking text into chunks."""
    
    def chunk(
        self,
        text: str,
        document_path: Path,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> List[Chunk]:
        """
        Chunk text into smaller pieces.
        
        Args:
            text: Text to chunk
            document_path: Source document path
            metadata: Optional metadata (e.g., code structure)
        
        Returns:
            List of Chunk objects
        """
        ...
```

### Embedder

Interface for generating embeddings.

```python
class Embedder(Protocol):
    """Interface for generating embeddings."""
    
    def embed(self, text: str) -> np.ndarray:
        """Generate embedding for a single text."""
        ...
    
    def embed_batch(self, texts: List[str]) -> np.ndarray:
        """
        Generate embeddings for a batch of texts.
        
        Returns:
            Array of shape (n, dimension) with normalized vectors
        """
        ...
    
    def get_dimension(self) -> int:
        """Get embedding dimension."""
        ...
```

### VectorIndex

Interface for vector similarity search.

```python
class VectorIndex(Protocol):
    """Interface for vector similarity search."""
    
    def add_vectors(
        self,
        vectors: np.ndarray,
        chunk_ids: List[str],
    ) -> None:
        """
        Add vectors to index.
        
        Args:
            vectors: Normalized vectors (n, dim)
            chunk_ids: Corresponding chunk IDs
        """
        ...
    
    def search(
        self,
        query_vector: np.ndarray,
        top_k: int,
    ) -> List[Tuple[int, float]]:
        """
        Search for similar vectors.
        
        Args:
            query_vector: Normalized query vector (dim,)
            top_k: Number of results
        
        Returns:
            List of (vector_id, score) tuples, sorted by score descending
            Score range: 0.0 (dissimilar) to 1.0 (identical)
        """
        ...
    
    def get_chunk_id(self, vector_id: int) -> Optional[str]:
        """Get chunk ID for a vector ID."""
        ...
    
    def save(self) -> None:
        """Persist index to disk."""
        ...
    
    def load(self) -> None:
        """Load index from disk."""
        ...
    
    def get_stats(self) -> Dict[str, Any]:
        """Get index statistics."""
        ...
```

### Registry

Interface for tracking indexed files and chunks.

```python
class Registry(Protocol):
    """Interface for tracking indexed files and chunks."""
    
    def register_document(self, document: Document) -> None:
        """Register a document."""
        ...
    
    def get_changed_documents(
        self,
        documents: List[Document],
    ) -> List[Document]:
        """Return documents that have changed since last index."""
        ...
    
    def register_chunk(self, chunk: Chunk) -> None:
        """Register a chunk."""
        ...
    
    def chunk_exists(self, chunk_hash: str) -> bool:
        """Check if chunk with given hash exists."""
        ...
    
    def delete_document_chunks(self, document_path: Path) -> None:
        """Delete all chunks for a document (when re-indexing)."""
        ...
    
    def get_chunk_metadata(self, chunk_id: str) -> Optional[Dict[str, Any]]:
        """Get chunk metadata by chunk ID."""
        ...
    
    def get_stats(self) -> Dict[str, Any]:
        """Get registry statistics."""
        ...
```

### LLM

Interface for language model inference.

```python
class LLM(Protocol):
    """Interface for language model inference."""
    
    def generate(
        self,
        prompt: str,
        context: Optional[str] = None,
    ) -> str:
        """
        Generate text from prompt.
        
        Args:
            prompt: User prompt/question
            context: Optional context (e.g., retrieved chunks)
        
        Returns:
            Generated text
        """
        ...
```

---

## 6. Services / Use Cases

All services are in `rag/application/services.py`.

### IngestService

**Responsibility**: Scan directories and identify indexable files.

```python
class IngestService:
    """Service for ingesting files."""
    
    def __init__(
        self,
        file_store: FileStore,
        registry: Registry,
    ):
        self.file_store = file_store
        self.registry = registry
    
    def ingest(
        self,
        roots: List[Path],
        text_extensions: List[str],
        code_extensions: List[str],
        ignore_patterns: List[str],
        dry_run: bool = False,
    ) -> List[Document]:
        """
        Scan directories and register documents.
        
        Returns:
            List of discovered documents
        """
        # 1. Scan all root directories
        # 2. Filter by extensions and ignore patterns
        # 3. Register documents in registry (if not dry_run)
        # 4. Return list of documents
```

### IndexService

**Responsibility**: Index documents (extract, chunk, embed, store).

```python
class IndexService:
    """Service for indexing documents."""
    
    def __init__(
        self,
        extractors: List[Extractor],
        chunkers: Dict[str, Chunker],  # keyed by file_type
        embedder: Embedder,
        vector_index: VectorIndex,
        registry: Registry,
    ):
        self.extractors = extractors
        self.chunkers = chunkers
        self.embedder = embedder
        self.vector_index = vector_index
        self.registry = registry
    
    def index_documents(
        self,
        documents: List[Document],
        batch_size: int = 32,
    ) -> Dict[str, int]:
        """
        Index documents.
        
        Returns:
            Dict with 'indexed', 'chunks_created', 'chunks_skipped'
        """
        # 1. Get changed documents from registry
        # 2. For each document:
        #    a. Find appropriate extractor
        #    b. Extract text + metadata
        #    c. Find appropriate chunker
        #    d. Chunk text
        #    e. Delete old chunks for document
        #    f. Batch chunks for embedding
        #    g. Generate embeddings (batch)
        #    h. Add to vector index
        #    i. Register chunks in registry
        # 3. Save vector index
        # 4. Return statistics
```

### QueryService

**Responsibility**: Answer questions using RAG pipeline.

```python
class QueryService:
    """Service for querying indexed content."""
    
    def __init__(
        self,
        embedder: Embedder,
        vector_index: VectorIndex,
        registry: Registry,
        llm: LLM,
    ):
        self.embedder = embedder
        self.vector_index = vector_index
        self.registry = registry
        self.llm = llm
    
    def query(
        self,
        question: str,
        top_k: int = 5,
    ) -> Answer:
        """
        Answer a question using RAG.
        
        Returns:
            Answer with text and source citations
        """
        # 1. Embed question
        # 2. Search vector index (top_k)
        # 3. Get chunk metadata from registry
        # 4. Build context from chunks
        # 5. Generate answer using LLM
        # 6. Return Answer with sources
```

### StatsService

**Responsibility**: Provide index statistics.

```python
class StatsService:
    """Service for index statistics."""
    
    def __init__(
        self,
        registry: Registry,
        vector_index: VectorIndex,
    ):
        self.registry = registry
        self.vector_index = vector_index
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get comprehensive statistics.
        
        Returns:
            Dict with file_count, chunk_count, vector_count, etc.
        """
        # 1. Get registry stats
        # 2. Get vector index stats
        # 3. Combine and return
```

### ConversationMemory (for REPL)

**Responsibility**: Manage in-memory conversation history.

```python
class ConversationMemory:
    """In-memory conversation history for REPL."""
    
    def __init__(self, max_turns: int = 10):
        self.turns: List[ConversationTurn] = []
        self.max_turns = max_turns
    
    def add_turn(self, query: str, answer: Answer) -> None:
        """Add a conversation turn."""
        # Add turn, trim if exceeds max_turns
    
    def get_context(self) -> str:
        """Get conversation context for LLM prompt."""
        # Format recent turns as context
    
    def clear(self) -> None:
        """Clear conversation history."""
        self.turns.clear()
```

---

## 7. Persistence Model (Workspace Storage Layout)

### Workspace Structure

```
~/.rag_data/
└── workspaces/
    └── <workspace_slug>/
        ├── faiss.index                    # FAISS vector index
        ├── faiss.index.mapping.json        # Vector ID → chunk ID mapping
        ├── registry.db                     # SQLite: documents + chunks
        └── config.yaml                     # Workspace-specific config (optional)
```

### Default Workspace

- **Slug**: `default`
- **Path**: `~/.rag_data/workspaces/default/`
- Used when no workspace is specified

### Workspace Slug Rules

- **Format**: Lowercase alphanumeric + hyphens/underscores
- **Validation**: `^[a-z0-9_-]+$`
- **Max Length**: 50 characters
- **Reserved**: `default`, `shared` (reserved for future)

### Registry Database Schema (SQLite)

```sql
-- Documents table
CREATE TABLE documents (
    path TEXT PRIMARY KEY,
    file_type TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    modified_at REAL NOT NULL,
    line_count INTEGER,
    indexed_at REAL,
    created_at REAL NOT NULL
);

-- Chunks table
CREATE TABLE chunks (
    chunk_id TEXT PRIMARY KEY,
    document_path TEXT NOT NULL,
    chunk_hash TEXT NOT NULL,
    chunk_text TEXT NOT NULL,
    start_line INTEGER,
    end_line INTEGER,
    start_offset INTEGER,
    end_offset INTEGER,
    created_at REAL NOT NULL,
    FOREIGN KEY (document_path) REFERENCES documents(path)
);

-- Indexes
CREATE INDEX idx_chunks_document ON chunks(document_path);
CREATE INDEX idx_chunks_hash ON chunks(chunk_hash);
CREATE INDEX idx_documents_hash ON documents(content_hash);
```

### Migration Strategy

**Phase 1**: Support both old and new layouts
- Check for `~/.rag_data/faiss.index` (old)
- If exists, migrate to `~/.rag_data/workspaces/default/`
- Create workspace structure

**Phase 2**: Remove old layout support (after migration period)

---

## 8. PDF OCR Strategy

### Extraction Flow

```
PDF Document
    ↓
1. Try text extraction (PyPDF2/pdfplumber)
    ↓ (if text found)
    Success → Return text
    ↓ (if no text or minimal text)
2. Fallback to OCR (Tesseract/pytesseract)
    ↓
    Extract text from images
    ↓
    Return OCR text
```

### Implementation Details

**Extractor Selection**:
1. Check if PDF has extractable text (metadata check)
2. If text extraction yields < 10% of page count → use OCR
3. Otherwise use text extraction

**OCR Requirements**:
- **Library**: `pytesseract` (Python wrapper for Tesseract)
- **Dependency**: Tesseract OCR must be installed (`brew install tesseract` on macOS)
- **Fallback**: If OCR fails, return extracted text (even if minimal)

**Error Handling**:
- If OCR not available → log warning, return extracted text
- If OCR fails → log error, return extracted text
- Never fail completely → always return something

### Code Structure

```python
# rag/infrastructure/extractors/pdf_extractor.py

class PDFExtractor:
    """PDF extractor with OCR fallback."""
    
    def extract(self, document: Document) -> Tuple[str, Dict[str, Any]]:
        # 1. Try text extraction
        text = self._extract_text(document.path)
        
        # 2. Check if text is sufficient
        if self._is_text_sufficient(text, document.path):
            return text, {"method": "text_extraction"}
        
        # 3. Fallback to OCR
        ocr_text = self._extract_with_ocr(document.path)
        return ocr_text, {"method": "ocr", "fallback": True}
```

---

## 9. CLI Commands

### Command Structure

All commands in `rag/cli/commands.py` using Typer.

### `rag ingest`

**Purpose**: Scan directories and identify indexable files.

```bash
rag ingest <roots...> [OPTIONS]
```

**Options**:
- `--workspace TEXT`: Workspace slug (default: "default")
- `--config PATH`: Config file path
- `--dry-run`: Preview without registering

**Behavior**:
1. Load workspace config
2. Scan directories using FileStore
3. Register documents in Registry (unless dry-run)
4. Print summary

### `rag index`

**Purpose**: Index documents (extract, chunk, embed, store).

```bash
rag index <roots...> [OPTIONS]
```

**Options**:
- `--workspace TEXT`: Workspace slug
- `--config PATH`: Config file path

**Behavior**:
1. Load workspace config
2. Get changed documents from Registry
3. Run IndexService
4. Print progress and statistics

### `rag ask`

**Purpose**: Answer a question using RAG.

```bash
rag ask <question> [OPTIONS]
```

**Options**:
- `--workspace TEXT`: Workspace slug
- `--config PATH`: Config file path
- `--top-k INT`: Number of chunks to retrieve (default: 5)

**Behavior**:
1. Load workspace config
2. Run QueryService
3. Print answer and sources

### `rag stats`

**Purpose**: Show index statistics.

```bash
rag stats [OPTIONS]
```

**Options**:
- `--workspace TEXT`: Workspace slug
- `--config PATH`: Config file path

**Behavior**:
1. Load workspace config
2. Run StatsService
3. Print formatted statistics

### `rag repl`

**Purpose**: Interactive REPL mode with conversation memory.

```bash
rag repl [OPTIONS]
```

**Options**:
- `--workspace TEXT`: Workspace slug
- `--config PATH`: Config file path
- `--max-turns INT`: Max conversation turns to remember (default: 10)

**Behavior**:
1. Load workspace config
2. Initialize ConversationMemory
3. Enter interactive loop:
   - Prompt: `rag> `
   - Read user input
   - Run QueryService with conversation context
   - Add turn to memory
   - Print answer
   - Repeat until `exit` or `quit`
4. Commands:
   - `clear`: Clear conversation memory
   - `stats`: Show statistics
   - `exit`/`quit`: Exit REPL

### REPL Memory Approach

**Scope**: Session-only (in-memory)
- Memory lives only during REPL session
- Cleared when REPL exits
- Not persisted to disk

**Implementation**:
- ConversationMemory holds last N turns (default: 10)
- Each QueryService call includes conversation context in prompt
- Context format:
  ```
  Previous conversation:
  Q: <previous question>
  A: <previous answer>
  
  [Repeat for last N turns]
  
  Current question: <user question>
  ```

**LLM Prompt Enhancement**:
```python
def query_with_context(
    self,
    question: str,
    conversation_context: Optional[str] = None,
    top_k: int = 5,
) -> Answer:
    # Build prompt with context
    prompt = f"""
    {conversation_context or ""}
    
    Context from indexed documents:
    {retrieved_chunks}
    
    Question: {question}
    
    Answer:
    """
    # ... rest of query logic
```

---

## 10. Observability (Logging + Errors)

### Logging Strategy

**Library**: Python `logging` module (standard library)

**Log Levels**:
- **DEBUG**: Detailed diagnostic information (chunking, embedding details)
- **INFO**: General informational messages (files indexed, queries processed)
- **WARNING**: Warning messages (OCR fallback, missing files)
- **ERROR**: Error messages (extraction failures, API errors)
- **CRITICAL**: Critical errors (corrupt index, database errors)

**Log Format**:
```
[YYYY-MM-DD HH:MM:SS] [LEVEL] [MODULE] Message
```

**Example**:
```
[2024-12-12 14:30:15] [INFO] [rag.application.services.IndexService] Indexing 3 documents
[2024-12-12 14:30:16] [WARNING] [rag.infrastructure.extractors.pdf_extractor] OCR fallback used for document.pdf
[2024-12-12 14:30:20] [ERROR] [rag.infrastructure.llm.ollama_llm] Failed to connect to Ollama: Connection refused
```

### Error Handling

**Error Types**:

1. **Domain Errors** (in `rag/domain/`):
   - `InvalidDocumentError`: Document validation failed
   - `InvalidChunkError`: Chunk validation failed

2. **Application Errors** (in `rag/application/`):
   - `IndexingError`: Indexing operation failed
   - `QueryError`: Query operation failed

3. **Infrastructure Errors** (in `rag/infrastructure/`):
   - `ExtractionError`: File extraction failed
   - `EmbeddingError`: Embedding generation failed
   - `VectorIndexError`: Vector index operation failed
   - `RegistryError`: Registry operation failed

**Error Handling Pattern**:

```python
# In services
try:
    result = self.vector_index.search(...)
except VectorIndexError as e:
    logger.error(f"Vector search failed: {e}")
    raise QueryError(f"Failed to search index: {e}") from e
```

**CLI Error Display**:
- Errors logged to stderr
- User-friendly messages to stdout
- Exit codes: 0 (success), 1 (error)

### Logging Configuration

**Default**: Log to stderr with INFO level

**Configurable via**:
- Environment variable: `RAG_LOG_LEVEL=DEBUG`
- Config file: `logging.level: DEBUG`

**File Logging** (optional):
- Config: `logging.file: ~/.rag_data/rag.log`
- Rotate logs (10MB, keep 5 files)

---

## 11. Step-by-Step Refactor Plan

### Phase 0: Preparation (No Breaking Changes)

**Goal**: Set up new structure without changing existing code.

1. **Create new directory structure**
   - Create `rag/domain/`, `rag/application/`, `rag/infrastructure/`, `rag/cli/`
   - Add `__init__.py` files

2. **Extract domain models**
   - Create `rag/domain/models.py`
   - Define `Document`, `Chunk`, `SearchResult`, `Answer` as dataclasses
   - Keep existing models in place (for now)

3. **Define port interfaces**
   - Create `rag/domain/ports.py`
   - Define all Protocol interfaces
   - No implementations yet

4. **Add workspace support (backward compatible)**
   - Create `rag/infrastructure/storage/workspace.py`
   - Add workspace detection (default to "default")
   - Support old `~/.rag_data/` layout (migration helper)

**Validation**: All existing tests pass, no CLI changes

---

### Phase 1: Extract Domain Layer

**Goal**: Move business logic to domain, define interfaces.

1. **Move models to domain**
   - Copy models from existing code to `rag/domain/models.py`
   - Update imports in tests only
   - Keep old models as aliases (deprecation)

2. **Create port interfaces**
   - Define all ports in `rag/domain/ports.py`
   - Use `typing.Protocol` for structural subtyping

3. **Extract pure business logic**
   - Move chunk ID generation to domain
   - Move hash computation to domain
   - No I/O in domain

**Validation**: Domain tests pass, existing functionality unchanged

---

### Phase 2: Create Adapters (Infrastructure)

**Goal**: Implement port interfaces as adapters.

1. **FileStore adapter**
   - Create `rag/infrastructure/storage/file_store.py`
   - Implement `FileStore` protocol
   - Wrap existing `FileScanner` logic

2. **Extractor adapters**
   - Move extractors to `rag/infrastructure/extractors/`
   - Make them implement `Extractor` protocol
   - Keep existing implementations

3. **Chunker adapters**
   - Move chunkers to `rag/infrastructure/chunkers/`
   - Make them implement `Chunker` protocol

4. **Embedder adapter**
   - Create `rag/infrastructure/embeddings/ollama_embedder.py`
   - Wrap existing `OllamaEmbeddings` as `Embedder` adapter

5. **VectorIndex adapter**
   - Create `rag/infrastructure/vector/faiss_index.py`
   - Wrap existing `VectorStore` as `VectorIndex` adapter

6. **Registry adapter**
   - Create `rag/infrastructure/storage/registry_store.py`
   - Wrap existing `FileRegistry` as `Registry` adapter

7. **LLM adapter**
   - Create `rag/infrastructure/llm/ollama_llm.py`
   - Extract LLM logic from `RAGPipeline`

**Validation**: Adapter tests pass, existing CLI still works

---

### Phase 3: Create Services (Application)

**Goal**: Implement use cases as services.

1. **IngestService**
   - Create `rag/application/services.py`
   - Implement `IngestService` using ports
   - Wire adapters via dependency injection

2. **IndexService**
   - Implement `IndexService`
   - Use extractors, chunkers, embedder, vector_index, registry

3. **QueryService**
   - Implement `QueryService`
   - Use embedder, vector_index, registry, llm

4. **StatsService**
   - Implement `StatsService`
   - Use registry, vector_index

5. **ConversationMemory**
   - Create `rag/application/memory.py`
   - Implement in-memory conversation history

**Validation**: Service tests pass (with mocks), existing CLI works

---

### Phase 4: Refactor CLI

**Goal**: Update CLI to use services.

1. **Update CLI commands**
   - Modify `rag/cli/commands.py`
   - Wire services with adapters
   - Keep same CLI interface (no breaking changes)

2. **Add REPL mode**
   - Create `rag/cli/repl.py`
   - Implement interactive loop
   - Use ConversationMemory

3. **Add workspace support to CLI**
   - Add `--workspace` option to all commands
   - Load workspace-specific config

**Validation**: All CLI commands work, backward compatible

---

### Phase 5: Cleanup & Migration

**Goal**: Remove old code, complete migration.

1. **Migrate old data**
   - Create migration script
   - Move `~/.rag_data/*` to `~/.rag_data/workspaces/default/`
   - Update users via documentation

2. **Remove deprecated code**
   - Remove old model definitions
   - Remove old service classes
   - Update all imports

3. **Update tests**
   - Move tests to new structure
   - Update test imports
   - Add integration tests

4. **Update documentation**
   - Update README with new structure
   - Document workspace concept
   - Update examples

**Validation**: All tests pass, documentation updated, migration complete

---

### Migration Safety Checklist

Before each phase:
- [ ] All existing tests pass
- [ ] CLI commands work identically
- [ ] No breaking changes to public API
- [ ] Backward compatibility maintained

After each phase:
- [ ] Run full test suite
- [ ] Test CLI commands manually
- [ ] Verify data integrity
- [ ] Check import structure (no domain → infrastructure)

---

## 12. Cursor Rules (Strict Architectural Constraints)

### Import Rules (ENFORCED)

```python
# ✅ ALLOWED IMPORTS

# Domain (pure, no imports)
# Nothing imports domain

# Application
from rag.domain.models import Document, Chunk
from rag.domain.ports import FileStore, Extractor

# Infrastructure
from rag.domain.models import Document, Chunk
from rag.domain.ports import FileStore, Extractor

# CLI
from rag.application.services import IndexService
from rag.infrastructure.storage.file_store import FileStoreAdapter
```

```python
# ❌ FORBIDDEN IMPORTS

# Domain importing anything
from rag.application import ...  # FORBIDDEN
from rag.infrastructure import ...  # FORBIDDEN
from rag.cli import ...  # FORBIDDEN

# Application importing infrastructure directly
from rag.infrastructure.storage import ...  # FORBIDDEN (use dependency injection)

# Infrastructure importing application
from rag.application import ...  # FORBIDDEN
```

### Code Organization Rules

1. **Domain Layer**
   - NO file I/O
   - NO network calls
   - NO database access
   - NO external libraries (except stdlib, typing, dataclasses)
   - Pure Python, pure logic

2. **Application Layer**
   - Orchestrates domain models and ports
   - NO direct infrastructure imports
   - Uses dependency injection
   - Business workflows only

3. **Infrastructure Layer**
   - Implements port interfaces
   - All external system access
   - All I/O operations
   - Can use any libraries

4. **CLI Layer**
   - Wires dependencies
   - User interface only
   - No business logic

### Testing Rules

1. **Domain Tests**
   - Unit tests only
   - No mocks needed
   - Fast, isolated

2. **Application Tests**
   - Use mocks for ports
   - Test business logic
   - Integration tests for services

3. **Infrastructure Tests**
   - Integration tests
   - Test real adapters
   - May require external systems (Ollama, file system)

### Workspace Rules

1. **Always use workspace paths**
   - Never hardcode `~/.rag_data/`
   - Use workspace manager
   - Support default workspace

2. **Isolation**
   - No cross-workspace access
   - Workspace-specific config
   - Isolated storage

### CLI Compatibility Rules

1. **No Breaking Changes**
   - All existing commands must work
   - Same options, same behavior
   - Backward compatible output

2. **Additive Only**
   - New features are additions
   - New options are optional
   - Default behavior unchanged

### Error Handling Rules

1. **Domain Errors**
   - Raise domain exceptions
   - No infrastructure details

2. **Application Errors**
   - Catch domain errors
   - Wrap in application errors
   - Log appropriately

3. **Infrastructure Errors**
   - Catch external errors
   - Wrap in infrastructure errors
   - Log with context

### Documentation Rules

1. **All Ports Documented**
   - Method signatures
   - Parameter types
   - Return types
   - Behavior description

2. **All Services Documented**
   - Responsibilities
   - Dependencies
   - Usage examples

3. **Architecture Decisions**
   - Document in ARCHITECTURE_SPEC.md
   - Update when changing architecture

---

## Appendix: Quick Reference

### Current → Target Mapping

| Current | Target |
|---------|--------|
| `rag/scanner.py` | `rag/infrastructure/storage/file_store.py` |
| `rag/extractors/*` | `rag/infrastructure/extractors/*` |
| `rag/chunkers/*` | `rag/infrastructure/chunkers/*` |
| `rag/embeddings.py` | `rag/infrastructure/embeddings/ollama_embedder.py` |
| `rag/vector_store.py` | `rag/infrastructure/vector/faiss_index.py` |
| `rag/registry.py` | `rag/infrastructure/storage/registry_store.py` |
| `rag/rag_pipeline.py` | `rag/application/services.py` (QueryService) |
| `rag/cli.py` | `rag/cli/commands.py` |

### Workspace Path Helper

```python
# rag/infrastructure/storage/workspace.py

def get_workspace_path(workspace_slug: str = "default") -> Path:
    """Get workspace storage path."""
    base = Path.home() / ".rag_data" / "workspaces"
    return base / workspace_slug

def ensure_workspace(workspace_slug: str = "default") -> Path:
    """Ensure workspace directory exists."""
    path = get_workspace_path(workspace_slug)
    path.mkdir(parents=True, exist_ok=True)
    return path
```

---

**End of Architecture Specification**

This document serves as the **contract** for all future development. Any deviations must be documented and approved before implementation.


