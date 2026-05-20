"""
FAISS-based vector store for similarity search.
Manages dual indexes for static KB and dynamic DB content.
"""

import os
import json
import pickle
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import numpy as np

try:
    import faiss
except ImportError:
    faiss = None
    print("⚠️ FAISS not available. Vector store will use numpy-based fallback.")

from utilities.config_loader import get_config
from services.vector_db.models import VectorChunk, SearchResult
from services.vector_db.embedding_service import get_embedding_service


class VectorStore:
    """
    FAISS-based vector store with support for dual indexes.
    Manages static KB and dynamic DB indexes separately.
    """
    
    def __init__(self, store_path: Optional[str] = None):
        """
        Initialize the vector store.
        
        Args:
            store_path: Path to store/load index files. Defaults to data/vector_db/
        """
        self.config = get_config()
        self.embedding_service = get_embedding_service()
        self.dimension = self.embedding_service.dimension
        
        # Set store path
        if store_path:
            self.store_path = Path(store_path)
        else:
            project_root = Path(__file__).parent.parent.parent
            self.store_path = project_root / "data" / "vector_db"
        
        self.store_path.mkdir(parents=True, exist_ok=True)
        
        # Initialize indexes
        self._static_index = None
        self._dynamic_index = None
        self._static_metadata: Dict[int, Dict] = {}
        self._dynamic_metadata: Dict[int, Dict] = {}
        
        # Load existing indexes if available
        self._load_indexes()
    
    def _create_index(self) -> 'faiss.IndexFlatIP':
        """Create a new FAISS index using inner product (for cosine similarity with normalized vectors)."""
        if faiss is None:
            return None
        return faiss.IndexFlatIP(self.dimension)
    
    def _load_indexes(self) -> None:
        """Load existing indexes from disk."""
        # Load static KB index
        static_index_path = self.store_path / "static_kb.index"
        static_meta_path = self.store_path / "static_kb_meta.json"
        
        if static_index_path.exists() and faiss is not None:
            self._static_index = faiss.read_index(str(static_index_path))
            if static_meta_path.exists():
                with open(static_meta_path, 'r') as f:
                    self._static_metadata = {int(k): v for k, v in json.load(f).items()}
        else:
            self._static_index = self._create_index()
        
        # Load dynamic DB index
        dynamic_index_path = self.store_path / "dynamic_db.index"
        dynamic_meta_path = self.store_path / "dynamic_db_meta.json"
        
        if dynamic_index_path.exists() and faiss is not None:
            self._dynamic_index = faiss.read_index(str(dynamic_index_path))
            if dynamic_meta_path.exists():
                with open(dynamic_meta_path, 'r') as f:
                    self._dynamic_metadata = {int(k): v for k, v in json.load(f).items()}
        else:
            self._dynamic_index = self._create_index()
    
    def _save_indexes(self) -> None:
        """Save indexes to disk."""
        if faiss is None:
            return
        
        # Save static KB index
        if self._static_index is not None:
            faiss.write_index(self._static_index, str(self.store_path / "static_kb.index"))
            with open(self.store_path / "static_kb_meta.json", 'w') as f:
                json.dump(self._static_metadata, f)
        
        # Save dynamic DB index
        if self._dynamic_index is not None:
            faiss.write_index(self._dynamic_index, str(self.store_path / "dynamic_db.index"))
            with open(self.store_path / "dynamic_db_meta.json", 'w') as f:
                json.dump(self._dynamic_metadata, f)
    
    def add_chunk(self, chunk: VectorChunk) -> None:
        """
        Add a single chunk to the appropriate index.
        
        Args:
            chunk: VectorChunk to add
        """
        # Determine which index to use
        if chunk.source == "static_kb":
            index = self._static_index
            metadata = self._static_metadata
        else:
            index = self._dynamic_index
            metadata = self._dynamic_metadata
        
        if index is None:
            print("⚠️ FAISS not available, cannot add chunk")
            return
        
        # Check for duplicates - skip if chunk_id or text already exists
        for existing_meta in metadata.values():
            if existing_meta.get("chunk_id") == chunk.chunk_id:
                print(f"  ⏭️ Skipping duplicate chunk: {chunk.chunk_id[:30]}...")
                return
            # Also check text similarity to avoid semantic duplicates
            if existing_meta.get("text") == chunk.text:
                print(f"  ⏭️ Skipping duplicate text chunk")
                return
        
        # Normalize the embedding for cosine similarity
        embedding = np.array([chunk.embedding], dtype=np.float32)
        faiss.normalize_L2(embedding)
        
        # Get the next index ID
        idx = index.ntotal
        
        # Add to index
        index.add(embedding)
        
        # Store metadata
        metadata[idx] = chunk.to_dict()
        
        # Auto-save
        self._save_indexes()
    
    def add_chunks(self, chunks: List[VectorChunk]) -> None:
        """
        Add multiple chunks to the appropriate indexes.
        Checks for duplicates before adding.
        
        Args:
            chunks: List of VectorChunks to add
        """
        # Separate chunks by source
        static_chunks = [c for c in chunks if c.source == "static_kb"]
        dynamic_chunks = [c for c in chunks if c.source != "static_kb"]
        
        # Filter out duplicates
        static_chunks = self._filter_duplicates(static_chunks, self._static_metadata)
        dynamic_chunks = self._filter_duplicates(dynamic_chunks, self._dynamic_metadata)
        
        # Add static KB chunks
        if static_chunks and self._static_index is not None:
            embeddings = np.array([c.embedding for c in static_chunks], dtype=np.float32)
            faiss.normalize_L2(embeddings)
            
            start_idx = self._static_index.ntotal
            self._static_index.add(embeddings)
            
            for i, chunk in enumerate(static_chunks):
                self._static_metadata[start_idx + i] = chunk.to_dict()
        
        # Add dynamic DB chunks
        if dynamic_chunks and self._dynamic_index is not None:
            embeddings = np.array([c.embedding for c in dynamic_chunks], dtype=np.float32)
            faiss.normalize_L2(embeddings)
            
            start_idx = self._dynamic_index.ntotal
            self._dynamic_index.add(embeddings)
            
            for i, chunk in enumerate(dynamic_chunks):
                self._dynamic_metadata[start_idx + i] = chunk.to_dict()
        
        # Save indexes
        self._save_indexes()
    
    def _filter_duplicates(self, chunks: List[VectorChunk], metadata: Dict) -> List[VectorChunk]:
        """Filter out chunks that already exist in the metadata."""
        existing_texts = {m.get("text") for m in metadata.values()}
        existing_ids = {m.get("chunk_id") for m in metadata.values()}
        
        filtered = []
        for chunk in chunks:
            if chunk.chunk_id in existing_ids:
                continue
            if chunk.text in existing_texts:
                continue
            filtered.append(chunk)
            existing_texts.add(chunk.text)  # Prevent duplicates within same batch
        
        if len(filtered) < len(chunks):
            print(f"  ⏭️ Skipped {len(chunks) - len(filtered)} duplicate chunks")
        
        return filtered
    
    def search(
        self,
        query: str,
        source: Optional[str] = None,
        k: int = 5,
        include_expired: bool = False
    ) -> List[SearchResult]:
        """
        Search for similar chunks.
        
        Args:
            query: Search query text
            source: Optional source filter ("static_kb" or "dynamic_db")
            k: Number of results to return
            include_expired: Whether to include expired chunks
            
        Returns:
            List of SearchResults sorted by similarity
        """
        # Get query embedding
        query_embedding = np.array([self.embedding_service.embed_text(query)], dtype=np.float32)
        faiss.normalize_L2(query_embedding)
        
        results = []
        
        # Search static KB
        if source is None or source == "static_kb":
            static_results = self._search_index(
                self._static_index, 
                self._static_metadata,
                query_embedding, 
                k,
                include_expired
            )
            results.extend(static_results)
        
        # Search dynamic DB
        if source is None or source == "dynamic_db":
            dynamic_results = self._search_index(
                self._dynamic_index,
                self._dynamic_metadata,
                query_embedding,
                k,
                include_expired
            )
            results.extend(dynamic_results)
        
        # Sort by similarity and return top k
        results.sort(key=lambda x: x.similarity_score, reverse=True)
        
        # Debug: Show top similarity scores
        threshold = self.config.get('vector_db.similarity_threshold', 0.65)
        if results:
            print(f"   🔎 Vector search scores (threshold={threshold}):")
            for i, r in enumerate(results[:5]):
                status = "✓" if r.similarity_score >= threshold else "✗"
                text_preview = r.chunk.text[:50].replace('\n', ' ') + "..."
                print(f"      {status} {r.similarity_score:.3f}: {text_preview}")
        
        return results[:k]
    
    def _search_index(
        self,
        index,
        metadata: Dict[int, Dict],
        query_embedding: np.ndarray,
        k: int,
        include_expired: bool
    ) -> List[SearchResult]:
        """Search a single index."""
        if index is None or index.ntotal == 0:
            return []
        
        # Search index
        actual_k = min(k * 2, index.ntotal)  # Get extra results for filtering
        scores, indices = index.search(query_embedding, actual_k)
        
        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0:  # FAISS returns -1 for empty slots
                continue
            
            if idx not in metadata:
                continue
            
            meta = metadata[idx]
            
            # Reconstruct chunk (embedding not stored in metadata)
            chunk = VectorChunk(
                chunk_id=meta["chunk_id"],
                text=meta["text"],
                embedding=[],  # Not needed for results
                entity_type=meta["entity_type"],
                entity_id=meta.get("entity_id"),
                source=meta["source"],
                timestamp=datetime.fromisoformat(meta["timestamp"]),
                ttl_days=meta["ttl_days"],
                metadata=meta.get("metadata", {})
            )
            
            # Skip expired unless requested
            if not include_expired and chunk.is_expired:
                continue
            
            results.append(SearchResult(
                chunk=chunk,
                similarity_score=float(score)
            ))
        
        return results
    
    def remove_expired(self) -> int:
        """
        Remove all expired chunks from indexes.
        Note: FAISS doesn't support deletion, so this rebuilds the indexes.
        
        Returns:
            Number of chunks removed
        """
        removed_count = 0
        
        # Rebuild static KB index
        removed_count += self._rebuild_index_without_expired("static_kb")
        
        # Rebuild dynamic DB index
        removed_count += self._rebuild_index_without_expired("dynamic_db")
        
        return removed_count
    
    def _rebuild_index_without_expired(self, source: str) -> int:
        """
        Rebuild an index excluding expired chunks.
        Re-embeds all valid chunks and writes a fresh FAISS index to disk.
        """
        if source == "static_kb":
            old_metadata = self._static_metadata
        else:
            old_metadata = self._dynamic_metadata

        # Separate valid from expired entries
        valid_entries = []
        removed_count = 0

        for meta in old_metadata.values():
            timestamp = datetime.fromisoformat(meta["timestamp"])
            ttl_days = meta["ttl_days"]

            from datetime import timedelta
            if datetime.now() > timestamp + timedelta(days=ttl_days):
                removed_count += 1
            else:
                valid_entries.append(meta)

        if removed_count == 0:
            return 0  # Nothing to do

        # Short-circuit: if every chunk expired, swap in a blank index and return
        if not valid_entries:
            new_index = self._create_index()
            if source == "static_kb":
                self._static_index = new_index
                self._static_metadata = {}
            else:
                self._dynamic_index = new_index
                self._dynamic_metadata = {}
            self._save_indexes()
            print(f"  ♻️ All {removed_count} chunks in {source} expired — index cleared")
            return removed_count

        # Build a fresh index from the surviving entries
        new_index = self._create_index()
        new_metadata: Dict[int, Dict] = {}

        if new_index is not None and valid_entries:
            embedding_service = get_embedding_service()
            texts = [m["text"] for m in valid_entries]
            embeddings = np.array(
                [embedding_service.embed_text(t) for t in texts], dtype=np.float32
            )
            faiss.normalize_L2(embeddings)
            new_index.add(embeddings)
            for i, meta in enumerate(valid_entries):
                new_metadata[i] = meta

        # Swap in the rebuilt index
        if source == "static_kb":
            self._static_index = new_index
            self._static_metadata = new_metadata
        else:
            self._dynamic_index = new_index
            self._dynamic_metadata = new_metadata

        self._save_indexes()
        print(f"  ♻️ Rebuilt {source} index: removed {removed_count} expired chunks, kept {len(valid_entries)}")
        return removed_count
    
    def clear_index(self, source: Optional[str] = None) -> None:
        """
        Clear an index.
        
        Args:
            source: "static_kb", "dynamic_db", or None for both
        """
        if source is None or source == "static_kb":
            self._static_index = self._create_index()
            self._static_metadata = {}
        
        if source is None or source == "dynamic_db":
            self._dynamic_index = self._create_index()
            self._dynamic_metadata = {}
        
        self._save_indexes()
    
    def get_stats(self) -> Dict[str, int]:
        """Get statistics about the vector store."""
        return {
            "static_kb_count": self._static_index.ntotal if self._static_index else 0,
            "dynamic_db_count": self._dynamic_index.ntotal if self._dynamic_index else 0,
            "total_count": (
                (self._static_index.ntotal if self._static_index else 0) +
                (self._dynamic_index.ntotal if self._dynamic_index else 0)
            )
        }


# Global vector store instance
_vector_store = None


def get_vector_store() -> VectorStore:
    """Get the global vector store instance."""
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore()
    return _vector_store
