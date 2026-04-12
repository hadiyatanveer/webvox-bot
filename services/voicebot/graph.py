# services/voicebot/graph.py
from langgraph.graph import StateGraph, START, END
from typing import Literal

from services.voicebot.state import GraphState
from services.voicebot.nodes import (
    detect_intent_node,
    vector_search_node,
    graphql_planning_node,
    generate_response_node
)

# --- CONDITIONAL EDGE FUNCTIONS ---

def route_after_intent(state: GraphState) -> Literal["generate_response", "vector_search"]:
    """If the intent is vague, skip RAG and ask for clarification."""
    if state.get("needs_clarification"):
        print("---EDGE: Vague Intent -> Routing to Clarification---")
        return "generate_response"
    print("---EDGE: Intent Clear -> Routing to Vector Search---")
    return "vector_search"

def route_after_vector_search(state: GraphState) -> Literal["graphql_planning", "generate_response"]:
    """If Vector search failed or is stale, route to GraphQL."""
    if state.get("requires_graphql"):
        print("---EDGE: Vector insufficient -> Routing to GraphQL---")
        return "graphql_planning"
    print("---EDGE: Vector sufficient -> Routing to Generation---")
    return "generate_response"

def route_after_graphql(state: GraphState) -> Literal["graphql_planning", "generate_response"]:
    """Evaluates if the GraphQL query succeeded or needs to self-heal."""
    error = state.get("graphql_error")
    retries = state.get("graphql_retries", 0)
    
    if error and retries < 3:
        print(f"---EDGE: GraphQL Error Detected. Cycling back to self-heal (Attempt {retries}/3)---")
        return "graphql_planning"
        
    if error and retries >= 3:
        print("---EDGE: GraphQL Max Retries Reached. Proceeding to Generation with Failure Context---")
        
    print("---EDGE: GraphQL Success. Routing to Generation---")
    return "generate_response"

# --- BUILD THE GRAPH ---

def build_voicebot_graph():
    """Compiles the LangGraph architecture."""
    workflow = StateGraph(GraphState)

    workflow.add_node("intent_detector", detect_intent_node)
    workflow.add_node("vector_search", vector_search_node)
    workflow.add_node("graphql_planning", graphql_planning_node)
    workflow.add_node("generate_response", generate_response_node)

    workflow.add_edge(START, "intent_detector")
    
    workflow.add_conditional_edges(
        "intent_detector",
        route_after_intent,
        {"vector_search": "vector_search", "generate_response": "generate_response"}
    )

    workflow.add_conditional_edges(
        "vector_search",
        route_after_vector_search,
        {"graphql_planning": "graphql_planning", "generate_response": "generate_response"}
    )

    # --- REPLACED: Changed from standard edge to Conditional Edge ---
    workflow.add_conditional_edges(
        "graphql_planning",
        route_after_graphql,
        {"graphql_planning": "graphql_planning", "generate_response": "generate_response"}
    )
    
    workflow.add_edge("generate_response", END)

    app = workflow.compile()

    try:
        # This generates a PNG using LangGraph's built-in Mermaid renderer
        img_bytes = app.get_graph().draw_mermaid_png()
        with open("voicebot_graph.png", "wb") as f:
            f.write(img_bytes)
        print("✅ Graph successfully visualized and saved as voicebot_graph.png")
    except Exception as e:
        print(f"⚠️ Could not generate graph visualization: {e}")

    return app