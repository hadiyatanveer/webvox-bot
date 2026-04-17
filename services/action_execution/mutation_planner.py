"""
Mutation Planner Agent - Generates GraphQL mutation strings from ActionIntent.
"""
import json
from datetime import datetime
from typing import Dict, Any, Optional

from utilities.llm_configure import generate_content
from utilities.prompt_loader import load_prompt
from services.graphql.schema_analyzer import get_schema_analyzer

class MutationPlanner:
    """
    LLM-powered agent that plans and generates GraphQL mutation strings.
    """
    
    def __init__(self):
        self.analyzer = get_schema_analyzer()

    def plan_mutation(self, action_intent: Dict[str, Any], user_id: Optional[int] = None) -> str:
        """
        Generate a GraphQL mutation string based on action intent.
        """
        # Get schema context with mutability hints
        schema_context = self.analyzer.build_schema_context()
        
        # Prepare prompt
        prompt = load_prompt("action_execution", "plan_mutation.prompt.txt", {
            "schema_context": schema_context,
            "action_intent": json.dumps(action_intent, indent=2),
            "user_id": user_id if user_id is not None else "NOT_SET",
            "current_time": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
        })
        
        try:
            response = generate_content(prompt)
            
            # Extract response text
            if hasattr(response, "candidates"):
                mutation_string = response.candidates[0].content.parts[0].text
            elif hasattr(response, "content"):
                mutation_string = response.content
            else:
                mutation_string = str(response)
            
            # Clean possible markdown formatting
            mutation_string = mutation_string.strip()
            if mutation_string.startswith("```"):
                mutation_string = mutation_string.strip("`").replace("graphql", "").strip()
            
            return mutation_string
            
        except Exception as e:
            print(f"Mutation Planner error: {e}")
            raise Exception(f"Failed to generate mutation: {e}")

_mutation_planner = None

def get_mutation_planner() -> MutationPlanner:
    """Get global instance."""
    global _mutation_planner
    if _mutation_planner is None:
        _mutation_planner = MutationPlanner()
    return _mutation_planner
