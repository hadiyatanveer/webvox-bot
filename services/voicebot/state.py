# services/voicebot/state.py
from typing import TypedDict, Dict, Any, Optional, List, Annotated


def _append_messages(
    existing: Optional[List[Dict[str, str]]],
    new: Optional[List[Dict[str, str]]]
) -> List[Dict[str, str]]:
    """
    Custom reducer for chat_history.

    LangGraph calls this reducer on every state update, passing:
      - existing: the current persisted list (or None on the very first turn)
      - new:      whatever the node returned for this key (or None if the node
                  didn't touch chat_history at all)

    We simply append new messages to the existing list, capping at the last
    MAX_HISTORY turns so the prompt never grows unbounded.
    """
    MAX_HISTORY = 20  # keep the last 20 messages (~10 turns)
    base = existing or []
    additions = new or []
    combined = base + additions
    # Trim from the front so we always keep the most recent messages
    return combined[-MAX_HISTORY:]


class GraphState(TypedDict):
    """
    Represents the state of our voicebot graph.
    This state flows through every node and is persisted by the MemorySaver
    checkpointer, keyed by session_id (thread_id).
    """
    user_input: str
    session_id: str
    user_context: Dict[str, Any]

    # ── Conversation History ──────────────────────────────────────────────────
    # A list of {"role": "user"|"assistant", "content": "..."} dicts.
    # The _append_messages reducer means nodes only need to RETURN the NEW
    # messages for the current turn; LangGraph merges them automatically.
    chat_history: Annotated[List[Dict[str, str]], _append_messages]

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