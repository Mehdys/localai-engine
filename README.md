# LocalAI Engine

<div align="center">

**RAG that never leaves your machine.**

*Private. Fast. Cited.*

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Local-First](https://img.shields.io/badge/local--first-100%25-green.svg)](https://www.inkandswitch.com/local-first/)

[Try it](#try-it) • [How it works](#architecture) • [Roadmap](#roadmap)

</div>

---

## Try it

```bash
rag index ~/projects/myproject
rag ask "How does authentication work?"
```

**Result:**

```
Answer:
Authentication is handled by the `verify_token()` function which validates 
JWT tokens against the secret key. The function checks token expiration and 
signature before allowing access to protected routes.

Sources:
  1. src/auth.py (lines 42-58) (score: 0.847)
     "def verify_token(token: str) -> bool:\n    try:\n        payload = jwt.decode(...)"
  
  2. src/middleware.py (lines 12-28) (score: 0.812)
     "class AuthMiddleware:\n    def __call__(self, request):\n        token = request.headers.get('Authorization')"
```

---

## Core Guarantees

- **100% local** — Your machine. Zero cloud.
- **No API keys** — [Ollama](https://ollama.ai) runs locally.
- **Stable IDs** — `vector_id == chunk_id`. No mappings.
- **Incremental** — SHA256 detection. Only changed files.
- **Reproducible** — Manifest validates config automatically.

---

## Who is this for?

| Use Case | Why LocalAI Engine |
|----------|-------------------|
| **Developers** | Query codebases privately. Zero cloud exposure. |
| **Researchers** | Index sensitive papers. Private knowledge bases. |
| **Privacy teams** | Self-hosted RAG. No lock-in. No API costs. |
| **Offline work** | Full RAG without internet. |

---

## How It Compares

| Feature | LocalAI Engine | Frameworks | Managed DBs |
|---------|----------------|------------|-------------|
| **Privacy** | 100% local | Your setup | Cloud |
| **Cost** | Free | Free | Subscription |
| **Offline** | ✅ | ✅ | ❌ |
| **Setup** | Simple | Moderate | Simple |
| **Incremental** | ✅ SHA256 | ⚠️ Varies | ⚠️ Varies |
| **Stable IDs** | ✅ Built-in | ⚠️ Varies | ⚠️ Varies |

**Choose LocalAI Engine for:** Privacy, zero costs, sensitive content, offline work.

---

## Quick Start

**Prerequisites:**

```bash
brew install ollama
ollama serve
ollama pull nomic-embed-text
ollama pull llama3.2
```

**Install:**

```bash
git clone https://github.com/Mehdys/localai-engine.git
cd localai-engine
pip install -r requirements.txt
pip install -e .
```

**Run:**

```bash
rag index ~/projects/myproject
rag ask "How does authentication work?"
```

Done.

---

## Architecture

Files become searchable knowledge:

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

<details>
<summary><strong>Indexing Pipeline</strong></summary>

Files become searchable in five steps:

```
📂 Files
    │
    │ [1] Scan
    ▼
🔍 Scanner
    Finds: .py, .md, .txt, .js
    Skips: .git/, node_modules/
    │
    │ [2] Extract
    ▼
📄 Extractor
    Reads content
    Detects structure
    → List[Segment]
    │
    │ [3] Chunk
    ▼
✂️  Chunker
    Smart splitting
    Preserves boundaries
    → List[Chunk]
    │
    │ [4] Embed
    ▼
🧠 Ollama
    text → 768-dim vector
    (nomic-embed-text)
    │
    │ [5] Store
    ▼
    ┌──────────────┐    ┌──────────────┐
    │ 💾 SQLite    │    │ 🔢 FAISS     │
    │ Metadata     │    │ Vectors       │
    │ Chunks       │    │ HNSW Index    │
    └──────────────┘    └──────────────┘
```

</details>

<details>
<summary><strong>Query Pipeline</strong></summary>

Questions become answers in five steps:

```
❓ Question
    │
    │ [1] Embed
    ▼
🧠 Ollama
    question → 768-dim vector
    │
    │ [2] Search
    ▼
🔢 FAISS
    Find top-5 similar
    → [(chunk_id, score)]
    │
    │ [3] Retrieve
    ▼
💾 SQLite
    Get text, path, lines
    → RetrievedChunk[]
    │
    │ [4] Build Context
    ▼
📝 Prompt Builder
    question + chunks
    → formatted prompt
    │
    │ [5] Generate
    ▼
🤖 Ollama LLM
    (llama3.2)
    │
    ▼
✅ Answer + Sources
    text + citations
```

</details>

<details>
<summary><strong>Database Schema</strong></summary>

Data flows through a unified SQLite database:

```
                    📄 documents
                    ┌─────────────┐
                    │ id           │
                    │ path (unique)│
                    │ doc_type     │
                    │ size_bytes   │
                    └──────┬───────┘
                           │ 1:N
                           │
                    📝 doc_versions
                    ┌─────────────┐
                    │ id           │
                    │ document_id  │──┐
                    │ sha256       │  │ tracks changes
                    │ mtime        │  │
                    └──────┬───────┘  │
                           │ 1:N      │
                           │          │
                    ✂️  chunks       │
                    ┌─────────────┐  │
                    │ id          │◄─┘ (vector_id)
                    │ doc_version │
                    │ chunk_hash  │
                    │ content     │
                    │ loc_json    │
                    └──────┬──────┘
                           │ 1:1
                           │
                    🧠 embeddings
                    ┌─────────────┐
                    │ chunk_id     │───┐
                    │ vector_id    │◄──┘ (same as chunk_id)
                    │ model        │
                    │ dim (768)    │
                    └──────────────┘
                           │
                           ▼
                    🔢 FAISS Index
                    (vector_id → 768-dim vector)
```

**Key relationships:**
- One document → Many versions (file changes tracked)
- One version → Many chunks (text split)
- One chunk → One embedding (1:1 mapping)
- `vector_id == chunk_id` (stable, no JSON mapping needed)

</details>

<details>
<summary><strong>Type System</strong></summary>

Type transformations through the pipeline:

```
┌─────────────────────────────────────────────────────────────┐
│                    INDEXING FLOW                            │
└─────────────────────────────────────────────────────────────┘

📄 Raw File
    │
    │ Extract
    ▼
📦 Segment
    ┌─────────────────────┐
    │ text: str           │
    │ loc: {line_start,   │
    │       line_end}     │
    └──────────┬──────────┘
               │
               │ Chunk
               ▼
✂️  Chunk
    ┌─────────────────────┐
    │ text: str           │
    │ loc: {line_start,   │
    │       line_end}     │
    │ chunk_hash: SHA256  │
    └──────────┬──────────┘
               │
               │ Store
               ▼
💾 Database + 🔢 FAISS
    (chunk_id = vector_id)


┌─────────────────────────────────────────────────────────────┐
│                    QUERY FLOW                               │
└─────────────────────────────────────────────────────────────┘

❓ User Query
    │
    │ Embed
    ▼
🔢 FAISS Search
    │
    │ Retrieve (chunk_id)
    ▼
🎯 RetrievedChunk
    ┌─────────────────────┐
    │ chunk_id: int       │
    │ text: str           │
    │ path: str           │
    │ loc: {line_start,   │
    │       line_end}     │
    │ score: float        │
    │ display_score: 0-1  │
    └─────────────────────┘
```

**Type contracts:**
- `Extractors` → `List[Segment]`
- `Chunkers` → `List[Chunk]`
- `FAISS Search` → `List[RetrievedChunk]`

</details>

---

## 🔧 CLI Reference

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

