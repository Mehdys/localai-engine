# LocalAI Engine

<div align="center">

**Local-first RAG infrastructure for private, offline knowledge bases**

*Index your codebase and documents locally. Query with natural language. Zero cloud dependencies.*

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Local-First](https://img.shields.io/badge/local--first-100%25-green.svg)](https://www.inkandswitch.com/local-first/)

[Quick Start](#-quick-start) • [Architecture](#-architecture) • [Documentation](#-documentation) • [Contributing](#-contributing)

</div>

---

## Why LocalAI Engine?

**The problem:** Most RAG systems require cloud APIs, send your data externally, or lock you into proprietary platforms. You want to query your private codebase and documents with natural language, but you need **complete control** and **zero data leakage**.

**The solution:** LocalAI Engine runs entirely on your machine. It uses [Ollama](https://ollama.ai) for local LLM inference, [FAISS](https://github.com/facebookresearch/faiss) for fast vector search, and a unified SQLite database for metadata. Your data never leaves your computer.

**What it does:** Transforms your files into a searchable knowledge base. Ask questions in natural language. Get answers with source citations. All processing happens locally.

---

## Who Is This For?

| Use Case | Why LocalAI Engine? |
|----------|---------------------|
| **Developers** | Query your codebase without exposing it to cloud services. Understand large codebases quickly. |
| **Researchers** | Index papers and documents privately. Build knowledge bases for sensitive research. |
| **Teams** | Self-hosted RAG infrastructure. No vendor lock-in, no API costs, complete data sovereignty. |
| **Privacy-conscious users** | Process proprietary documents, internal wikis, or personal notes without cloud dependencies. |
| **Offline workflows** | Work with RAG capabilities without internet connectivity. Perfect for air-gapped environments. |

---

## How It Compares

| Feature | LocalAI Engine | LangChain | LlamaIndex | Cloud RAG (Pinecone, etc.) |
|---------|----------------|-----------|------------|----------------------------|
| **Local-first** | ✅ 100% local | ❌ Cloud APIs | ❌ Cloud APIs | ❌ Cloud-only |
| **Privacy** | ✅ Zero data leaves machine | ⚠️ Depends on providers | ⚠️ Depends on providers | ❌ Data sent to cloud |
| **Infrastructure control** | ✅ Full control | ❌ Vendor-dependent | ❌ Vendor-dependent | ❌ Vendor lock-in |
| **Cost** | ✅ Free (runs on your hardware) | 💰 Pay per API call | 💰 Pay per API call | 💰 Subscription fees |
| **Offline capable** | ✅ Works offline | ❌ Requires internet | ❌ Requires internet | ❌ Requires internet |
| **Setup complexity** | ⚡ Simple (Ollama + Python) | ⚡ Moderate | ⚡ Moderate | ⚡ Simple (but cloud-dependent) |
| **Incremental indexing** | ✅ SHA256-based change detection | ⚠️ Varies | ⚠️ Varies | ⚠️ Varies |
| **Stable vector IDs** | ✅ Built-in (no JSON mapping) | ⚠️ Varies | ⚠️ Varies | ⚠️ Varies |

**When to choose LocalAI Engine:**
- You need complete data privacy
- You want to avoid cloud API costs
- You work with sensitive or proprietary content
- You need offline capabilities
- You prefer self-hosted infrastructure

---

## 🚀 Quick Start

### Prerequisites

1. **Ollama** (for local LLM and embeddings):
   ```bash
   brew install ollama  # macOS
   # Or download from https://ollama.ai
   
   ollama serve
   ollama pull nomic-embed-text  # Embeddings (768 dim)
   ollama pull llama3.2          # LLM for answers
   ```

2. **Python 3.10+**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

### Installation

```bash
git clone https://github.com/Mehdys/localai-engine.git
cd localai-engine
pip install -r requirements.txt
pip install -e .  # Install CLI
```

### Your First Query

```bash
# 1. Index your codebase
rag index ~/projects/myproject

# 2. Ask a question
rag ask "How does authentication work?"

# 3. Validate system health
rag validate
```

**That's it.** Your files are now searchable with natural language queries.

---

## ✨ Features

### Core Capabilities

- **🔍 Semantic Search**: Find content by meaning, not keywords. Powered by FAISS vector similarity.
- **📁 Multi-format Support**: Index code (`.py`, `.js`, `.ts`), documents (`.txt`, `.md`), and PDFs.
- **⚡ Fast Indexing**: Incremental updates using SHA256 change detection. Only re-indexes what changed.
- **🎯 Smart Chunking**: Code-aware (function/class boundaries) and text-aware (sentence/paragraph) splitting.
- **🔒 Privacy-first**: 100% local processing. No external APIs. No data transmission.
- **🛠️ Developer Tools**: Built-in validation, debugging, and integrity checks.

### Technical Highlights

- **Unified Database**: Single SQLite file (`rag.db`) stores all metadata. No JSON mapping files.
- **Stable Vector IDs**: `vector_id == chunk_id` ensures reliable retrieval without external mappings.
- **File Versioning**: Tracks document changes over time. Enables efficient incremental updates.
- **Manifest System**: Validates index configuration. Detects configuration mismatches.
- **Type-safe Pipeline**: Clean contracts: `Segment → Chunk → RetrievedChunk`.

---

## 🏗️ Architecture

### High-Level Overview

LocalAI Engine transforms files into searchable knowledge through a modular pipeline:

```
┌─────────────────────────────────────────────────────────────────────┐
│                         📁 Your Files                                │
│                    (Code, Docs, Text Files)                          │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             ▼
                    ┌────────────────┐
                    │   🔍 Scanner    │  ← Finds indexable files
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

### Indexing Pipeline

How files become searchable:

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
      │  • Skips ignored patterns (.git/, node_modules/, etc.)
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

### Query Pipeline

How questions get answered:

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

### Database Schema

Unified SQLite database (`rag.db`) architecture:

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

**Key Design Decisions:**

| Feature | Benefit |
|---------|---------|
| **Stable Vector IDs** | `vector_id == chunk_id` means no JSON mapping file needed |
| **File Versioning** | Track file changes over time, only re-index what changed |
| **Incremental Updates** | Changed files create new `doc_version`, unchanged files skipped |
| **Manifest System** | Validates index configuration matches current settings |
| **Unified Storage** | Everything in one database - easy to backup and migrate |

### Type System

Clean, type-safe pipeline contracts:

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
# Extractors produce Segments
@dataclass
class Segment:
    text: str                    # Extracted text content
    loc: Dict[str, Any]          # Location: {line_start, line_end} or {page: N}

# Chunkers produce Chunks
@dataclass
class Chunk:
    text: str                    # Chunk text
    loc: Dict[str, Any]          # Location metadata
    chunk_hash: str              # SHA256(text + canonical_json(loc))

# Pipeline returns RetrievedChunks
@dataclass
class RetrievedChunk:
    chunk_id: int                # Database ID (also vector_id in FAISS)
    text: str                    # Chunk content
    loc: Dict[str, Any]          # Location for citation
    path: str                    # File path
    score: float                 # Raw similarity (-1 to 1)
    display_score: float         # Normalized (0 to 1) for UI
```

**Contract Flow:**

```
Extractors  →  List[Segment]  →  Chunkers  →  List[Chunk]  →  Database
                                                                    │
                                                                    ▼
User Query  →  Embedding  →  FAISS Search  →  RetrievedChunk[]  →  Answer
```

---

## 🔧 CLI Reference

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

# Use custom config
rag index ~/projects/myproject --config config.yaml
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

**Output:**
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

---

## ⚙️ Configuration

Create a `config.yaml` file to customize behavior:

```yaml
ollama:
  base_url: "http://localhost:11434"
  embedding_model: "nomic-embed-text"
  llm_model: "llama3.2"
  timeout: 300

chunking:
  text_chunk_size: 900      # Characters per text chunk
  text_overlap: 150          # Overlap between chunks
  code_chunk_size: 800      # Characters per code chunk
  code_overlap: 100          # Overlap between code chunks

indexing:
  top_k: 5                   # Default number of chunks to retrieve
  batch_size: 32             # Embedding batch size
  use_hnsw: true             # Use HNSW index (faster, approximate)
  hnsw_m: 32                 # HNSW parameter
  hnsw_ef_construction: 200  # HNSW construction parameter

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

---

## 📁 Project Structure

```
localai-engine/
├── rag/
│   ├── __init__.py
│   ├── config.py              # Configuration management
│   ├── scanner.py             # File discovery and filtering
│   ├── registry.py            # File registry (compatibility layer)
│   ├── db.py                  # Unified SQLite database
│   ├── embeddings.py          # Ollama embeddings client
│   ├── vector_store.py        # FAISS vector store
│   ├── indexing.py            # Indexing pipeline
│   ├── rag_pipeline.py        # RAG query pipeline
│   ├── cli.py                 # CLI interface
│   ├── types.py               # Core types (Segment, Chunk, RetrievedChunk)
│   ├── extractors/
│   │   ├── text_extractor.py
│   │   ├── code_extractor.py
│   │   └── pdf_extractor.py
│   └── chunkers/
│       ├── text_chunker.py
│       └── code_chunker.py
├── tests/
│   ├── step0/                 # Step 0: Observability tests
│   ├── step1/                 # Step 1: Database tests
│   ├── step2/                 # Step 2: Pipeline contract tests
│   └── test_*.py              # Baseline tests
├── scripts/
│   └── verify_step1.py       # Step 1 verification script
├── config.example.yaml        # Example configuration
├── requirements.txt           # Python dependencies
├── setup.py                   # Package setup
└── README.md                  # This file
```

---

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

---

## 🗺️ Roadmap

### v0 (Current)

✅ **Core Features**
- Local-first RAG pipeline
- Unified SQLite database
- FAISS vector store with stable IDs
- Incremental indexing
- CLI interface with validation and debugging

✅ **Architecture**
- Type-safe pipeline contracts (Segment → Chunk → RetrievedChunk)
- File versioning system
- Manifest-based configuration validation
- Modular extractor/chunker architecture

### v1 (Short-term)

🔲 **Enhanced Features**
- Session-based memory for conversational queries
- Multi-index support (separate indexes for different document types)
- Advanced chunking strategies (semantic chunking, hierarchical)
- Batch query processing
- Export/import functionality

🔲 **Developer Experience**
- Python SDK/API (beyond CLI)
- Web UI for querying and visualization
- Performance profiling and optimization tools
- Extended test coverage

### v2 (Future)

🔲 **Advanced Capabilities**
- Multi-modal support (images, audio transcription)
- Hybrid search (vector + keyword)
- Fine-tuned embedding models
- Distributed indexing for large-scale deployments
- Plugin system for custom extractors/chunkers

🔲 **Enterprise Features**
- Multi-user support with access control
- Audit logging
- Backup and restore utilities
- Monitoring and observability dashboards

---

## 🐛 Troubleshooting

### Ollama Not Running

```bash
# Check if Ollama is running
curl http://localhost:11434/api/tags

# Start Ollama if needed
ollama serve
```

### Models Not Found

```bash
# List available models
ollama list

# Pull required models
ollama pull nomic-embed-text
ollama pull llama3.2
```

### FAISS Installation Issues

On macOS:
```bash
brew install cmake
pip install faiss-cpu
```

### Database Integrity Issues

```bash
# Run validation
rag validate

# If issues found, you may need to re-index
rag index <paths>
```

### Large File Handling

The system streams files and batches embeddings to handle large codebases efficiently. If you encounter memory issues:
- Reduce `batch_size` in config
- Use HNSW index (default) for better memory efficiency
- Process directories separately

---

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
