"""FAISS vector store with stable IDs and DB-backed mapping."""
import faiss
import numpy as np
from pathlib import Path
from typing import List, Tuple, Optional
from rag.config import IndexingConfig
from rag.db import RAGDatabase


class VectorStore:
    """FAISS-based vector store with stable IDs using IndexIDMap2."""
    
    def __init__(
        self,
        index_path: Path,
        config: IndexingConfig,
        dimension: int,
        db: RAGDatabase,
        model: str,
        index_name: str = "documents",
    ):
        self.index_path = index_path
        self.config = config
        self.dimension = dimension
        self.db = db
        self.model = model
        self.index_name = index_name
        self.index: Optional[faiss.Index] = None
        self.base_index: Optional[faiss.Index] = None
        
        self._init_index()
    
    def _init_index(self):
        """Initialize or load FAISS index with stable IDs."""
        if self.index_path.exists():
            self.load()
        else:
            # Create base index
            if self.config.use_hnsw:
                # HNSW for better performance on larger datasets
                # Use inner product metric for cosine similarity (normalized vectors)
                self.base_index = faiss.IndexHNSWFlat(
                    self.dimension,
                    self.config.hnsw_m,
                    faiss.METRIC_INNER_PRODUCT,
                )
                self.base_index.hnsw.efConstruction = self.config.hnsw_ef_construction
            else:
                # Flat index for smaller datasets
                self.base_index = faiss.IndexFlatIP(self.dimension)
            
            # Wrap with IndexIDMap2 for stable IDs
            self.index = faiss.IndexIDMap2(self.base_index)
    
    def add_vectors(self, vectors: np.ndarray, chunk_ids: List[int]):
        """
        Add vectors to index with stable chunk IDs.
        
        Args:
            vectors: (n, dim) array of normalized vectors
            chunk_ids: List of chunk IDs (from DB chunks.id) to use as stable vector IDs
        """
        if self.index is None:
            raise RuntimeError("Index not initialized")
        
        if len(vectors) != len(chunk_ids):
            raise ValueError("Vectors and chunk_ids must have same length")
        
        # Convert to numpy array of int64 for FAISS IDs
        ids_array = np.array(chunk_ids, dtype=np.int64)
        
        # Add to FAISS with stable IDs
        self.index.add_with_ids(vectors.astype(np.float32), ids_array)
    
    def search(self, query_vector: np.ndarray, top_k: int) -> List[Tuple[int, float]]:
        """
        Search for similar vectors.
        
        Args:
            query_vector: (dim,) query vector (normalized)
            top_k: Number of results to return
        
        Returns:
            List of (chunk_id, score) tuples, sorted by score descending
            chunk_id is the stable DB chunk ID (used as vector_id in FAISS)
        """
        if self.index is None or self.index.ntotal == 0:
            return []
        
        # Reshape for FAISS (needs (1, dim))
        query = query_vector.reshape(1, -1).astype(np.float32)
        
        # Search
        scores, indices = self.index.search(query, min(top_k, self.index.ntotal))
        
        # Convert to list of tuples
        # indices[0] contains the stable chunk IDs (vector_ids)
        results = [
            (int(idx), float(score))
            for idx, score in zip(indices[0], scores[0])
            if idx >= 0  # FAISS returns -1 for empty slots
        ]
        
        return results
    
    def get_chunk_id(self, vector_id: int) -> Optional[int]:
        """Get chunk ID for a vector ID (vector_id is the chunk_id in DB).
        
        Args:
            vector_id: FAISS vector ID (which is the chunk_id from DB)
        
        Returns:
            chunk_id (same as vector_id in Step 1)
        """
        # In Step 1, vector_id IS the chunk_id
        return vector_id if vector_id >= 0 else None
    
    def save(self):
        """Save index atomically (temp write then rename)."""
        if self.index is None:
            return
        
        # Atomic save: write to temp file then rename
        temp_path = self.index_path.with_suffix(".index.tmp")
        faiss.write_index(self.index, str(temp_path))
        
        # Atomic rename (works on Unix and Windows)
        temp_path.replace(self.index_path)
    
    def load(self):
        """Load index from disk."""
        if not self.index_path.exists():
            return
        
        # Load FAISS index
        loaded_index = faiss.read_index(str(self.index_path))
        
        # Check if it's wrapped with IndexIDMap2
        if isinstance(loaded_index, faiss.IndexIDMap2):
            self.index = loaded_index
            self.base_index = loaded_index.index
        else:
            # Legacy index without IDMap - wrap it
            self.base_index = loaded_index
            self.index = faiss.IndexIDMap2(self.base_index)
    
    def get_stats(self) -> dict:
        """Get index statistics."""
        if self.index is None:
            return {
                "vector_count": 0,
                "dimension": self.dimension,
                "index_type": "none",
            }
        
        index_type = "HNSW" if self.config.use_hnsw else "Flat"
        
        return {
            "vector_count": self.index.ntotal,
            "dimension": self.dimension,
            "index_type": index_type,
        }

