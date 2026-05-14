# services/voicebot/nodes.py
from typing import Dict, Any

from services.voicebot.state import GraphState
from services.intent_detection.intent_detector import detect_intent
from services.rag.context_assembler import get_context_assembler, get_retrieval_router
from services.graphql.query_planner import get_query_planner_agent
from services.graphql.client import get_graphql_client
from services.graphql.response_handler import get_response_handler
from services.response_generator.generator import get_response_generator
from services.action_execution.action_intent_classifier import get_action_intent_classifier
from services.action_execution.action_enricher import get_action_enricher
from services.action_execution.mutation_planner import get_mutation_planner

def action_enrichment_node(state: GraphState) -> Dict[str, Any]:
    """
    Enriches action_data with resolved IDs and calculated fields.
    """
    action_data = state.get("action_data")
    if not action_data:
        return {}
    
    print(f"---NODE: ACTION ENRICHMENT---")
    enricher = get_action_enricher()
    enriched_data = enricher.enrich_intent(action_data)
    
    return {"action_data": enriched_data}

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

def action_intent_classifier_node(state: GraphState) -> Dict[str, Any]:
    """Refines action-category intents and enforces safety rules."""
    print("---NODE: ACTION INTENT CLASSIFIER---")
    user_input = state["user_input"]
    intent_data = state["intent_data"]
    
    classifier = get_action_intent_classifier()
    
    # Extract entities from the main intent detector to pass as context
    detected_entities = intent_data.get("entities", {})
    
    # Classify the specific action (insert/update/delete) and table/columns
    # Pass existing action_data to handle iterative turns
    action_intent = classifier.classify_action(
        user_input, 
        detected_entities, 
        previous_action_data=state.get("action_data")
    )
    
    # Convert dataclass to dict for LangGraph state
    action_data = {
        "operation": action_intent.operation,
        "primary_table": action_intent.primary_table,
        "secondary_tables": action_intent.secondary_tables,
        "tables_data": action_intent.tables_data,
        "missing_info": action_intent.missing_info,
        "confidence": action_intent.confidence,
        "reasoning": action_intent.reasoning,
        "error": action_intent.error
    }
    
    result = {"action_data": action_data}
    
    # Handle missing information (Clarification flag)
    if not action_intent.missing_info.get("is_complete", True):
        result["needs_clarification"] = True
        
    return result

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

# Permission-denied error patterns (table not accessible for current role)
_PERMISSION_DENIED_PATTERNS = [
    "field not found in type",
    "not found in type",
    "field not allowed",
    "permission denied",
    "access denied",
    "not permitted",
    "not allowed for role",
]

def _is_permission_error(error_msg: str) -> bool:
    """Check if an error message indicates a permission/access denial."""
    error_lower = error_msg.lower()
    return any(pattern in error_lower for pattern in _PERMISSION_DENIED_PATTERNS)


