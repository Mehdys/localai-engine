"""Setup script for RAG system."""
from setuptools import setup, find_packages

setup(
    name="local-rag",
    version="0.1.0",
    description="Local-first RAG system using Ollama",
    packages=find_packages(),
    install_requires=[
        "typer>=0.9.0",
        "pydantic>=2.0.0",
        "pydantic-settings>=2.0.0",
        "faiss-cpu>=1.7.4",
        "numpy>=1.24.0",
        "requests>=2.31.0",
        "pyyaml>=6.0",
    ],
    entry_points={
        "console_scripts": [
            "rag=rag.cli:app",
        ],
    },
    python_requires=">=3.10",
)

