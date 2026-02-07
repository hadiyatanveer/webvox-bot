"""
Information Retrieval Module for WebVox.
Main handler for retrieve_information intent.
"""

from typing import Dict, Any, Optional

from utilities.config_loader import get_config
from services.rag.context_assembler import get_context_assembler
from services.vector_db.models import RAGContext


class InformationRetriever:
    """
    Handles information retrieval for user queries.
    Coordinates RAG pipeline and formats results.
    """
    
    def __init__(self):
        self.config = get_config()
        self.context_assembler = get_context_assembler()
    
    def retrieve(
        self,
        user_query: str,
        detected_entities: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Retrieve information for a user query.
        
        Args:
            user_query: The user's query text
            detected_entities: Entities extracted from the query
            
        Returns:
            Retrieval result with context and metadata
        """
        try:
            # Assemble context using RAG pipeline
            context = self.context_assembler.assemble_context(
                user_query=user_query,
                detected_entities=detected_entities
            )
            
            # Check if we got relevant results
            if not context.has_relevant_results:
                return self._no_results_response(user_query)
            
            # Format the context for LLM
            combined_context = context.get_combined_context(
                max_length=self.config.get('response.max_context_length', 4000)
            )
            
            return {
                "status": "success",
                "context": combined_context,
                "source_path": context.source_path,
                "metadata": {
                    "static_kb_count": len(context.static_kb_results),
                    "dynamic_db_count": len(context.dynamic_db_results),
                    "fresh_db_count": len(context.fresh_db_results)
                }
            }
            
        except Exception as e:
            print(f"⚠️ Information retrieval error: {e}")
            return self._error_response(str(e))
    
    def _no_results_response(self, query: str) -> Dict[str, Any]:
        """Generate response when no results found."""
        fallback_msg = self.config.get(
            'response.fallback.no_results',
            "I couldn't find the information you're looking for. Could you try rephrasing?"
        )
        
        return {
            "status": "no_results",
            "context": "",
            "message": fallback_msg,
            "metadata": {
                "query": query,
                "needs_clarification": True
            }
        }
    
    def _error_response(self, error: str) -> Dict[str, Any]:
        """Generate response for errors."""
        fallback_msg = self.config.get(
            'response.fallback.service_error',
            "I'm having trouble accessing the information right now."
        )
        
        return {
            "status": "error",
            "context": "",
            "message": fallback_msg,
            "metadata": {
                "error": error
            }
        }


# Global instance
_information_retriever = None


def get_information_retriever() -> InformationRetriever:
    """Get the global information retriever instance."""
    global _information_retriever
    if _information_retriever is None:
        _information_retriever = InformationRetriever()
    return _information_retriever
