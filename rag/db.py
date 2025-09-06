"""Unified SQLite database for RAG system."""
import sqlite3
import json
import time
from pathlib import Path
from typing import Optional, Dict, Any, List, ContextManager
from contextlib import contextmanager
from datetime import datetime


# Version constants
EXTRACTOR_VERSION = "1.0"
CHUNKER_VERSION = "1.0"
DB_VERSION = 1


class RAGDatabase:
    """Unified database for documents, chunks, embeddings, and manifests."""
    
    def __init__(self, db_path: Path):
        """Initialize database connection.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()
    
    def _init_schema(self):
        """Initialize database schema with migrations."""
        with self.connection() as conn:
            cursor = conn.cursor()
            
            # Check if schema exists
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='documents'
            """)
            schema_exists = cursor.fetchone() is not None
            
            if not schema_exists:
                self._create_schema(cursor)
                conn.commit()
            else:
                # Check DB version and migrate if needed
                self._migrate_schema(cursor, conn)
    
    def _create_schema(self, cursor: sqlite3.Cursor):
        """Create initial database schema."""
        # Documents table
        cursor.execute("""
            CREATE TABLE documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                path TEXT UNIQUE NOT NULL,
                doc_type TEXT NOT NULL,
                size_bytes INTEGER NOT NULL,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            )
        """)
        
        # Document versions table
        cursor.execute("""
            CREATE TABLE doc_versions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_id INTEGER NOT NULL,
                sha256 TEXT NOT NULL,
                mtime REAL NOT NULL,
                extractor_version TEXT NOT NULL,
                chunker_version TEXT NOT NULL,
                created_at REAL NOT NULL,
                UNIQUE(document_id, sha256),
                FOREIGN KEY(document_id) REFERENCES documents(id)
            )
        """)
        
        # Chunks table
        cursor.execute("""
            CREATE TABLE chunks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                doc_version_id INTEGER NOT NULL,
                chunk_hash TEXT NOT NULL,
                content TEXT NOT NULL,
                loc_json TEXT NOT NULL,
                created_at REAL NOT NULL,
                UNIQUE(doc_version_id, chunk_hash),
                FOREIGN KEY(doc_version_id) REFERENCES doc_versions(id)
            )
        """)
        
        # Embeddings table
        cursor.execute("""
            CREATE TABLE embeddings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chunk_id INTEGER NOT NULL,
                model TEXT NOT NULL,
                dim INTEGER NOT NULL,
                index_name TEXT NOT NULL,
                vector_id INTEGER NOT NULL,
                created_at REAL NOT NULL,
                UNIQUE(chunk_id, model, index_name),
                FOREIGN KEY(chunk_id) REFERENCES chunks(id)
            )
        """)
        
        # Manifests table
        cursor.execute("""
            CREATE TABLE manifests (
                key TEXT UNIQUE NOT NULL,
                value_json TEXT NOT NULL
            )
        """)
        
        # Create indexes for performance
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_documents_path ON documents(path)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_doc_versions_document_id ON doc_versions(document_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_doc_versions_sha256 ON doc_versions(sha256)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_chunks_doc_version_id ON chunks(doc_version_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_chunks_chunk_hash ON chunks(chunk_hash)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_embeddings_chunk_id ON embeddings(chunk_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_embeddings_vector_id ON embeddings(vector_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_embeddings_model_index ON embeddings(model, index_name)")
        
        # Store DB version
        cursor.execute("""
            INSERT INTO manifests (key, value_json)
            VALUES ('db_version', ?)
        """, (json.dumps(DB_VERSION),))
    
    def _migrate_schema(self, cursor: sqlite3.Cursor, conn: sqlite3.Connection):
        """Migrate schema if needed."""
        # Get current DB version
        cursor.execute("SELECT value_json FROM manifests WHERE key = 'db_version'")
        row = cursor.fetchone()
        current_version = int(json.loads(row[0])) if row else 0
        
        if current_version < DB_VERSION:
            # Future migrations go here
            # For now, just update version
            cursor.execute("""
                UPDATE manifests SET value_json = ? WHERE key = 'db_version'
            """, (json.dumps(DB_VERSION),))
            conn.commit()
    
    @contextmanager
    def connection(self) -> ContextManager[sqlite3.Connection]:
        """Get database connection as context manager."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
    
    @contextmanager
    def transaction(self) -> ContextManager[sqlite3.Connection]:
        """Get database connection with transaction support."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    
    # Document operations
    def get_document(self, path: Path) -> Optional[Dict[str, Any]]:
        """Get document by path."""
        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM documents WHERE path = ?", (str(path),))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def create_or_update_document(
        self,
        path: Path,
        doc_type: str,
        size_bytes: int,
    ) -> int:
        """Create or update document, return document ID."""
        with self.transaction() as conn:
            cursor = conn.cursor()
            now = time.time()
            
            # Check if exists
            cursor.execute("SELECT id FROM documents WHERE path = ?", (str(path),))
            row = cursor.fetchone()
            
            if row:
                doc_id = row[0]
                cursor.execute("""
                    UPDATE documents 
                    SET doc_type = ?, size_bytes = ?, updated_at = ?
                    WHERE id = ?
                """, (doc_type, size_bytes, now, doc_id))
            else:
                cursor.execute("""
                    INSERT INTO documents (path, doc_type, size_bytes, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (str(path), doc_type, size_bytes, now, now))
                doc_id = cursor.lastrowid
            
            return doc_id
    
    # Document version operations
    def get_doc_version(self, document_id: int, sha256: str) -> Optional[Dict[str, Any]]:
        """Get document version by document_id and sha256."""
        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM doc_versions 
                WHERE document_id = ? AND sha256 = ?
            """, (document_id, sha256))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def create_doc_version(
        self,
        document_id: int,
        sha256: str,
        mtime: float,
        extractor_version: str = EXTRACTOR_VERSION,
        chunker_version: str = CHUNKER_VERSION,
    ) -> int:
        """Create document version, return version ID."""
        with self.transaction() as conn:
            cursor = conn.cursor()
            now = time.time()
            
            cursor.execute("""
                INSERT OR IGNORE INTO doc_versions 
                (document_id, sha256, mtime, extractor_version, chunker_version, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (document_id, sha256, mtime, extractor_version, chunker_version, now))
            
            # Get the ID (either newly inserted or existing)
            cursor.execute("""
                SELECT id FROM doc_versions 
                WHERE document_id = ? AND sha256 = ?
            """, (document_id, sha256))
            row = cursor.fetchone()
            return row[0] if row else None
    
    def delete_doc_version_chunks(self, doc_version_id: int):
        """Delete all chunks for a document version."""
        with self.transaction() as conn:
            cursor = conn.cursor()
            # Delete embeddings first (foreign key constraint)
            cursor.execute("""
                DELETE FROM embeddings 
                WHERE chunk_id IN (
                    SELECT id FROM chunks WHERE doc_version_id = ?
                )
            """, (doc_version_id,))
            # Delete chunks
            cursor.execute("DELETE FROM chunks WHERE doc_version_id = ?", (doc_version_id,))
    
    # Chunk operations
    def get_chunk(self, chunk_id: int) -> Optional[Dict[str, Any]]:
        """Get chunk by ID."""
        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT c.*, dv.document_id, d.path as document_path
                FROM chunks c
                JOIN doc_versions dv ON c.doc_version_id = dv.id
                JOIN documents d ON dv.document_id = d.id
                WHERE c.id = ?
            """, (chunk_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def create_chunk(
        self,
        doc_version_id: int,
        chunk_hash: str,
        content: str,
        loc_json: Dict[str, Any],
    ) -> int:
        """Create chunk, return chunk ID."""
        with self.transaction() as conn:
            cursor = conn.cursor()
            now = time.time()
            
            cursor.execute("""
                INSERT OR IGNORE INTO chunks 
                (doc_version_id, chunk_hash, content, loc_json, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (doc_version_id, chunk_hash, content, json.dumps(loc_json), now))
            
            # Get the ID (either newly inserted or existing)
            cursor.execute("""
                SELECT id FROM chunks 
                WHERE doc_version_id = ? AND chunk_hash = ?
            """, (doc_version_id, chunk_hash))
            row = cursor.fetchone()
            return row[0] if row else None
    
    def chunk_exists(self, doc_version_id: int, chunk_hash: str) -> bool:
        """Check if chunk exists."""
        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 1 FROM chunks 
                WHERE doc_version_id = ? AND chunk_hash = ?
                LIMIT 1
            """, (doc_version_id, chunk_hash))
            return cursor.fetchone() is not None
    
    # Embedding operations
    def create_embedding(
        self,
        chunk_id: int,
        model: str,
        dim: int,
        index_name: str,
        vector_id: int,
    ) -> int:
        """Create embedding record, return embedding ID."""
        with self.transaction() as conn:
            cursor = conn.cursor()
            now = time.time()
            
            cursor.execute("""
                INSERT OR IGNORE INTO embeddings 
                (chunk_id, model, dim, index_name, vector_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (chunk_id, model, dim, index_name, vector_id, now))
            
            # Get the ID
            cursor.execute("""
                SELECT id FROM embeddings 
                WHERE chunk_id = ? AND model = ? AND index_name = ?
            """, (chunk_id, model, index_name))
            row = cursor.fetchone()
            return row[0] if row else None
    
    def get_chunk_by_vector_id(self, vector_id: int, model: str, index_name: str) -> Optional[Dict[str, Any]]:
        """Get chunk by vector_id (FAISS ID)."""
        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT c.*, dv.document_id, d.path as document_path
                FROM chunks c
                JOIN embeddings e ON c.id = e.chunk_id
                JOIN doc_versions dv ON c.doc_version_id = dv.id
                JOIN documents d ON dv.document_id = d.id
                WHERE e.vector_id = ? AND e.model = ? AND e.index_name = ?
            """, (vector_id, model, index_name))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    # Manifest operations
    def get_manifest(self, key: str) -> Optional[Dict[str, Any]]:
        """Get manifest value by key."""
        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value_json FROM manifests WHERE key = ?", (key,))
            row = cursor.fetchone()
            return json.loads(row[0]) if row else None
    
    def set_manifest(self, key: str, value: Dict[str, Any]):
        """Set manifest value."""
        with self.transaction() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO manifests (key, value_json)
                VALUES (?, ?)
            """, (key, json.dumps(value)))
    
    # Statistics
    def get_stats(self) -> Dict[str, Any]:
        """Get database statistics."""
        with self.connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("SELECT COUNT(*) FROM documents")
            doc_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM doc_versions")
            version_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM chunks")
            chunk_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM embeddings")
            embedding_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT MAX(updated_at) FROM documents")
            last_updated = cursor.fetchone()[0]
            
            return {
                "doc_count": doc_count,
                "version_count": version_count,
                "chunk_count": chunk_count,
                "embedding_count": embedding_count,
                "last_updated": last_updated,
            }
    
    def check_integrity(self) -> Dict[str, Any]:
        """Check database integrity."""
        with self.connection() as conn:
            cursor = conn.cursor()
            
            # Check for orphan chunks (chunks with non-existent doc_version)
            cursor.execute("""
                SELECT COUNT(*) FROM chunks c
                LEFT JOIN doc_versions dv ON c.doc_version_id = dv.id
                WHERE dv.id IS NULL
            """)
            orphan_chunks = cursor.fetchone()[0]
            
            # Check for orphan embeddings (embeddings with non-existent chunks)
            cursor.execute("""
                SELECT COUNT(*) FROM embeddings e
                LEFT JOIN chunks c ON e.chunk_id = c.id
                WHERE c.id IS NULL
            """)
            orphan_embeddings = cursor.fetchone()[0]
            
            # Check for orphan doc_versions
            cursor.execute("""
                SELECT COUNT(*) FROM doc_versions dv
                LEFT JOIN documents d ON dv.document_id = d.id
                WHERE d.id IS NULL
            """)
            orphan_versions = cursor.fetchone()[0]
            
            # Get total counts
            cursor.execute("SELECT COUNT(*) FROM chunks")
            total_chunks = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM documents")
            total_docs = cursor.fetchone()[0]
            
            return {
                "orphan_chunks": orphan_chunks,
                "orphan_embeddings": orphan_embeddings,
                "orphan_versions": orphan_versions,
                "total_chunks": total_chunks,
                "total_docs": total_docs,
                "is_valid": orphan_chunks == 0 and orphan_embeddings == 0 and orphan_versions == 0,
            }

# 
