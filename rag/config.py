"""Configuration management for RAG system."""
import os
from pathlib import Path
from typing import List, Optional
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings


class OllamaConfig(BaseModel):
    """Ollama API configuration."""
    base_url: str = "http://localhost:11434"
    embedding_model: str = "nomic-embed-text"
    llm_model: str = "llama3.2"
    timeout: int = 300


class ChunkingConfig(BaseModel):
    """Chunking configuration."""
    text_chunk_size: int = 900
    text_overlap: int = 150
    code_chunk_size: int = 800
    code_overlap: int = 100


class IndexingConfig(BaseModel):
    """Indexing configuration."""
    top_k: int = 5
    batch_size: int = 32
    use_hnsw: bool = True  # Use HNSW for better performance on larger datasets
    hnsw_m: int = 32
    hnsw_ef_construction: int = 200


class RAGQueryConfig(BaseModel):
    """RAG query configuration."""
    use_general_knowledge: bool = True  # Allow LLM to use general knowledge if indexed content insufficient
    similarity_threshold: float = 0.3  # Minimum similarity score (0-1) to consider chunks relevant


class RAGConfig(BaseSettings):
    """Main RAG configuration."""
    ollama: OllamaConfig = Field(default_factory=OllamaConfig)
    chunking: ChunkingConfig = Field(default_factory=ChunkingConfig)
    indexing: IndexingConfig = Field(default_factory=IndexingConfig)
    rag: RAGQueryConfig = Field(default_factory=RAGQueryConfig)
    
    # File type support
    text_extensions: List[str] = Field(default_factory=lambda: [".txt", ".md"])
    code_extensions: List[str] = Field(
        default_factory=lambda: [".py", ".js", ".ts", ".json", ".yaml", ".yml"]
    )
    
    # Ignore patterns
    ignore_patterns: List[str] = Field(
        default_factory=lambda: [
            ".git/",
            "node_modules/",
            "dist/",
            "build/",
            ".venv/",
            "venv/",
            "__pycache__/",
            ".pytest_cache/",
            "*.pyc",
            "*.pyo",
            "*.lock",
            ".DS_Store",
            "*.log",
        ]
    )
    
    # Storage paths
    data_dir: Path = Field(default_factory=lambda: Path.home() / ".rag_data")
    db_path: Path = Field(default_factory=lambda: Path.home() / ".rag_data" / "rag.db")
    index_path: Path = Field(default_factory=lambda: Path.home() / ".rag_data" / "faiss.index")
    
    # Legacy paths (for migration)
    metadata_path: Path = Field(default_factory=lambda: Path.home() / ".rag_data" / "metadata.db")
    registry_path: Path = Field(default_factory=lambda: Path.home() / ".rag_data" / "registry.db")
    
    class Config:
        env_prefix = "RAG_"
        case_sensitive = False
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Ensure data directory exists
        self.data_dir.mkdir(parents=True, exist_ok=True)


def load_config(config_path: Optional[Path] = None) -> RAGConfig:
    """Load configuration from file or environment."""
    if config_path and config_path.exists():
        import yaml
        with open(config_path, "r") as f:
            config_dict = yaml.safe_load(f) or {}
        return RAGConfig(**config_dict)
    return RAGConfig()

