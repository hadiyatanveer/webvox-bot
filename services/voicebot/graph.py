# services/voicebot/graph.py
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from typing import Literal

from services.voicebot.state import GraphState
from services.voicebot.nodes import (
    detect_intent_node,
    action_intent_classifier_node,
    action_enrichment_node,
    vector_search_node,
    graphql_planning_node,
    mutation_execution_node,
    generate_response_node
)

# --- CONDITIONAL EDGE FUNCTIONS ---

def route_at_start(state: GraphState) -> Literal["intent_detector", "action_intent_classifier"]:
    """Determines whether to detect a new intent or continue a pending action."""
    action_data = state.get("action_data")
    if action_data and not action_data.get("missing_info", {}).get("is_complete", True):
        print("---EDGE: START -> Pending Action Incomplete -> Routing to Action Classifier---")
        return "action_intent_classifier"
    
    print("---EDGE: START -> Routing to Intent Detector---")
    return "intent_detector"

def route_action_classifier(state: GraphState) -> Literal["Action Complete", "Action Incomplete"]:
    """Determines whether to execute enrichment or ask for more info/show error."""
    action_data = state.get("action_data")
    if not action_data:
        return "Action Incomplete"
    
    # 1. If there's an error (Security/Disallowed), route to response generation immediately
    if action_data.get("error"):
        print(f"---EDGE: Action Error Detected ({action_data['error']}) -> Routing to Response Generation---")
        return "Action Incomplete"
    
    # 2. If complete, proceed to enrichment
    if action_data.get("missing_info", {}).get("is_complete", False):
        print("---EDGE: Action Complete -> Routing to Action Enrichment---")
        return "Action Complete"
    
    print("---EDGE: Action Incomplete -> Routing to Response Generation (Clarification)---")
    return "Action Incomplete"

def route_after_intent(state: GraphState) -> Literal["generate_response", "vector_search", "action_intent_classifier"]:
    """Routes based on detected intent category."""
    
    # Conventional routing (Clarification, Category-based)
    if state.get("needs_clarification"):
        print("---EDGE: Vague Intent -> Routing to Clarification---")
        return "generate_response"
    
    intent_data = state.get("intent_data", {})
    if intent_data.get("category") == "action":
        print("---EDGE: Category Action -> Routing to Action Classifier---")
        return "action_intent_classifier"
        
    print("---EDGE: Category Info/Other -> Routing to Vector Search---")
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
    # 1. Initialize the Graph with our State schema
    workflow = StateGraph(GraphState)

    # 2. Add all of our Nodes
    workflow.add_node("intent_detector", detect_intent_node)
    workflow.add_node("action_intent_classifier", action_intent_classifier_node)
    workflow.add_node("action_enrichment", action_enrichment_node)
    workflow.add_node("mutation_execution", mutation_execution_node)
    workflow.add_node("vector_search", vector_search_node)
    workflow.add_node("graphql_planning", graphql_planning_node)
    workflow.add_node("generate_response", generate_response_node)

    # 3. Define the routing edges
    # Start -> Intent OR Action Classifier (via router)
    workflow.add_conditional_edges(
        START,
        route_at_start,
        {
            "intent_detector": "intent_detector",
            "action_intent_classifier": "action_intent_classifier"
        }
    )
    
    # Intent -> Vector Search OR Action Classifier OR Generation (Clarification)
    workflow.add_conditional_edges(
        "intent_detector",
        route_after_intent,
        {
            "vector_search": "vector_search",
            "action_intent_classifier": "action_intent_classifier",
            "generate_response": "generate_response"
        }
    )

    # Action Classifier -> Mutation Execution OR Generation (via router)
    workflow.add_conditional_edges(
        "action_intent_classifier",
        route_action_classifier,
        {
            "Action Incomplete": "generate_response",
            "Action Complete": "action_enrichment"
        }
    )

    # Action Enrichment -> Mutation Execution
    workflow.add_edge("action_enrichment", "mutation_execution")

    # Mutation Execution -> Generation
    workflow.add_edge("mutation_execution", "generate_response")

    # Vector Search -> GraphQL OR Generation
    workflow.add_conditional_edges(
        "vector_search",
        route_after_vector_search,
        {
            "graphql_planning": "graphql_planning",
            "generate_response": "generate_response"
        }
    )

    # GraphQL -> Generation OR Self-Heal Loop
    workflow.add_conditional_edges(
        "graphql_planning",
        route_after_graphql,
        {
            "graphql_planning": "graphql_planning",
            "generate_response": "generate_response"
        }
    )
    
    # Generation -> End
    workflow.add_edge("generate_response", END)

    # 4. Compile with persistence support (checkpointer)
    checkpointer = MemorySaver()
    app = workflow.compile(checkpointer=checkpointer)

    # 5. Graph Visualization
    try:
        # This generates a PNG using LangGraph's built-in Mermaid renderer
        img_bytes = app.get_graph().draw_mermaid_png()
        with open("voicebot_graph.png", "wb") as f:
            f.write(img_bytes)
        print("✅ Graph successfully visualized and saved as voicebot_graph.png")
    except Exception as e:
        print(f"⚠️ Could not generate graph visualization: {e}")

    return app