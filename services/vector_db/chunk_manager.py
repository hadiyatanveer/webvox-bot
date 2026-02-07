"""
Chunk manager for text chunking and storage policy decisions.
Handles text splitting, embedding, and deciding what to store.
"""

import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional

from utilities.config_loader import get_config
from services.vector_db.models import VectorChunk
from services.vector_db.embedding_service import get_embedding_service


class ChunkManager:
    """Manages text chunking and storage policy for the vector store."""
    
    def __init__(self):
        self.config = get_config()
        self.embedding_service = get_embedding_service()
        
        # Chunking settings
        self.min_tokens = self.config.get('vector_db.chunking.min_tokens', 512)
        self.max_tokens = self.config.get('vector_db.chunking.max_tokens', 2048)
        self.overlap_tokens = self.config.get('vector_db.chunking.overlap_tokens', 50)
        
        # Storage policy settings
        self.min_response_size = self.config.get(
            'vector_db.storage_policy.min_response_size_bytes', 2048
        )
        self.high_freq_entities = self.config.get(
            'vector_db.storage_policy.high_frequency_entities', 
            ["products", "orders", "policies", "menu_items"]
        )
        self.exclude_entities = self.config.get(
            'vector_db.storage_policy.exclude_entities',
            ["user_address", "payment_info", "personal_data"]
        )
    
    def chunk_text(
        self,
        text: str,
        entity_type: str,
        entity_id: Optional[str] = None,
        source: str = "dynamic_db",
        metadata: Optional[Dict[str, Any]] = None,
        batch_size: int = 10  # Process embeddings in batches to avoid memory issues
    ) -> List[VectorChunk]:
        """
        Split text into chunks and create VectorChunk objects.
        
        Args:
            text: Text to chunk
            entity_type: Type of entity (e.g., "product", "order")
            entity_id: Optional entity ID
            source: Source type ("static_kb" or "dynamic_db")
            metadata: Additional metadata
            batch_size: Number of chunks to embed at once (prevents memory overflow)
            
        Returns:
            List of VectorChunk objects
        """
        if not text or not text.strip():
            return []
        
        # Get TTL based on source
        if source == "static_kb":
            ttl_days = self.config.get('vector_db.ttl.static_kb_days', 30)
        else:
            ttl_days = self.config.get('vector_db.ttl.dynamic_db_days', 1)
        
        # Split into chunks
        chunks_text = self._split_text(text)
        total_chunks = len(chunks_text)
        
        print(f"  📄 Splitting into {total_chunks} chunks...")
        
        chunks = []
        
        # Process in batches to avoid memory overflow
        for batch_start in range(0, total_chunks, batch_size):
            batch_end = min(batch_start + batch_size, total_chunks)
            batch_texts = chunks_text[batch_start:batch_end]
            
            print(f"  ⏳ Embedding batch {batch_start//batch_size + 1}/{(total_chunks + batch_size - 1)//batch_size} (chunks {batch_start+1}-{batch_end})...")
            
            # Embed this batch only
            batch_embeddings = self.embedding_service.embed_texts(batch_texts)
            
            # Create VectorChunk objects for this batch
            for i, (chunk_text, embedding) in enumerate(zip(batch_texts, batch_embeddings)):
                chunk = VectorChunk(
                    chunk_id=f"{entity_type}_{entity_id or 'none'}_{uuid.uuid4().hex[:8]}",
                    text=chunk_text,
                    embedding=embedding,
                    entity_type=entity_type,
                    entity_id=entity_id,
                    source=source,
                    timestamp=datetime.now(),
                    ttl_days=ttl_days,
                    metadata=metadata or {}
                )
                chunks.append(chunk)
        
        print(f"  ✓ Created {len(chunks)} chunks with embeddings")
        return chunks
    
    def _split_text(self, text: str) -> List[str]:
        """
        Split text into chunks based on token limits.
        Uses a simple word-based approximation (1 token ≈ 0.75 words).
        """
        # Approximate: 1 token ≈ 0.75 words (conservative estimate)
        words_per_token = 0.75
        max_words = int(self.max_tokens * words_per_token)
        overlap_words = int(self.overlap_tokens * words_per_token)
        
        words = text.split()
        
        if len(words) <= max_words:
            return [text]
        
        chunks = []
        start = 0
        
        while start < len(words):
            end = min(start + max_words, len(words))
            chunk_words = words[start:end]
            chunks.append(" ".join(chunk_words))
            
            # Move start with overlap
            start = end - overlap_words
            if start >= len(words):
                break
        
        return chunks
    
    def should_store(
        self,
        text: str,
        entity_type: str,
        is_user_specific: bool = False,
        is_frequently_updated: bool = False
    ) -> bool:
        """
        Determine if a response should be stored in the vector DB.
        
        Args:
            text: The response text
            entity_type: Type of entity
            is_user_specific: Whether this is user-specific data
            is_frequently_updated: Whether this data changes frequently
            
        Returns:
            True if should store, False otherwise
        """
        # Never store excluded entities
        if entity_type in self.exclude_entities:
            print(" → Excluded entity type, skipping chunking")
            return False
        
        # Never store user-specific information
        if is_user_specific:    
            print(" → User-specific information, skipping chunking")
            return False
        
        # Don't store frequently updated data
        if is_frequently_updated:
            print(" → Frequently updated data, skipping chunking")
            return False
        
        # Check size threshold
        if len(text.encode('utf-8')) < self.min_response_size:
            print(" → Response size too small, skipping chunking")
            return False
        
        # Prefer high-frequency entities
        if entity_type in self.high_freq_entities:
            print(" → High-frequency entity, storing chunking")
            return True
        
        # Default: store if meets size threshold
        print(" → Default: storing chunking")
        return True
    
    def normalize_entity_text(
        self,
        entity_data: Dict[str, Any],
        entity_type: str
    ) -> str:
        """
        Convert entity data to normalized text for embedding.
        
        Args:
            entity_data: Raw entity data dictionary
            entity_type: Type of entity
            
        Returns:
            Normalized text representation
        """
        pii_fields = self.config.get('graphql.normalize.pii_fields', [])
        system_fields = self.config.get('graphql.normalize.remove_system_fields', [])
        
        # Remove unwanted fields
        filtered_data = {}
        for key, value in entity_data.items():
            if key in pii_fields or key in system_fields:
                continue
            filtered_data[key] = value
        
        # Convert to readable text
        lines = [f"{entity_type.replace('_', ' ').title()}:"]
        
        for key, value in filtered_data.items():
            if value is not None:
                # Handle nested objects
                if isinstance(value, dict):
                    value = self._flatten_dict(value)
                elif isinstance(value, list):
                    value = ", ".join(str(v) for v in value)
                
                key_readable = key.replace('_', ' ').title()
                lines.append(f"  {key_readable}: {value}")
        
        return "\n".join(lines)
    
    def _flatten_dict(self, d: Dict[str, Any], prefix: str = "") -> str:
        """Flatten a nested dictionary to a string."""
        items = []
        for key, value in d.items():
            full_key = f"{prefix}{key}" if prefix else key
            if isinstance(value, dict):
                items.append(self._flatten_dict(value, f"{full_key}."))
            else:
                items.append(f"{full_key}={value}")
        return ", ".join(items)


# Global chunk manager instance
_chunk_manager = None


def get_chunk_manager() -> ChunkManager:
    """Get the global chunk manager instance."""
    global _chunk_manager
    if _chunk_manager is None:
        _chunk_manager = ChunkManager()
    return _chunk_manager