def graphql_planning_node(state: GraphState) -> Dict[str, Any]:
    """Slow Path: Plans and executes a Hasura GraphQL query with retries."""
    print("---NODE: GRAPHQL DATABASE (SLOW PATH)---")
    user_input = state["user_input"]
    intent_data = state["intent_data"]
    
    # Get current retry state
    retries = state.get("graphql_retries", 0)
    prev_error = state.get("graphql_error")
    prev_query = state.get("previous_graphql_query")
    
    # Extract user_id from context for security filtering
    user_id = state.get("user_context", {}).get("user_id")
    
    planner = get_query_planner_agent()
    client = get_graphql_client()
    handler = get_response_handler()
    
    try:
        # Step 1: LLM Query Planning
        # Pass previous errors and user_id to the planner to generate the query
        query_plan, graphql_query = planner.plan_query(
            user_input, 
            intent_data.get("entities"),
            previous_error=prev_error,
            previous_query=prev_query,
            user_id=user_id
        )
        
        # Step 2: Preemptive LLM Security Refusal Check
        # The LLM determines if the query violates security policies before execution.
        # If confidence is 0, it short-circuits the retry loop with a dummy success
        # and a refusal message.
        if query_plan.confidence <= 0:
            print(f"  🚫 Security Refusal: {query_plan.reasoning}")
            rag_context = {
                "status": "success",
                "context": f"I'm sorry, I don't have permission to access that information. {query_plan.reasoning}",
                "source_path": "security_refusal",
                "query_description": query_plan.reasoning
            }
            return {
                "rag_context": rag_context,
                "graphql_error": None,
                "graphql_retries": retries + 1,
                "previous_graphql_query": None
            }

        # Step 3: Execute GraphQL Query
        print(f"  → Generated GraphQL query (Attempt {retries + 1}):\n{graphql_query}")
        raw_response = client.execute_graphql_query(graphql_query)
        
        # Step 4: Handle Soft DB Validation Errors
        # If Hasura returns an error (like missing permissions due to RBAC), we check
        # if it's a permission error. If it is, we short-circuit the loop again
        # to avoid frantic retries from the LLM on forbidden data.
        if not raw_response.get("success"):
            error_msg = raw_response.get("error", "Unknown Hasura Error")
            
            if _is_permission_error(error_msg):
                print(f"  🚫 Permission denied — not retrying: {error_msg}")
                rag_context = {
                    "status": "success",
                    "context": "I'm sorry, I don't have access to that information. "
                               "The data you requested is restricted and cannot be retrieved.",
                    "source_path": "security_refusal",
                    "query_description": "Access denied by database permissions"
                }
                return {
                    "rag_context": rag_context,
                    "graphql_error": None,
                    "graphql_retries": retries + 1,
                    "previous_graphql_query": graphql_query
                }
            
            raise Exception(error_msg)
            
        print(f"  → Raw GraphQL Query response: {raw_response}")
        
        # Step 5: Process Successful Query
        # Normalize the raw DB JSON into context string for the response generator
        normalized_context = handler.normalize(raw_response, query_plan.primary_table)
        context_string = normalized_context.get("text", str(normalized_context))
        
        rag_context = {
            "status": "success",               
            "context": context_string,     
            "source_path": "graphql_database",
            "query_description": query_plan.reasoning
        }
        
        # Step 6: Return Standard Success
        # Clear errors and advance the retry counter
        return {
            "rag_context": rag_context,
            "graphql_error": None,
            "graphql_retries": retries + 1,
            "previous_graphql_query": graphql_query
        }
        
    except Exception as e:
        error_msg = str(e)
        print(f"  ⚠️ GraphQL execution failed: {error_msg}")
        
        # Step 7: Hard Execution Exception Fallback
        # If the GraphQL client raises a raw Python exception rather than a soft error,
        # check for permission issues again to guarantee a consistent short-circuit exit.
        if _is_permission_error(error_msg):
            print(f"  🚫 Permission denied (exception) — not retrying")
            rag_context = {
                "status": "success",
                "context": "I'm sorry, I don't have access to that information. "
                           "The data you requested is restricted and cannot be retrieved.",
                "source_path": "security_refusal",
                "query_description": "Access denied by database permissions"
            }
            return {
                "rag_context": rag_context,
                "graphql_error": None,
                "graphql_retries": retries + 1,
                "previous_graphql_query": graphql_query if 'graphql_query' in locals() else None,
            }
        
        # Step 8: Trigger Retry for Non-Security Errors
        # If it was a natural failure (like a syntax error), return the error in state 
        # so the LangGraph edge catches it and triggers a retry via the LLM.
        return {
            "graphql_error": error_msg,
            "graphql_retries": retries + 1,
            "previous_graphql_query": graphql_query if 'graphql_query' in locals() else None,
            "rag_context": None
        }

def mutation_execution_node(state: GraphState) -> Dict[str, Any]:
    """Plans and executes the finalized GraphQL mutation."""
    print("---NODE: MUTATION EXECUTION---")
    
    action_data = state.get("action_data")
    if not action_data:
        return {"error": "No action data found for execution."}
        
    planner = get_mutation_planner()
    client = get_graphql_client()
    
    try:
        # Extract user_id from context
        user_id = state.get("user_context", {}).get("user_id")
        
        # 1. Generate the mutation string from the collected data
        mutation_string = planner.plan_mutation(action_data, user_id)
        print(f"  → Generated Mutation:\n{mutation_string}")
        
        # 2. Execute against Hasura
        raw_response = client.execute_graphql_query(mutation_string)
        
        # 3. Store result for Response Generator
        return {
            "mutation_result": raw_response,
            "error": None if raw_response.get("success") else raw_response.get("error")
        }
        
    except Exception as e:
        print(f"Mutation execution failed: {e}")
        return {"error": str(e)}
    
def generate_response_node(state: GraphState) -> Dict[str, Any]:
    generator = get_response_generator()
    
    result = generator.generate(
        user_query=state["user_input"],
        intent_data=state["intent_data"],
        retrieval_result=state.get("rag_context"),
        action_data=state.get("action_data"),       # reads from current state — unaffected
        mutation_result=state.get("mutation_result")
    )
    
    updates = {"final_response": result.get("response", "I'm sorry, I encountered an error.")}

    # Clear action_data from persisted state after terminal conditions,
    # so the next turn's route_at_start doesn't re-enter the action flow.
    action_data = state.get("action_data")
    if action_data and action_data.get("error"):
        updates["action_data"] = None  # only affects checkpointed state for next turn

    if state.get("mutation_result") and state["mutation_result"].get("success"):
        updates["action_data"] = None  # same pattern already in your code

    return updates