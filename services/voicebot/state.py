# services/voicebot/state.py
from typing import TypedDict, Dict, Any, Optional, List

class GraphState(TypedDict):
    """
    Represents the state of our voicebot graph.
    This state flows through every node and is persisted.
    """
    user_input: str
    session_id: str
    user_context: Dict[str, Any]
    
    # Intent Detection
    intent_data: Dict[str, Any]
    action_data: Optional[Dict[str, Any]]
    needs_clarification: bool
    
    # RAG Context
    vector_results: Optional[List[Any]]
    requires_graphql: bool
    rag_context: Optional[Dict[str, Any]]
    
    # --- GraphQL Retry State ---
    graphql_retries: int
    graphql_error: Optional[str]
    previous_graphql_query: Optional[str]
    
    # Output
    mutation_result: Optional[Dict[str, Any]]
    final_response: str
    error: Optional[str]