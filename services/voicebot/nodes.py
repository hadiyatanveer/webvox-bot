# services/voicebot/nodes.py
from typing import Dict, Any

from services.voicebot.state import GraphState
from services.intent_detection.intent_detector import detect_intent
from services.rag.context_assembler import get_context_assembler, get_retrieval_router
from services.graphql.query_planner import get_query_planner_agent
from services.graphql.client import get_graphql_client
from services.graphql.response_handler import get_response_handler
from services.response_generator.generator import get_response_generator

def detect_intent_node(state: GraphState) -> Dict[str, Any]:
    """Analyzes the user's intent and extracts entities."""
    print("---NODE: DETECT INTENT---")
    user_input = state["user_input"]
    
    # Call your existing intent detector
    intent_data = detect_intent(user_input)
    
    # Check if the intent was too vague
    needs_clarification = intent_data.get("needs_clarification", False)
    
    return {
        "intent_data": intent_data,
        "needs_clarification": needs_clarification
    }

def vector_search_node(state: GraphState) -> Dict[str, Any]:
    """Fast Path: Searches FAISS for static documents."""
    print("---NODE: VECTOR SEARCH (FAST PATH)---")
    user_input = state["user_input"]
    intent_data = state["intent_data"]
    
    assembler = get_context_assembler()
    router = get_retrieval_router()
    
    # FIX 1: Use 'k' instead of 'limit' for FAISS search
    vector_results = assembler.vector_store.search(
        query=user_input, 
        k=assembler.max_results
    )
    
    # FIX 2: Use your dedicated RetrievalRouter to evaluate the results
    detected_entities = intent_data.get("entities", {})
    requires_graphql = router.should_use_slow_path(
        vector_results=vector_results, 
        query=user_input, 
        detected_entities=detected_entities
    )
    
    # If the vector search was good enough, format it for the generator
    rag_context = None
    if not requires_graphql:
        # Combine the vector chunks into a single readable string
        context_text = "\n\n".join([str(r.chunk.to_dict()) for r in vector_results])
        
        rag_context = {
            "status": "success",           # <--- Bypasses clarification check
            "context": context_text,       # <--- Feeds the LLM the policy text
            "source_path": "vector_faiss"
        }
        
    return {
        "vector_results": vector_results,
        "requires_graphql": requires_graphql,
        "rag_context": rag_context
    }

def graphql_planning_node(state: GraphState) -> Dict[str, Any]:
    """Slow Path: Plans and executes a Hasura GraphQL query with retries."""
    print("---NODE: GRAPHQL DATABASE (SLOW PATH)---")
    user_input = state["user_input"]
    intent_data = state["intent_data"]
    
    # Get current retry state
    retries = state.get("graphql_retries", 0)
    prev_error = state.get("graphql_error")
    prev_query = state.get("previous_graphql_query")
    
    planner = get_query_planner_agent()
    client = get_graphql_client()
    handler = get_response_handler()
    
    try:
        # Pass previous errors to the planner
        query_plan, graphql_query = planner.plan_query(
            user_input, 
            intent_data.get("entities"),
            previous_error=prev_error,
            previous_query=prev_query
        )
        
        print(f"  → Generated GraphQL query (Attempt {retries + 1}):\n{graphql_query}")
        
        raw_response = client.execute_graphql_query(graphql_query)
        
        # --- Explicitly trigger retry if Hasura returns an error ---
        if not raw_response.get("success"):
            raise Exception(raw_response.get("error", "Unknown Hasura Error"))
            
        print(f"  → Raw GraphQL Query response: {raw_response}")
        
        normalized_context = handler.normalize(raw_response, query_plan.primary_table)
        context_string = normalized_context.get("text", str(normalized_context))
        
        rag_context = {
            "status": "success",               
            "context": context_string,     
            "source_path": "graphql_database"
        }
        
        # Success! Clear errors and advance the retry counter
        return {
            "rag_context": rag_context,
            "graphql_error": None,
            "graphql_retries": retries + 1,
            "previous_graphql_query": graphql_query
        }
        
    except Exception as e:
        error_msg = str(e)
        print(f"  ⚠️ GraphQL execution failed: {error_msg}")
        
        # Return the error to the state so the graph edge can catch it
        return {
            "graphql_error": error_msg,
            "graphql_retries": retries + 1,
            "previous_graphql_query": graphql_query if 'graphql_query' in locals() else None,
            "rag_context": None
        }
    
def generate_response_node(state: GraphState) -> Dict[str, Any]:
    """Synthesizes the final voice response."""
    print("---NODE: GENERATE RESPONSE---")
    
    generator = get_response_generator()
    
    # Generate the conversational reply using your existing generator
    result = generator.generate(
        user_query=state["user_input"],
        intent_data=state["intent_data"],
        retrieval_result=state.get("rag_context")
    )
    
    return {"final_response": result.get("response", "I'm sorry, I encountered an error.")}