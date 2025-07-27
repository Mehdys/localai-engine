# Quick Start Guide

## 1. Prerequisites Check

Ensure Ollama is running and models are available:

```bash
# Check Ollama is running
curl http://localhost:11434/api/tags

# If not running, start it:
ollama serve

# Pull required models (if not already done):
ollama pull nomic-embed-text
ollama pull llama3.2  # or llama3
```

## 2. Install Dependencies

```bash
# Activate virtual environment (if using one)
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install package (for CLI command)
pip install -e .
```

## 3. First Indexing Session

```bash
# 1. See what would be indexed (dry run)
rag ingest ~/your-project --dry-run

# 2. Register files
rag ingest ~/your-project

# 3. Index files (this may take a while)
rag index ~/your-project

# 4. Check stats
rag stats
```

## 4. Ask Questions

```bash
rag ask "What is the main purpose of this codebase?"
rag ask "How does authentication work?" --top-k 10
```

## 5. Update Index (Incremental)

When files change, just run:

```bash
rag index ~/your-project
```

Only changed files will be re-indexed!

## Troubleshooting

### "Connection refused" to Ollama
- Ensure Ollama is running: `ollama serve`
- Check it's accessible: `curl http://localhost:11434/api/tags`

### "Model not found"
- Pull the models: `ollama pull nomic-embed-text` and `ollama pull llama3.2`

### FAISS installation issues
```bash
brew install cmake
pip install faiss-cpu --no-cache-dir
```

### Import errors
- Ensure you're in the project directory
- Activate virtual environment
- Run `pip install -e .` to install the package

