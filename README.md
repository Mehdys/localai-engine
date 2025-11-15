# LocalAI Engine

<div align="center">

**A production-ready, local-first RAG (Retrieval-Augmented Generation) system**

*Index your files locally and query them with natural language using Ollama*

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Local-First](https://img.shields.io/badge/local--first-100%25-green.svg)](https://www.inkandswitch.com/local-first/)

</div>

---

## 🎯 Overview

LocalAI Engine is a **100% local** RAG system that enables you to:

- 📁 **Index** your codebase, documents, and files locally
- 🔍 **Search** using semantic similarity (no keyword matching)
- 💬 **Query** your indexed content with natural language questions
- 🔒 **Privacy-first** - all processing happens on your machine
- ⚡ **Fast** - FAISS-based vector search with HNSW indexing
- 🔄 **Incremental** - only re-indexes changed files

**No cloud services. No API keys. No data leaves your machine.**

---

## 🏗️ Architecture

### 🎯 How It Works

LocalAI Engine transforms your files into a searchable knowledge base through a clean, modular pipeline:

```
┌─────────────────────────────────────────────────────────────────────┐
│                         📁 Your Files                                │
│                    (Code, Docs, Text Files)                          │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             ▼
                    ┌────────────────┐
                    │   🔍 Scanner    │  ← Finds all indexable files
                    │  (File Finder)  │     Skips .git, node_modules, etc.
                    └────────┬───────┘
                             │
                             ▼
                    ┌────────────────┐
                    │  📄 Extractor   │  ← Reads file content
                    │ (Text/Code/PDF) │     Returns: List[Segment]
                    └────────┬───────┘
                             │
                             ▼
                    ┌────────────────┐
                    │  ✂️  Chunker    │  ← Splits into smart chunks
                    │ (Smart Split)  │     Returns: List[Chunk]
                    └────────┬───────┘
                             │
                             ▼
                    ┌────────────────┐
                    │  🧠 Embeddings  │  ← Converts to vectors
                    │    (Ollama)     │     768-dim vectors
                    └────────┬───────┘
                             │
                ┌────────────┴────────────┐
                ▼                         ▼
        ┌──────────────┐         ┌──────────────┐
        │  💾 Database  │         │  🔢 FAISS     │
        │   (SQLite)    │         │  (Vectors)    │
        │               │         │               │
        │ • Metadata    │         │ • Fast Search │
        │ • File Info   │         │ • HNSW Index  │
        │ • Chunk Hash  │         │ • Stable IDs  │
        └──────────────┘         └──────────────┘
```

### 📊 Indexing Flow (How Files Become Searchable)

```
┌─────────────────────────────────────────────────────────────────┐
│                    INDEXING PIPELINE                             │
└─────────────────────────────────────────────────────────────────┘

  📂 File System
      │
      │ 1. Scan
      ▼
  🔍 Scanner
      │  • Finds .py, .md, .txt, .js, etc.
      │  • Skips ignored patterns
      │
      │ 2. Extract
      ▼
  📄 Extractor
      │  • Reads file content
      │  • Detects structure (functions, classes)
      │  • Output: Segment(text="...", loc={line: 1-10})
      │
      │ 3. Chunk
      ▼
  ✂️  Chunker
      │  • Splits into overlapping chunks
      │  • Preserves code structure
      │  • Output: Chunk(text="...", hash="abc123...")
      │
      │ 4. Embed
      ▼
  🧠 Ollama Embeddings
      │  • Converts text → 768-dim vector
      │  • Model: nomic-embed-text
      │
      │ 5. Store
      ▼
  ┌─────────────────┐      ┌─────────────────┐
  │  💾 SQLite DB   │      │  🔢 FAISS Index │
  │                 │      │                 │
  │ • File metadata │      │ • Vector search │
  │ • Chunk content │      │ • Fast retrieval│
  │ • Locations     │      │ • Stable IDs    │
  └─────────────────┘      └─────────────────┘
```

### 🔍 Query Flow (How Questions Get Answered)

```
┌─────────────────────────────────────────────────────────────────┐
│                      QUERY PIPELINE                              │
└─────────────────────────────────────────────────────────────────┘

  ❓ User Question
      │  "How does authentication work?"
      │
      │ 1. Embed Question
      ▼
  🧠 Ollama Embeddings
      │  • Question → 768-dim vector
      │
      │ 2. Search
      ▼
  🔢 FAISS Vector Store
      │  • Find top-5 similar chunks
      │  • Returns: [(chunk_id, score), ...]
      │
      │ 3. Retrieve Metadata
      ▼
  💾 SQLite Database
      │  • Get chunk text, file path, line numbers
      │  • Returns: RetrievedChunk[]
      │
      │ 4. Build Context
      ▼
  📝 Prompt Builder
      │  • Combine question + retrieved chunks
      │  • Format: "Answer using this context: ..."
      │
      │ 5. Generate Answer
      ▼
  🤖 Ollama LLM
      │  • Model: llama3.2
      │  • Generates grounded answer
      │
      ▼
  ✅ Answer + Sources
      │  • Answer text
      │  • Citations: file.py:lines 42-58
      │  • Confidence scores
```

### 💾 Database Schema

The system uses a **unified SQLite database** (`rag.db`) that stores everything in one place:

```
┌─────────────────────────────────────────────────────────────┐
│                    📊 Unified Database (rag.db)             │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  📄 documents                                               │
│  ─────────────────────────────────────────────────────────  │
│  • id              → Primary key                            │
│  • path            → File path (unique)                     │
│  • doc_type        → "text", "code", "pdf"                 │
│  • size_bytes      → File size                              │
│  • created_at      → When first indexed                     │
│  • updated_at      → Last modification                      │
└────────────┬────────────────────────────────────────────────┘
             │
             │  One file can have multiple versions
             │  (when file changes, new version created)
             ▼
┌─────────────────────────────────────────────────────────────┐
│  📝 doc_versions                                            │
│  ─────────────────────────────────────────────────────────  │
│  • id              → Version ID                              │
│  • document_id     → Links to documents table               │
│  • sha256          → File hash (detects changes)            │
│  • mtime           → Modification time                      │
│  • extractor_ver   → Extractor version used                 │
│  • chunker_ver     → Chunker version used                   │
│  • created_at      → When this version was created          │
└────────────┬────────────────────────────────────────────────┘
             │
             │  Each version contains multiple chunks
             │  (text split into overlapping pieces)
             ▼
┌─────────────────────────────────────────────────────────────┐
│  ✂️  chunks                                                 │
│  ─────────────────────────────────────────────────────────  │
│  • id              → Chunk ID (used as vector_id!)         │
│  • doc_version_id  → Links to doc_versions                  │
│  • chunk_hash      → SHA256(text + location)                │
│  • content         → Actual chunk text                      │
│  • loc_json        → Location: {"line_start": 1, ...}      │
│  • created_at      → When chunked                           │
└────────────┬────────────────────────────────────────────────┘
             │
             │  Each chunk has embedding metadata
             │  (links to FAISS vector index)
             ▼
┌─────────────────────────────────────────────────────────────┐
│  🧠 embeddings                                              │
│  ─────────────────────────────────────────────────────────  │
│  • id              → Embedding record ID                    │
│  • chunk_id        → Links to chunks (FK)                   │
│  • model           → "nomic-embed-text"                      │
│  • dim             → 768 (embedding dimension)              │
│  • index_name      → "documents"                            │
│  • vector_id       → Same as chunk_id! (stable mapping)     │
│  • created_at      → When embedded                          │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  ⚙️  manifests                                              │
│  ─────────────────────────────────────────────────────────  │
│  • key             → "index_manifest"                        │
│  • value_json      → Config snapshot (for validation)       │
└─────────────────────────────────────────────────────────────┘
```

**🎯 Key Design Features:**

| Feature | Benefit |
|---------|---------|
| **Stable Vector IDs** | `vector_id == chunk_id` means no JSON mapping file needed |
| **File Versioning** | Track file changes over time, only re-index what changed |
| **Incremental Updates** | Changed files create new `doc_version`, unchanged files skipped |
| **Manifest System** | Validates index configuration matches current settings |
| **Unified Storage** | Everything in one database - easy to backup and migrate |

### 🔄 Type System (Data Flow)

The pipeline uses a clean, type-safe contract that flows through the system:

```
┌─────────────────────────────────────────────────────────────┐
│                    TYPE TRANSFORMATION                       │
└─────────────────────────────────────────────────────────────┘

  📄 Raw File
      │
      │ Extract
      ▼
  📦 Segment
      │  • text: "def hello():\n    return 'world'"
      │  • loc: {"line_start": 1, "line_end": 2}
      │
      │ Chunk
      ▼
  ✂️  Chunk
      │  • text: "def hello():\n    return 'world'"
      │  • loc: {"line_start": 1, "line_end": 2}
      │  • chunk_hash: "abc123..." (SHA256)
      │
      │ Store in DB + FAISS
      │
      │ Retrieve (on query)
      ▼
  🎯 RetrievedChunk
      │  • chunk_id: 42
      │  • text: "def hello():\n    return 'world'"
      │  • loc: {"line_start": 1, "line_end": 2}
      │  • path: "/path/to/file.py"
      │  • score: 0.85 (similarity)
      │  • display_score: 0.925 (normalized)
```

**Type Definitions:**

```python
# Step 1: Extractors produce Segments
@dataclass
class Segment:
    text: str                    # Extracted text content
    loc: Dict[str, Any]          # Location: {line_start, line_end} or {page: N}

# Step 2: Chunkers produce Chunks
@dataclass
class Chunk:
    text: str                    # Chunk text
    loc: Dict[str, Any]          # Location metadata
    chunk_hash: str              # SHA256(text + canonical_json(loc))
                                 # Used for deduplication

# Step 3: Pipeline returns RetrievedChunks
@dataclass
class RetrievedChunk:
    chunk_id: int                # Database ID (also vector_id in FAISS)
    text: str                    # Chunk content
    loc: Dict[str, Any]          # Location for citation
    path: str                    # File path
    score: float                 # Raw similarity (-1 to 1)
    display_score: float         # Normalized (0 to 1) for UI
```

**🔄 Contract Flow:**

```
Extractors  →  List[Segment]  →  Chunkers  →  List[Chunk]  →  Database
                                                                    │
                                                                    ▼
User Query  →  Embedding  →  FAISS Search  →  RetrievedChunk[]  →  Answer
```

---

---

## 🚀 Quick Start

Get started in 3 simple steps:

- **Incremental Indexing**: Only re-indexes changed files using SHA256 hashing
- **Smart Chunking**: Text and code-aware chunking with function/class boundary detection
- **FAISS Vector Store**: Fast similarity search using FAISS (HNSW or Flat index)
- **Skip Lists**: Configurable ignore patterns for common directories (`.git/`, `node_modules/`, etc.)
- **Multiple File Types**: Supports text (`.txt`, `.md`), code (`.py`, `.js`, `.ts`, `.json`, `.yaml`), and PDF (v2)
- **Clean Architecture**: Modular design with separate extractors, chunkers, and vector store
- **Persistent Registry**: SQLite-based tracking of files and chunks

### Prerequisites

1. **Install Ollama**:
   ```bash
   # Install Ollama (if not already installed)
   # Visit https://ollama.ai or use Homebrew:
   brew install ollama
   
   # Start Ollama
   ollama serve
   
   # Pull required models
   ollama pull nomic-embed-text  # For embeddings
   ollama pull llama3.2          # For LLM (or llama3)
   ```

2. **Python 3.10+** with virtual environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

### Installation

```bash
# Clone the repository
git clone https://github.com/Mehdys/localai-engine.git
cd localai-engine

# Install dependencies
pip install -r requirements.txt

# Install the package (for CLI)
pip install -e .
```

### Basic Usage

```bash
# 1. Index your codebase
rag index ~/projects/myproject

# 2. Ask questions
rag ask "How does authentication work?"

# 3. Check system health
rag validate

# 4. Debug retrieval
rag explain "What is the main function?"
```

---

## 📖 Features

### 🔍 Smart Indexing

- **Incremental Updates**: Only re-indexes changed files (SHA256-based)
- **Smart Chunking**: 
  - Text: Sentence/paragraph-aware splitting
  - Code: Function/class boundary detection
- **Multiple File Types**: `.txt`, `.md`, `.py`, `.js`, `.ts`, `.json`, `.yaml`, `.pdf`
- **Configurable Ignore Patterns**: Skip `.git/`, `node_modules/`, `venv/`, etc.

### 🎯 Vector Search

- **FAISS Backend**: Fast similarity search
- **HNSW Index**: Approximate nearest neighbor (default)
- **Flat Index**: Exact search (optional)
- **Stable IDs**: `vector_id == chunk_id` for reliable retrieval

### 💬 Natural Language Queries

- **Semantic Search**: Find relevant content by meaning, not keywords
- **Context-Aware Answers**: LLM generates answers using retrieved chunks
- **Source Citations**: Every answer includes file paths and line numbers
- **Configurable Top-K**: Retrieve 1-20 most relevant chunks

### 🔒 Privacy & Security

- **100% Local**: All processing on your machine
- **No External APIs**: Uses Ollama (runs locally)
- **No Data Transmission**: Nothing leaves your computer
- **SQLite Database**: All metadata stored locally

### 🛠️ Developer Tools

- **`rag validate`**: System health checks and integrity validation
- **`rag explain`**: Debug retrieval process and see what chunks were found
- **Comprehensive Tests**: Step-by-step test suites for each feature

---

## ⚙️ Configuration

First, scan your directories to see what would be indexed:

```bash
rag ingest /path/to/your/code /path/to/docs --dry-run
```

This will print all indexable files without actually indexing them.

### 2. Index Files

Index files for the first time or update the index:

```bash
rag index /path/to/your/code /path/to/docs
```

The system will:
- Scan directories recursively
- Skip ignored patterns (`.git/`, `node_modules/`, etc.)
- Only process changed files (based on SHA256 hash)
- Extract text, chunk it, create embeddings, and store in FAISS

### 3. Ask Questions

Query your indexed content:

```bash
rag ask "What does the main function do?" --top-k 5
```

The system will:
- Embed your question
- Retrieve top-k similar chunks
- Build a grounded prompt with context
- Call Ollama LLM to generate an answer
- Return answer with source citations

### 4. Check Statistics

View index statistics:

```bash
rag stats
```

Shows:
- Number of indexed files
- Total chunks
- Vector store information
- Last indexing time

## Configuration

Create a `config.yaml` file to customize behavior:

```yaml
ollama:
  base_url: "http://localhost:11434"
  embedding_model: "nomic-embed-text"
  llm_model: "llama3.2"
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

text_extensions:
  - ".txt"
  - ".md"

code_extensions:
  - ".py"
  - ".js"
  - ".ts"
  - ".json"
  - ".yaml"
  - ".yml"

ignore_patterns:
  - ".git/"
  - "node_modules/"
  - "dist/"
  - "build/"
  - ".venv/"
  - "venv/"
  - "__pycache__/"
  - "*.pyc"
  - "*.lock"
```

Use with `--config` flag:

```bash
rag index /path/to/code --config config.yaml
```

## Project Structure

```
rag/
├── __init__.py
├── config.py              # Configuration management
├── scanner.py             # File discovery and filtering
├── registry.py             # SQLite registry for files/chunks
├── embeddings.py           # Ollama embeddings client
├── vector_store.py         # FAISS vector store
├── rag_pipeline.py         # RAG query pipeline
├── cli.py                  # CLI interface
├── extractors/
│   ├── text_extractor.py
│   ├── code_extractor.py
│   └── pdf_extractor.py    # Stub for v2
└── chunkers/
    ├── text_chunker.py
    └── code_chunker.py

tests/
├── test_chunkers.py
└── test_registry.py
```

## 🗄️ Data Storage

All data is stored in `~/.rag_data/`:

```
~/.rag_data/
├── rag.db              # Unified SQLite database
│   ├── documents       # File metadata
│   ├── doc_versions    # File versioning
│   ├── chunks          # Text chunks
│   ├── embeddings      # Embedding metadata
│   └── manifests       # Index configuration
└── faiss.index         # FAISS vector index
```

**No JSON mapping files** - everything is in the database with stable IDs.

## 🔧 CLI Commands

### `rag ingest <paths...>`

Scan directories and identify indexable files.

```bash
# Dry run (see what would be indexed)
rag ingest ~/projects/myproject --dry-run

# Register files in database
rag ingest ~/projects/myproject
```

### `rag index <paths...>`

Index files: extract, chunk, embed, and store.

```bash
# Index a directory
rag index ~/projects/myproject

# Index multiple directories
rag index ~/code ~/docs
```

### `rag ask "<question>"`

Query your indexed content.

```bash
# Ask a question
rag ask "How does authentication work?"

# Retrieve more chunks
rag ask "What are the main classes?" --top-k 10
```

### `rag validate`

Check system health and integrity.

```bash
rag validate
```

Output:
```
✓ Ollama reachable at http://localhost:11434
✓ Embedding model 'nomic-embed-text' found (768 dim)
✓ LLM model 'llama3.2' found
✓ Documents index: HNSW with 1,234 vectors
✓ Database integrity: OK
  - No orphan chunks
  - Total files: 42
  - Total chunks: 1,234
```

### `rag explain "<question>"`

Debug retrieval process.

```bash
rag explain "What does the main function do?"
```

Shows:
- Retrieved chunks with scores
- Citation information
- Prompt length
- Which chunks were selected

### `rag stats`

View index statistics.

```bash
rag stats
```

### `rag migrate`

Migrate from v1 to v2 (if upgrading from older version).

## Troubleshooting

### Ollama Not Running

If you see connection errors:
```bash
# Check if Ollama is running
curl http://localhost:11434/api/tags

# Start Ollama if needed
ollama serve
```

### Models Not Found

Ensure models are pulled:
```bash
ollama list
# If nomic-embed-text or llama3.2 not listed:
ollama pull nomic-embed-text
ollama pull llama3.2
```

### FAISS Installation Issues

On macOS, you might need:
```bash
brew install cmake
pip install faiss-cpu
```

### Large File Handling

The system streams files and batches embeddings to handle large codebases efficiently. If you encounter memory issues:
- Reduce `batch_size` in config
- Use HNSW index (default) for better memory efficiency
- Process directories separately

## 🧪 Testing

Run the test suite:

```bash
# All tests
pytest tests/

# Step-specific tests
pytest tests/step0/    # Observability tests
pytest tests/step1/    # Database tests
pytest tests/step2/    # Pipeline contract tests

# With coverage
pytest --cov=rag tests/
```

---

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.

---

## 🙏 Acknowledgments

- [Ollama](https://ollama.ai) - Local LLM and embeddings
- [FAISS](https://github.com/facebookresearch/faiss) - Efficient similarity search
- Inspired by the [local-first software](https://www.inkandswitch.com/local-first/) movement

---

<div align="center">

**Built with ❤️ for privacy and local-first computing**

[Report Bug](https://github.com/Mehdys/localai-engine/issues) · [Request Feature](https://github.com/Mehdys/localai-engine/issues)

</div>


# 
