"""
LLM-Based Database Router Agent for WebVox.
Uses LLM to determine which database table to access based on user queries.
Replaces the manual pattern-matching entity_router.
"""

import re
import json
from typing import Dict, Any, List, Optional, Tuple

from utilities.config_loader import get_config
from utilities.llm_configure import generate_content


class DatabaseRouterAgent:
    """
    LLM-based agent that determines which database table to access
    based on user queries. Replaces manual pattern matching.
    """
    
    def __init__(self):
        self.config = get_config()
    
    def get_table_schema_description(self, available_tables: List[str]) -> str:
        """
        Get human-readable descriptions of available tables.
        This helps the LLM understand what each table contains.
        """
        # Table descriptions
        table_descriptions = {
            "menu_items": "Contains food menu items with name, price, description, category, calories, availability, vegetarian flag, and ratings",
            "categories": "Contains food categories/sections like Pizza, Burgers, Pasta, Salads, Desserts, Beverages",
            "orders": "Contains user order history with order ID, items ordered, status, total, timestamps",
            "policies": "Contains store policies including delivery policy, refund policy, allergen information"
        }
        
        descriptions = []
        for table in available_tables:
            desc = table_descriptions.get(table, f"Table containing {table.replace('_', ' ')}")
            descriptions.append(f"- {table}: {desc}")
        
        return "\n".join(descriptions)
    
    def route(self, user_query: str, available_tables: List[str], detected_entities: Optional[Dict[str, Any]] = None) -> Tuple[str, Dict[str, Any], float]:
        """
        Use LLM to determine which table to query based on user's request.
        
        Args:
            user_query: The user's natural language query
            available_tables: List of available table names
            detected_entities: Entities extracted from intent detection
            
        Returns:
            Tuple of (table_name, query_params, confidence)
        """
        detected_entities = detected_entities or {}
        table_schema = self.get_table_schema_description(available_tables)
        
        prompt = f"""You are a database routing agent for a food delivery application.
Your task is to determine which database table to query based on the user's request.

**Available Tables:**
{table_schema}

**User Query:** "{user_query}"

**Previously Detected Entities:** {json.dumps(detected_entities) if detected_entities else "None"}

**Instructions:**
1. Analyze the user's query to understand what information they want
2. Select the SINGLE most relevant table to query
3. Extract any filter parameters from the query (category, search term, etc.)
4. Assign a confidence score (0.0-1.0) for your decision

**Response Format (JSON only):**
{{
    "table": "table_name",
    "confidence": 0.95,
    "reasoning": "Brief explanation of why this table was selected"
}}

**Examples:**
- "Tell me about Margherita Pizza" → table: "menu_items", params: {{"search": "Margherita Pizza"}}
- "What pizzas do you have?" → table: "menu_items", params: {{"category": "Pizza"}}
- "Show me all menu items" → table: "menu_items", params: {{}}
- "What vegetarian options do you have?" → table: "menu_items", params: {{"vegetarian": true}}
- "Show me vegan food" → table: "menu_items", params: {{"vegetarian": true}}
- "What's your delivery policy?" → table: "policies", params: {{"type": "delivery"}}
- "Show my orders" → table: "orders", params: {{"user_id": "current_user"}}
- "What categories do you have?" → table: "categories", params: {{}}

Respond with ONLY the JSON object, no other text:"""

        try:
            response = generate_content(prompt)
            
            # Extract response text
            if hasattr(response, "candidates"):
                raw_text = response.candidates[0].content.parts[0].text
            elif hasattr(response, "content"):
                raw_text = response.content
            else:
                raw_text = str(response)
            
            # Parse JSON from response
            result = self._parse_llm_response(raw_text, available_tables)
            
            print(f"  🤖 LLM Router: table={result['table']}, confidence={result['confidence']:.2f}")
            print(f"     Reasoning: {result.get('reasoning', 'N/A')}")
            
            return result["table"], result["confidence"]
            
        except Exception as e:
            print(f"  ⚠️ LLM Router error: {e}, falling back to menu_items")
            return "menu_items", {}, 0.5
    
    def _parse_llm_response(self, raw_text: str, available_tables: List[str]) -> Dict[str, Any]:
        """Parse LLM response and validate table selection."""
        
        # Try to extract JSON from response
        json_match = re.search(r'\{[\s\S]*\}', raw_text)
        if not json_match:
            return {
                "table": "menu_items",
                "params": {},
                "confidence": 0.5,
                "reasoning": "Could not parse LLM response"
            }
        
        try:
            result = json.loads(json_match.group())
        except json.JSONDecodeError:
            return {
                "table": "menu_items",
                "params": {},
                "confidence": 0.5,
                "reasoning": "Invalid JSON in LLM response"
            }
        
        # Validate table exists
        table = result.get("table", "menu_items")
        if table not in available_tables:
            # Find closest match or default
            table = "menu_items"
        
        # Clean up params - remove None values and fix common LLM mistakes
        params = result.get("params", {})
        cleaned_params = {}
        
        for k, v in params.items():
            if v is None or v == "" or v == "null":
                continue
            
            # Fix vegetarian param - should be boolean
            if k == "vegetarian":
                if isinstance(v, bool):
                    cleaned_params[k] = v
                elif str(v).lower() in ["true", "yes", "1"]:
                    cleaned_params[k] = True
                # Skip if it's a string like "vegetarian options"
                continue
            
            # Fix category param - should be a valid category name
            if k == "category":
                valid_categories = ["Pizza", "Burgers", "Pasta", "Salads", "Desserts", "Beverages"]
                # Check if the value is a valid category or contains one
                if v in valid_categories:
                    cleaned_params[k] = v
                else:
                    # Try to find matching category
                    for cat in valid_categories:
                        if cat.lower() in str(v).lower():
                            cleaned_params[k] = cat
                            break
                continue
            
            cleaned_params[k] = v
        
        return {
            "table": table,
            "params": cleaned_params,
            "confidence": float(result.get("confidence", 0.8)),
            "reasoning": result.get("reasoning", "")  
        }
    
    def get_all_tables(self, client) -> List[str]:
        """Get list of all available table names from the GraphQL client."""
        return client.get_available_tables()
    
    def get_table_data(self, client, table_name: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Get data from a specific table."""
        return client.query_table(table_name, params or {})
    
    def get_all_data(self, client) -> Dict[str, Any]:
        """Get all data from all tables (full database)."""
        return client.query_all_tables()


# Global instance
_database_router_agent = None


def get_database_router_agent() -> DatabaseRouterAgent:
    """Get the global database router agent instance."""
    global _database_router_agent
    if _database_router_agent is None:
        _database_router_agent = DatabaseRouterAgent()
    return _database_router_agent
