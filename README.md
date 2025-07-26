# Local-First RAG System

A production-minded, local-first RAG (Retrieval-Augmented Generation) system for macOS that indexes your files and answers questions using Ollama (LLM + embeddings). All processing happens locally - no external APIs required.

## Features

- **Incremental Indexing**: Only re-indexes changed files using SHA256 hashing
- **Smart Chunking**: Text and code-aware chunking with function/class boundary detection
- **FAISS Vector Store**: Fast similarity search using FAISS (HNSW or Flat index)
- **Skip Lists**: Configurable ignore patterns for common directories (`.git/`, `node_modules/`, etc.)
- **Multiple File Types**: Supports text (`.txt`, `.md`), code (`.py`, `.js`, `.ts`, `.json`, `.yaml`), and PDF (v2)
- **Clean Architecture**: Modular design with separate extractors, chunkers, and vector store
- **Persistent Registry**: SQLite-based tracking of files and chunks

## Prerequisites

1. **Ollama** must be installed and running:
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

## Installation

1. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Install the package** (optional, for CLI):
   ```bash
   pip install -e .
   ```

## Usage

### 1. Scan and Identify Files (Dry Run)

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

## Data Storage

All data is stored in `~/.rag_data/`:
- `faiss.index` - FAISS vector index
- `faiss.index.mapping.json` - Vector ID to chunk ID mapping
- `metadata.db` - SQLite database with chunk metadata
- `registry.db` - SQLite database with file registry

## Example Session

```bash
# 1. Check what would be indexed
rag ingest ~/projects/myproject --dry-run

# 2. Index the project
rag ingest ~/projects/myproject
rag index ~/projects/myproject

# 3. Ask questions
rag ask "How does authentication work in this codebase?"
rag ask "What are the main classes in the project?" --top-k 10

# 4. Check stats
rag stats

# 5. Update index (only changed files will be re-indexed)
rag index ~/projects/myproject
```

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

## Development

Run tests:
```bash
pytest tests/
```

## License

MIT

