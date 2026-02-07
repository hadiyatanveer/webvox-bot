"""
Data models for Vector DB operations.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, List, Optional


@dataclass
class VectorChunk:
    """Represents a chunk of text with its embedding and metadata."""
    
    chunk_id: str
    text: str
    embedding: List[float]
    entity_type: str               # e.g., "product", "order", "menu_item", "faq"
    entity_id: Optional[str]       # ID of the entity this chunk belongs to
    source: str                    # "static_kb" or "dynamic_db"
    timestamp: datetime
    ttl_days: int
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def is_expired(self) -> bool:
        """Check if this chunk has expired based on TTL."""
        from datetime import timedelta
        expiry_date = self.timestamp + timedelta(days=self.ttl_days)
        return datetime.now() > expiry_date
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "chunk_id": self.chunk_id,
            "text": self.text,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "source": self.source,
            "timestamp": self.timestamp.isoformat(),
            "ttl_days": self.ttl_days,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any], embedding: List[float]) -> 'VectorChunk':
        """Create from dictionary."""
        return cls(
            chunk_id=data["chunk_id"],
            text=data["text"],
            embedding=embedding,
            entity_type=data["entity_type"],
            entity_id=data.get("entity_id"),
            source=data["source"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            ttl_days=data["ttl_days"],
            metadata=data.get("metadata", {})
        )


@dataclass
class SearchResult:
    """Result from a vector similarity search."""
    
    chunk: VectorChunk
    similarity_score: float
    
    @property
    def is_relevant(self) -> bool:
        """Check if this result meets the relevance threshold."""
        from utilities.config_loader import get_config
        threshold = get_config().get('vector_db.similarity_threshold', 0.65)
        return self.similarity_score >= threshold


@dataclass
class RAGContext:
    """Assembled context for RAG response generation."""
    
    static_kb_results: List[SearchResult] = field(default_factory=list)
    dynamic_db_results: List[SearchResult] = field(default_factory=list)
    fresh_db_results: List[Dict[str, Any]] = field(default_factory=list)
    source_path: str = "fast"  # "fast" or "slow"
    
    def get_combined_context(self, max_length: int = 4000) -> str:
        """Combine all context sources into a single string."""
        context_parts = []
        
        # Add static KB context
        for result in self.static_kb_results:
            if not result.chunk.is_expired:
                context_parts.append(f"[Knowledge Base] {result.chunk.text}")
        
        # Add dynamic DB context
        for result in self.dynamic_db_results:
            if not result.chunk.is_expired:
                context_parts.append(f"[Database] {result.chunk.text}")
        
        # Add fresh DB results
        for result in self.fresh_db_results:
            context_parts.append(f"[Fresh Query] {result.get('text', str(result))}")
        
        combined = "\n\n".join(context_parts)
        
        # Truncate if too long
        if len(combined) > max_length:
            combined = combined[:max_length] + "..."
        
        return combined
    
    @property
    def has_relevant_results(self) -> bool:
        """Check if any relevant results were found."""
        # Check each source
        static_relevant = [r for r in self.static_kb_results if r.is_relevant]
        dynamic_relevant = [r for r in self.dynamic_db_results if r.is_relevant]
        
        has_static = len(static_relevant) > 0
        has_dynamic = len(dynamic_relevant) > 0
        has_fresh = len(self.fresh_db_results) > 0
        
        # Also consider if we have ANY results (even below threshold) as a fallback
        has_any_static = len(self.static_kb_results) > 0
        has_any_dynamic = len(self.dynamic_db_results) > 0
        
        # Debug logging
        print(f"  📊 RAGContext check: static_kb={has_static} ({len(static_relevant)}/{len(self.static_kb_results)}), "
              f"dynamic_db={has_dynamic} ({len(dynamic_relevant)}/{len(self.dynamic_db_results)}), "
              f"fresh_db={has_fresh} ({len(self.fresh_db_results)})")
        
        # Return true if we have relevant results OR if we have any results at all
        # This ensures we don't return "no_results" when we actually found something
        return has_static or has_dynamic or has_fresh or has_any_static or has_any_dynamic
