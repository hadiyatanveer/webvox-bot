# services/voicebot/state.py
from typing import TypedDict, Dict, Any, Optional

class GraphState(TypedDict):
    """
    Represents the state of our voicebot graph.
    This state flows through every node.
    """
    user_input: str
    session_id: str
    
    # Intent Detection
    intent_data: Dict[str, Any]
    needs_clarification: bool
    
    # RAG Context
    vector_results: Optional[Any]
    requires_graphql: bool
    rag_context: Optional[Dict[str, Any]]
    
    # Output
    final_response: str
    error: Optional[str]