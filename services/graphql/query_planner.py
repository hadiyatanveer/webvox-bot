"""
Query Planner Agent for WebVox.
Sophisticated agent that plans database queries by analyzing user intent,
detected entities, and dynamic database schema. Generates complete GraphQL
queries with WHERE clauses, filters, and nested relationships.
"""

import re
import json
from typing import Dict, Any, List, Optional, Tuple

from utilities.config_loader import get_config
from utilities.llm_configure import generate_content
from services.graphql.schema_introspector import get_schema_introspector
from utilities.prompt_loader import load_prompt
from services.graphql.schema_analyzer import get_schema_analyzer
from services.graphql.query_generator import QueryPlan, get_query_generator


class QueryPlannerAgent:
    """
    LLM-based agent that plans database queries by understanding user intent
    and generating appropriate GraphQL queries.
    """
    
    def __init__(self):
        self.config = get_config()
        self.introspector = get_schema_introspector()
        self.analyzer = get_schema_analyzer()
        self.generator = get_query_generator()
    
    def plan_query(
        self,
        user_query: str,
        detected_entities: Optional[Dict[str, Any]] = None
    ) -> Tuple[QueryPlan, str]:
        """
        Plan a database query based on user's request and detected entities.
        
        Args:
            user_query: The user's natural language query
            detected_entities: Entities extracted from intent detection
            
        Returns:
            Tuple of (QueryPlan object, generated GraphQL query string)
        """
        detected_entities = detected_entities or {}
        
        # Get schema context
        schema_context = self.analyzer.build_schema_context()
        print(schema_context)
        
        # Create prompt for LLM
        prompt = self._build_planning_prompt(
            user_query,
            detected_entities,
            schema_context
        )
        
        try:
            response = generate_content(prompt)
            
            # Extract response text
            if hasattr(response, "candidates"):
                raw_text = response.candidates[0].content.parts[0].text
            elif hasattr(response, "content"):
                raw_text = response.content
            else:
                raw_text = str(response)
            
            # Parse LLM response into QueryPlan
            query_plan = self._parse_llm_response(raw_text)
            
            print(f"  🗂️ Query Planner: table={query_plan.primary_table}, confidence={query_plan.confidence:.2f}")
            print(f"     Reasoning: {query_plan.reasoning}")
            print(f"     WHERE conditions: {query_plan.where_conditions}")
            if query_plan.relationships:
                print(f"     Relationships: {[r['name'] for r in query_plan.relationships]}")
            
            # Generate GraphQL query
            graphql_query = self.generator.generate_query(query_plan)
            
            return query_plan, graphql_query
            
        except Exception as e:
            print(f"  ⚠️ Query Planner error: {e}, falling back to simple query")
            # Fallback to simple menu_items query
            fallback_plan = QueryPlan(
                primary_table="menu_items",
                fields=["id", "name", "description", "price"],
                confidence=0.5,
                reasoning=f"Error in query planning: {e}"
            )
            fallback_query = self.generator.generate_query(fallback_plan)
            return fallback_plan, fallback_query
        
    def _build_planning_prompt(
        self,
        user_query: str,
        detected_entities: Dict[str, Any],
        schema_context: str
    ) -> str:
        """Build the LLM prompt for intelligent GraphQL query planning."""

        # Pre-compute the entities string for the prompt template
        entities_str = json.dumps(detected_entities, indent=2) if detected_entities else "None"

        prompt = load_prompt("query_planner", "plan_query.prompt.txt", {
            "schema_context": schema_context,
            "user_query": user_query,
            "detected_entities": entities_str,
        })
        return prompt

    
    def _parse_llm_response(self, raw_text: str) -> QueryPlan:
        """Parse LLM response into a QueryPlan object."""
        
        # Try to extract JSON from response
        json_match = re.search(r'\{[\s\S]*\}', raw_text)
        if not json_match:
            raise ValueError("Could not find JSON in LLM response")
        
        try:
            result = json.loads(json_match.group())
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in LLM response: {e}")
        
        # Validate and extract fields
        primary_table = result.get("primary_table", "menu_items")
        
        # Validate table exists
        available_tables = self.introspector.get_all_table_names()
        if primary_table not in available_tables:
            print(f"  ⚠️ Invalid table '{primary_table}', falling back to menu_items")
            primary_table = "menu_items"
        
        # Get table info for field validation
        table_info = self.introspector.get_table_info(primary_table)
        valid_fields = table_info.get_field_names() if table_info else []
        
        # Clean and validate fields
        requested_fields = result.get("fields", ["id", "name"])
        cleaned_fields = []
        for field in requested_fields:
            if field in valid_fields:
                cleaned_fields.append(field)
            else:
                print(f"  ⚠️ Field '{field}' not in {primary_table}, skipping")
        
        # Ensure at least 'id' is included
        if "id" not in cleaned_fields:
            cleaned_fields.insert(0, "id")
        
        # Clean where conditions
        where_conditions = self._clean_where_conditions(
            result.get("where_conditions", {}),
            valid_fields,
            primary_table
        )
        
        # Clean relationships
        relationships = result.get("relationships", [])
        cleaned_relationships = self._clean_relationships(
            relationships,
            primary_table
        )
        
        # Create QueryPlan
        query_plan = QueryPlan(
            primary_table=primary_table,
            fields=cleaned_fields,
            where_conditions=where_conditions,
            relationships=cleaned_relationships,
            limit=result.get("limit"),
            order_by=result.get("order_by"),
            confidence=float(result.get("confidence", 0.8)),
            reasoning=result.get("reasoning", "")
        )
        
        return query_plan
    
    def _clean_where_conditions(
        self,
        conditions: Dict[str, Any],
        valid_fields: List[str],
        primary_table: str = None
    ) -> Dict[str, Any]:
        """Clean and validate WHERE conditions."""
        cleaned = {}
        
        # Also allow relationship names as valid WHERE keys (for Hasura nested filtering)
        valid_rel_names = []
        if primary_table:
            table_info = self.introspector.get_table_info(primary_table)
            if table_info:
                valid_rel_names = table_info.get_relationship_names()
        
        for field, condition in conditions.items():
            # Skip if field is not a scalar field, relationship name, or logical operator
            if field not in valid_fields and field not in valid_rel_names and not field.startswith('_'):
                print(f"  ⚠️ Skipping WHERE condition on invalid field: {field}")
                continue
            
            # Handle logical operators (_and, _or, _not)
            if field.startswith('_'):
                cleaned[field] = condition
                continue
            
            # Validate condition structure
            if isinstance(condition, dict):
                cleaned[field] = condition
            else:
                # Convert simple value to _eq condition
                cleaned[field] = {"_eq": condition}
        
        return cleaned
    
    def _clean_relationships(
        self,
        relationships: List[Dict[str, Any]],
        primary_table: str
    ) -> List[Dict[str, Any]]:
        """Clean and validate relationships."""
        table_info = self.introspector.get_table_info(primary_table)
        if not table_info:
            return []
        
        valid_rel_names = table_info.get_relationship_names()
        cleaned = []
        
        for rel in relationships:
            rel_name = rel.get('name')
            
            if rel_name not in valid_rel_names:
                print(f"  ⚠️ Skipping invalid relationship: {rel_name}")
                continue
            
            # Get relationship info
            rel_info = next(
                (r for r in table_info.relationships if r.name == rel_name),
                None
            )
            
            if not rel_info:
                continue
            
            # Validate fields for the related table
            related_table_info = self.introspector.get_table_info(rel_info.remote_table)
            if not related_table_info:
                continue
            
            valid_fields = related_table_info.get_field_names()
            requested_fields = rel.get('fields', ['id'])
            
            cleaned_fields = [f for f in requested_fields if f in valid_fields]
            if not cleaned_fields:
                cleaned_fields = ['id']
            
            # Recursively clean nested relationships (for multi-hop queries)
            nested_relationships = self._clean_relationships(
                rel.get('relationships', []),
                rel_info.remote_table
            )
            
            cleaned.append({
                'name': rel_name,
                'fields': cleaned_fields,
                'where': rel.get('where', {}),
                'relationships': nested_relationships
            })
        
        return cleaned


# Global instance
_query_planner_agent = None


def get_query_planner_agent() -> QueryPlannerAgent:
    """Get the global query planner agent instance."""
    global _query_planner_agent
    if _query_planner_agent is None:
        _query_planner_agent = QueryPlannerAgent()
    return _query_planner_agent


def reset_query_planner_agent():
    """Reset the global query planner agent (useful for testing)."""
    global _query_planner_agent
    _query_planner_agent = None
