"""Compatibility layer for FileRegistry using unified DB."""
import hashlib
import json
from pathlib import Path
from typing import List, Optional, Dict
from rag.scanner import FileInfo
from rag.db import RAGDatabase


class FileRegistry:
    """Compatibility layer for FileRegistry using unified DB schema."""
    
    def __init__(self, db):
        """Initialize registry with unified database.
        
        Args:
            db: RAGDatabase instance or Path to database file (for backward compatibility)
        """
        if isinstance(db, Path) or isinstance(db, str):
            # Backward compatibility: accept Path or str
            self.db = RAGDatabase(Path(db))
        else:
            # Assume it's a RAGDatabase instance
            self.db = db
    
    def get_file(self, path: Path) -> Optional[Dict]:
        """Get file record by path."""
        doc = self.db.get_document(path)
        if doc:
            # Convert to old format for compatibility
            return {
                "path": doc["path"],
                "size": doc["size_bytes"],
                "mtime": None,  # Will be in doc_versions
                "sha256": None,  # Will be in doc_versions
                "file_type": doc["doc_type"],
                "indexed_at": doc["updated_at"],
            }
        return None
    
    def register_file(self, file_info: FileInfo, indexed_at: Optional[float] = None):
        """Register or update file in registry."""
        # Create or update document
        doc_id = self.db.create_or_update_document(
            path=file_info.path,
            doc_type=file_info.file_type,
            size_bytes=file_info.size,
        )
    
    def is_file_changed(self, file_info: FileInfo) -> bool:
        """Check if file has changed since last indexing."""
        doc = self.db.get_document(file_info.path)
        if doc is None:
            return True
        
        # Check if there's a doc_version with matching sha256
        doc_version = self.db.get_doc_version(doc["id"], file_info.sha256)
        if doc_version is None:
            return True
        
        # Check if mtime changed
        return doc_version["mtime"] != file_info.mtime
    
    def get_changed_files(self, scanned_files: List[FileInfo]) -> List[FileInfo]:
        """Filter scanned files to only those that changed."""
        changed = []
        for file_info in scanned_files:
            if self.is_file_changed(file_info):
                changed.append(file_info)
        return changed
    
    def register_chunk(
        self,
        chunk_id: str,
        file_path: Path,
        chunk_hash: str,
        chunk_text: str,
        start_line: Optional[int] = None,
        end_line: Optional[int] = None,
        start_offset: Optional[int] = None,
        end_offset: Optional[int] = None,
    ):
        """Register a chunk (legacy method - use DB directly in new code).
        
        Note: This method is kept for compatibility but should be replaced
        with direct DB calls in the indexing pipeline.
        """
        # This is a compatibility method - actual chunk registration
        # should be done via db.create_chunk() in the indexing pipeline
        # We'll keep this for now but it won't be used in new code
        pass
    
    def chunk_exists(self, chunk_hash: str) -> bool:
        """Check if chunk with given hash already exists (legacy method)."""
        # This method is kept for compatibility but should be replaced
        # with db.chunk_exists() in new code
        # For now, return False to allow indexing
        return False
    
    def get_chunk_metadata(self, chunk_id: str) -> Optional[Dict]:
        """Get chunk metadata by chunk_id (legacy method).
        
        Note: In new code, use db.get_chunk(chunk_id) where chunk_id is an int.
        This method tries to handle both string and int chunk_ids for compatibility.
        """
        # Try to convert to int if it's a numeric string
        try:
            chunk_id_int = int(chunk_id)
        except (ValueError, TypeError):
            # Legacy string chunk_id - not supported in new schema
            return None
        
        chunk = self.db.get_chunk(chunk_id_int)
        if chunk:
            # Convert to old format for compatibility
            loc = json.loads(chunk["loc_json"])
            return {
                "chunk_id": str(chunk["id"]),
                "file_path": chunk["document_path"],
                "chunk_hash": chunk["chunk_hash"],
                "chunk_text": chunk["content"],
                "start_line": loc.get("line_start"),
                "end_line": loc.get("line_end"),
                "start_offset": loc.get("char_start"),
                "end_offset": loc.get("char_end"),
                "created_at": chunk["created_at"],
            }
        return None
    
    def delete_file_chunks(self, file_path: Path):
        """Delete all chunks for a file (when re-indexing)."""
        doc = self.db.get_document(file_path)
        if doc:
            # Get all doc_versions for this document
            with self.db.connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT id FROM doc_versions WHERE document_id = ?
                """, (doc["id"],))
                versions = cursor.fetchall()
                
                # Delete chunks for each version
                for version_row in versions:
                    self.db.delete_doc_version_chunks(version_row[0])
    
    def get_stats(self) -> Dict:
        """Get registry statistics."""
        stats = self.db.get_stats()
        return {
            "file_count": stats["doc_count"],
            "chunk_count": stats["chunk_count"],
            "last_indexed": stats["last_updated"],
        }
    
    def check_integrity(self) -> Dict:
        """
        Check database integrity.
        
        Returns:
            Dict with integrity check results
        """
        integrity = self.db.check_integrity()
        return {
            "orphan_chunks": integrity["orphan_chunks"],
            "orphan_embeddings": integrity["orphan_embeddings"],
            "orphan_versions": integrity["orphan_versions"],
            "total_chunks": integrity["total_chunks"],
            "total_files": integrity["total_docs"],
            "is_valid": integrity["is_valid"],
        }

