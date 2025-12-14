"""RAG pipeline: retrieve, prompt, generate."""
import requests
import json
from typing import List, Dict, Tuple, Optional
from rag.config import RAGConfig, OllamaConfig
from rag.embeddings import OllamaEmbeddings
from rag.vector_store import VectorStore
from rag.db import RAGDatabase
from rag.types import RetrievedChunk


class RAGPipeline:
    """RAG pipeline for querying."""
    
    def __init__(
        self,
        config: RAGConfig,
        embeddings: OllamaEmbeddings,
        vector_store: VectorStore,
        db: RAGDatabase,
    ):
        self.config = config
        self.ollama_config = config.ollama
        self.embeddings = embeddings
        self.vector_store = vector_store
        self.db = db
    
    def query(
        self, 
        question: str, 
        top_k: int = 5, 
        use_general_knowledge: Optional[bool] = None,
        similarity_threshold: Optional[float] = None
    ) -> Dict:
        """
        Query the RAG system.
        
        Args:
            question: Question to ask
            top_k: Number of chunks to retrieve
            use_general_knowledge: If True, allow LLM to use general knowledge when context insufficient.
                                   If None, uses config default.
            similarity_threshold: Minimum similarity score (0-1) to consider chunks relevant.
                                  If None, uses config default.
        
        Returns:
            {
                "answer": str,
                "sources": List[Dict] with file_path, line_range, text,
                "answer_source": str,  # "indexed", "general_knowledge", "indexed_low_relevance", or "none"
                "relevance_score": float  # Best similarity score from retrieved chunks
            }
        """
        # Use config defaults if not provided
        use_general = use_general_knowledge if use_general_knowledge is not None else self.config.rag.use_general_knowledge
        threshold = similarity_threshold if similarity_threshold is not None else self.config.rag.similarity_threshold
        
        # 1. Embed query
        query_embedding = self.embeddings.embed(question)
        
        # 2. Retrieve top-k chunks
        results = self.vector_store.search(query_embedding, top_k)
        
        if not results:
            if use_general:
                # No indexed content, use general knowledge
                prompt = f"""Answer the following question using your general knowledge.

Question: {question}

Answer:"""
                answer = self._call_llm(prompt)
                return {
                    "answer": answer,
                    "sources": [],
                    "answer_source": "general_knowledge",
                    "relevance_score": 0.0,
                }
            else:
                return {
                    "answer": "I don't have any indexed content to answer your question.",
                    "sources": [],
                    "answer_source": "none",
                    "relevance_score": 0.0,
                }
        
        # 3. Get chunk metadata and check relevance
        retrieved_chunks: List[RetrievedChunk] = []
        best_score = -1.0
        
        for chunk_id, score in results:
            # Normalize score from [-1, 1] to [0, 1] for threshold comparison
            normalized_score = (float(score) + 1) / 2
            best_score = max(best_score, normalized_score)
            
            chunk = self.db.get_chunk_by_vector_id(
                chunk_id,
                self.embeddings.model,
                "documents"
            )
            if not chunk:
                continue
            
            chunk_text = chunk["content"]
            document_path = chunk["document_path"]
            loc = json.loads(chunk["loc_json"])
            
            retrieved_chunk = RetrievedChunk(
                chunk_id=chunk_id,
                text=chunk_text,
                loc=loc,
                path=document_path,
                score=float(score),
            )
            retrieved_chunks.append(retrieved_chunk)
        
        # 4. Determine if context is sufficient
        context_sufficient = best_score >= threshold
        
        # 5. Build sources list
        sources = []
        context_chunks = []
        for rc in retrieved_chunks:
            context_chunks.append(rc.text)
            start_line = rc.loc.get("line_start")
            end_line = rc.loc.get("line_end")
            sources.append({
                "file_path": rc.path,
                "line_range": f"{start_line}-{end_line}" if start_line and end_line else None,
                "score": rc.display_score or rc.score,
                "text": rc.text[:200] + "..." if len(rc.text) > 200 else rc.text,
            })
        
        # 6. Build prompt based on context sufficiency
        if context_sufficient:
            # Use indexed content primarily
            context = "\n\n".join([
                f"[Document {i+1}]\n{chunk}"
                for i, chunk in enumerate(context_chunks)
            ])
            
            prompt = f"""Answer the following question using the provided context. Prioritize information from the context, but you may supplement with your general knowledge if the context is incomplete.

Context:
{context}

Question: {question}

Answer:"""
            answer_source = "indexed"
        else:
            # Context insufficient, use general knowledge with context as reference
            if use_general:
                context = "\n\n".join([
                    f"[Document {i+1}]\n{chunk}"
                    for i, chunk in enumerate(context_chunks)
                ])
                
                prompt = f"""Answer the following question using your general knowledge. The following context from indexed documents may be relevant but is not highly relevant (similarity score: {best_score:.2f}). Use it as a reference if helpful, but rely primarily on your general knowledge.

Context (low relevance):
{context}

Question: {question}

Answer:"""
                answer_source = "general_knowledge"
            else:
                # Don't use general knowledge, but still provide context
                context = "\n\n".join([
                    f"[Document {i+1}]\n{chunk}"
                    for i, chunk in enumerate(context_chunks)
                ])
                
                prompt = f"""Answer the following question using ONLY the provided context. If the answer cannot be found in the context, say "I don't know" rather than making something up.

Context:
{context}

Question: {question}

Answer:"""
                answer_source = "indexed_low_relevance"
        
        # 7. Call LLM
        answer = self._call_llm(prompt)
        
        return {
            "answer": answer,
            "sources": sources,
            "answer_source": answer_source,
            "relevance_score": best_score,
        }
    
    def explain(self, question: str, top_k: int = 5) -> Dict:
        """
        Explain retrieval process for debugging.
        
        Returns:
            {
                "retrieved_chunks": List[Dict] with detailed info,
                "prompt_length": int,
                "memory_hits": int (always 0 for now, no session support yet)
            }
        """
        # 1. Embed query
        query_embedding = self.embeddings.embed(question)
        
        # 2. Retrieve top-k chunks
        results = self.vector_store.search(query_embedding, top_k)
        
        retrieved_chunks_list: List[RetrievedChunk] = []
        
        for chunk_id, raw_score in results:
            # chunk_id is the stable DB chunk ID (vector_id)
            chunk = self.db.get_chunk_by_vector_id(
                chunk_id,
                self.embeddings.model,
                "documents"
            )
            if not chunk:
                continue
            
            chunk_text = chunk["content"]
            document_path = chunk["document_path"]
            loc = json.loads(chunk["loc_json"])
            
            retrieved_chunk = RetrievedChunk(
                chunk_id=chunk_id,
                text=chunk_text,
                loc=loc,
                path=document_path,
                score=float(raw_score),
            )
            retrieved_chunks_list.append(retrieved_chunk)
        
        # Build backward-compatible format for explain output
        retrieved_chunks = []
        for rc in retrieved_chunks_list:
            start_line = rc.loc.get("line_start")
            end_line = rc.loc.get("line_end")
            citation = rc.format_citation()
            
            retrieved_chunks.append({
                "file_path": rc.path,
                "citation": citation,
                "raw_score": rc.score,
                "display_score": rc.display_score,
                "text_preview": rc.text[:200] + "..." if len(rc.text) > 200 else rc.text,
                "text_full": rc.text,  # Store full text for prompt length calculation
                "start_line": start_line,
                "end_line": end_line,
            })
        
        # 3. Build prompt (same as query) to get length
        # Use full text for accurate prompt length
        context = "\n\n".join([
            f"[Document {i+1}]\n{chunk['text_full']}"
            for i, chunk in enumerate(retrieved_chunks)
        ])
        
        prompt = f"""Answer the following question using ONLY the provided context. If the answer cannot be found in the context, say "I don't know" rather than making something up.

Context:
{context}

Question: {question}

Answer:"""
        
        return {
            "retrieved_chunks": retrieved_chunks,
            "prompt_length": len(prompt),
            "memory_hits": 0,  # No session support yet
        }
    
    def _read_chunk_text(self, file_path: str, start_offset: Optional[int], end_offset: Optional[int]) -> str:
        """Read chunk text from file (fallback method - chunks should be in DB)."""
        from pathlib import Path
        
        try:
            with open(Path(file_path), "r", encoding="utf-8", errors="replace") as f:
                if start_offset is not None and end_offset is not None:
                    f.seek(start_offset)
                    return f.read(end_offset - start_offset)
                else:
                    # Fallback: read entire file
                    return f.read()
        except Exception:
            return "[Unable to read chunk]"
    
    def _call_llm(self, prompt: str) -> str:
        """Call Ollama LLM API."""
        url = f"{self.ollama_config.base_url}/api/generate"
        
        payload = {
            "model": self.ollama_config.llm_model,
            "prompt": prompt,
            "stream": False,
        }
        
        try:
            response = requests.post(
                url,
                json=payload,
                timeout=self.ollama_config.timeout,
            )
            response.raise_for_status()
            data = response.json()
            return data.get("response", "").strip()
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Failed to call Ollama LLM: {e}")


# 
