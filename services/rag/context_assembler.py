"""
RAG Context Assembler - Main pipeline for retrieval-augmented generation.
Implements fast path (vector search) and slow path (LLM-routed DB query).
"""

from typing import Dict, Any, List, Optional
from datetime import datetime

from utilities.config_loader import get_config
from services.vector_db.models import RAGContext, SearchResult, VectorChunk
from services.vector_db.vector_store import get_vector_store
from services.vector_db.chunk_manager import get_chunk_manager
from services.graphql.client import get_graphql_client
from services.graphql.query_planner import get_query_planner_agent
from services.graphql.response_handler import get_response_handler


class ContextAssembler:
    """
    Main RAG pipeline coordinator.
    Assembles context from vector DB (fast path) and fresh DB queries (slow path).
    Uses LLM-based database agent to route queries to appropriate tables.
    """
    
    def __init__(self):
        self.config = get_config()
        self.vector_store = get_vector_store()
        self.chunk_manager = get_chunk_manager()
        self.graphql_client = get_graphql_client()
        self.query_planner = get_query_planner_agent()  # Query planner with schema introspection
        self.response_handler = get_response_handler()
        
        # Configuration
        self.similarity_threshold = self.config.get('vector_db.similarity_threshold', 0.65)
        self.max_results = self.config.get('rag.fast_path.max_results', 5)
        self.cache_results = self.config.get('rag.slow_path.cache_results', True)
        
        # Context source configuration
        self.use_static_kb = self.config.get('rag.context_sources.use_static_kb', True)
        self.use_dynamic_db = self.config.get('rag.context_sources.use_dynamic_db', True)
        self.use_fresh_db = self.config.get('rag.context_sources.use_fresh_db', True)
        self.combine_sources = self.config.get('rag.context_sources.combine_sources', True)
    
    def assemble_context(
        self,
        user_query: str,
        detected_entities: Optional[Dict[str, Any]] = None,
        force_slow_path: bool = False,
        # Override config settings for this call
        use_static_kb: Optional[bool] = None,
        use_dynamic_db: Optional[bool] = None,
        use_fresh_db: Optional[bool] = None,
        combine_sources: Optional[bool] = None
    ) -> RAGContext:
        """
        Assemble context for a user query using the RAG pipeline.
        
        Args:
            user_query: The user's query text
            detected_entities: Entities extracted from the query
            force_slow_path: Force fresh DB query regardless of vector results
            use_static_kb: Override config - use static KB (PDFs/docs)
            use_dynamic_db: Override config - use cached DB results
            use_fresh_db: Override config - use fresh DB queries
            combine_sources: Override config - combine all sources
            
        Returns:
            RAGContext with assembled context from all sources
        """
        detected_entities = detected_entities or {}
        context = RAGContext()
        
        # Use overrides or fall back to config
        _use_static_kb = use_static_kb if use_static_kb is not None else self.use_static_kb
        _use_dynamic_db = use_dynamic_db if use_dynamic_db is not None else self.use_dynamic_db
        _use_fresh_db = use_fresh_db if use_fresh_db is not None else self.use_fresh_db
        _combine_sources = combine_sources if combine_sources is not None else self.combine_sources
        
        print(f"📋 Context sources: static_kb={_use_static_kb}, dynamic_db={_use_dynamic_db}, fresh_db={_use_fresh_db}, combine={_combine_sources}")
        
        # Step 1: Fast path - check vector DB first
        if not force_slow_path and (_use_static_kb or _use_dynamic_db):
            vector_results = self._fast_path(user_query)
            
            # Separate and filter results by source based on config
            if _use_static_kb:
                context.static_kb_results = [r for r in vector_results if r.chunk.source == "static_kb"]
            if _use_dynamic_db:
                context.dynamic_db_results = [r for r in vector_results if r.chunk.source == "dynamic_db"]
            
            # Check if we have relevant results from enabled sources
            relevant_results = context.static_kb_results + context.dynamic_db_results
            has_relevant = any(r.is_relevant for r in relevant_results)
            
            if has_relevant:
                context.source_path = "fast"
                print(f"📚 Fast path: Found {len(relevant_results)} relevant results (static_kb: {len(context.static_kb_results)}, dynamic_db: {len(context.dynamic_db_results)})")
                
                # If not combining sources and we found results, return early
                if not _combine_sources:
                    return context
        
        # Step 2: Slow path - fresh database query using LLM agent
        if _use_fresh_db:
            print("🔍 Slow path: Using LLM agent to route query to database...")
            fresh_results = self._slow_path_with_agent(user_query, detected_entities)
            context.fresh_db_results = fresh_results
            
            if context.source_path != "fast":
                context.source_path = "slow"
            else:
                context.source_path = "combined"
        

        return context
    
    def _fast_path(self, query: str) -> List[SearchResult]:
        """
        Fast path: Search vector DB for relevant context.
        
        Args:
            query: Search query
            
        Returns:
            List of SearchResults from vector store
        """
        try:
            results = self.vector_store.search(
                query=query,
                k=self.max_results,
                include_expired=False
            )
            return results
        except Exception as e:
            print(f"⚠️ Fast path error: {e}")
            return []
    
    def _slow_path_with_agent(
        self,
        query: str,
        detected_entities: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Slow path: Use query planner to generate and execute GraphQL queries.
        
        Args:
            query: User query
            detected_entities: Extracted entities from intent detection
            
        Returns:
            List of normalized results
        """
        # Use query planner to generate a query plan and GraphQL query
        query_plan, graphql_query = self.query_planner.plan_query(
            user_query=query,
            detected_entities=detected_entities
        )
        
        print(f"  → Query plan: {query_plan.primary_table}, confidence: {query_plan.confidence:.2f}")
        print(f"  → Generated GraphQL query:")
        print(f"    {graphql_query.replace(chr(10), chr(10) + '    ')}")
        
        # Execute the generated GraphQL query
        raw_response = self.graphql_client.execute_graphql_query(graphql_query)
        print("Raw GraphQL Query response:", raw_response)
        
        if not raw_response.get("success"):
            print(f"  ⚠️ GraphQL query failed: {raw_response.get('error')}")
            return []
        
        # Normalize response
        query_type = raw_response.get("query_type", query_plan.primary_table)
        normalized = self.response_handler.normalize(raw_response, query_type)
        
        if not normalized.get("success"):
            return []
        
        # Cache results in vector DB for future fast path queries
        if self.cache_results and normalized.get("chunks"):
            print(f"  → Caching {len(normalized['chunks'])} chunks in vector DB...")
            self._cache_results(normalized["chunks"], query_type)
        
        return normalized.get("chunks", [])
    
    def _cache_results(self, chunks: List[Dict[str, Any]], table_name: str) -> None:
        """
        Cache normalized results in the vector DB if they meet storage criteria.
        
        Args:
            chunks: Normalized chunk data
            table_name: Name of the table that produced these chunks
        """
        for chunk_data in chunks:
            text = chunk_data.get("text", "")
            #print(f"  → Text(Data to store): {text}")
            entity_id = chunk_data.get("entity_id")
            
            # Check if should store
            should_store = self.chunk_manager.should_store(
                text=text,
                entity_type=table_name,
                is_user_specific=table_name == "orders",
                is_frequently_updated=False
            )
            
            if should_store:
                # Create and store vector chunks
                print(" → Storing criteria fulfilled, chunking text")
                vector_chunks = self.chunk_manager.chunk_text(
                    text=text,
                    entity_type=table_name,
                    entity_id=entity_id,
                    source="dynamic_db"
                )
                
                if vector_chunks:
                    self.vector_store.add_chunks(vector_chunks)
                    print(f"  ✓ Cached {len(vector_chunks)} chunks for {table_name}")
            else:
                print(" → Storing criteria not fulfilled, skipping chunking")
    
    def get_context_stats(self) -> Dict[str, Any]:
        """Get statistics about the context assembly."""
        vector_stats = self.vector_store.get_stats()
        return {
            "vector_store": vector_stats,
            "available_tables": self.graphql_client.get_available_tables(),
            "similarity_threshold": self.similarity_threshold
        }


class RetrievalRouter:
    """
    Decides between fast and slow path based on query characteristics.
    """
    
    def __init__(self):
        self.config = get_config()
        self.similarity_threshold = self.config.get('vector_db.similarity_threshold', 0.65)
    
    def should_use_slow_path(
        self,
        vector_results: List[SearchResult],
        query: str,
        detected_entities: Dict[str, Any]
    ) -> bool:
        """
        Determine if slow path should be used.
        
        Returns True if:
        - No relevant vector results
        - Vector results are stale (expired)
        - Query involves new/unseen entities
        """
        # No results at all
        if not vector_results:
            return True
        
        # No results above threshold
        relevant_results = [r for r in vector_results if r.is_relevant]
        if not relevant_results:
            return True
        
        # All results are expired
        non_expired = [r for r in relevant_results if not r.chunk.is_expired]
        if not non_expired:
            return True
        
        # Query mentions specific entity ID not in results
        entity_id = detected_entities.get("entity_id") or detected_entities.get("id")
        if entity_id:
            has_matching_entity = any(
                r.chunk.entity_id == entity_id for r in relevant_results
            )
            if not has_matching_entity:
                return True
        
        return False


# Global instances
_context_assembler = None
_retrieval_router = None


def get_context_assembler() -> ContextAssembler:
    """Get the global context assembler instance."""
    global _context_assembler
    if _context_assembler is None:
        _context_assembler = ContextAssembler()
    return _context_assembler


def get_retrieval_router() -> RetrievalRouter:
    """Get the global retrieval router instance."""
    global _retrieval_router
    if _retrieval_router is None:
        _retrieval_router = RetrievalRouter()
    return _retrieval_router
