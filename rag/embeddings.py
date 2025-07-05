"""Ollama embeddings client."""
import requests
import numpy as np
from typing import List, Optional
from rag.config import OllamaConfig


class OllamaEmbeddings:
    """Client for Ollama embeddings API."""
    
    def __init__(self, config: OllamaConfig):
        self.config = config
        self.base_url = config.base_url
        self.model = config.embedding_model
        self.timeout = config.timeout
    
    def embed(self, text: str) -> np.ndarray:
        """
        Generate embedding for a single text.
        
        Returns:
            Normalized embedding vector
        """
        embeddings = self.embed_batch([text])
        return embeddings[0]
    
    def embed_batch(self, texts: List[str]) -> np.ndarray:
        """
        Generate embeddings for a batch of texts.
        
        Returns:
            Array of normalized embedding vectors (n, dim)
        """
        url = f"{self.base_url}/api/embeddings"
        
        # Ollama API expects a single prompt, so we'll call it for each text
        # In production, you might want to batch differently
        embeddings = []
        
        for text in texts:
            payload = {
                "model": self.model,
                "prompt": text,
            }
            
            try:
                response = requests.post(
                    url,
                    json=payload,
                    timeout=self.timeout,
                )
                response.raise_for_status()
                data = response.json()
                embedding = np.array(data["embedding"], dtype=np.float32)
                embeddings.append(embedding)
            except requests.exceptions.RequestException as e:
                raise RuntimeError(f"Failed to get embedding from Ollama: {e}")
        
        # Stack into matrix
        embeddings_array = np.vstack(embeddings)
        
        # Normalize (L2 normalization for cosine similarity)
        norms = np.linalg.norm(embeddings_array, axis=1, keepdims=True)
        norms = np.where(norms == 0, 1, norms)  # Avoid division by zero
        embeddings_array = embeddings_array / norms
        
        return embeddings_array
    
    def get_dimension(self) -> int:
        """Get embedding dimension by testing with a dummy text."""
        test_embedding = self.embed("test")
        return len(test_embedding)

