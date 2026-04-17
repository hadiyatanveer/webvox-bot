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
from services.graphql.schema_introspector import get_schema_introspector, RelationshipType
from utilities.prompt_loader import load_prompt
from services.graphql.schema_analyzer import get_schema_analyzer
from services.graphql.query_generator import QueryPlan, get_query_generator


class QueryPlannerAgent:
    """
    LLM-based agent that plans database queries by understanding user intent
    and generating appropriate GraphQL queries.
    """
    
    # Sensitive fields that should never be included in query results
    _SENSITIVE_FIELDS = {'password', 'password_hash', 'ssn', 'credit_card', 'secret_key'}

    def __init__(self):
        self.config = get_config()
        self.introspector = get_schema_introspector()
        self.analyzer = get_schema_analyzer()
        self.generator = get_query_generator()
        self._enforce_security = self.config.get('graphql.security.enforce_programmatic', True)
    
    def plan_query( self, user_query: str, detected_entities: Optional[Dict[str, Any]] = None, previous_error: Optional[str] = None, previous_query: Optional[str] = None, user_id: Optional[int] = None ) -> Tuple[QueryPlan, str]:
        """
        Plan a database query based on user's request and detected entities.
        
        Args:
            user_query: The user's natural language query
            detected_entities: Entities extracted from intent detection
            previous_error: Error from a previous failed query attempt
            previous_query: The previous query that failed
            user_id: Current authenticated user's ID for security filtering
            
        Returns:
            Tuple of (QueryPlan object, generated GraphQL query string)
        """
        detected_entities = detected_entities or {}
        
        # Get schema context
        schema_context = self.analyzer.build_schema_context()
        
        if previous_error and previous_query:
            user_query += (
                f"\n\n[SYSTEM ALERT - PREVIOUS QUERY FAILED]\n"
                f"Your last query:\n{previous_query}\n"
                f"Failed with error:\n{previous_error}\n"
                f"Please fix the syntax or field names based on the schema and try again."
            )

        # Create prompt for LLM
        prompt = self._build_planning_prompt(
            user_query,
            detected_entities,
            schema_context,
            user_id
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
            
            # Programmatic security enforcement (if enabled)
            if self._enforce_security:
                self._enforce_security_filters(query_plan, user_id)
            
            # Stop here if security blocked it (confidence 0)
            if query_plan.confidence <= 0:
                print(f"  🚫 Security Blocked: {query_plan.reasoning}")
                return query_plan, ""

            print(f"  🗂️ Query Planner: table={query_plan.primary_table}, confidence={query_plan.confidence:.2f}")
            print(f"     Reasoning: {query_plan.reasoning}")
            print(f"     WHERE conditions: {query_plan.where_conditions}")
            if query_plan.relationships:
                print(f"     Relationships: {[r['name'] for r in query_plan.relationships]}")
            
            # Generate GraphQL query
            graphql_query = self.generator.generate_query(query_plan)
            
            return query_plan, graphql_query
            
        except Exception as e:
            print(f"  ⚠️ Query Planner error: {e}")
            raise e
        
    def _build_planning_prompt(
        self,
        user_query: str,
        detected_entities: Dict[str, Any],
        schema_context: str,
        user_id: Optional[int] = None
    ) -> str:
        """Build the LLM prompt for intelligent GraphQL query planning."""

        # Pre-compute the entities string for the prompt template
        entities_str = json.dumps(detected_entities, indent=2) if detected_entities else "None"

        prompt = load_prompt("query_planner", "plan_query.prompt.txt", {
            "schema_context": schema_context,
            "user_query": user_query,
            "detected_entities": entities_str,
            "user_id": user_id if user_id is not None else "ANONYMOUS",
        })
        return prompt

    # ------------------------------------------------------------------
    # Programmatic Security Enforcement
    # ------------------------------------------------------------------

    def _enforce_security_filters(
        self, query_plan: QueryPlan, user_id: Optional[int]
    ) -> None:
        """
        Programmatically enforce security filters on a QueryPlan AFTER the LLM
        generates it but BEFORE the GraphQL query is built.

        This is a safety net — even if the LLM forgets a filter, this guarantees
        no user-scoped data leaks. All checks use schema introspection rather
        than hardcoded table names.
        """
        table = query_plan.primary_table

        # 1. Strip sensitive fields at every level
        self._strip_sensitive_fields(query_plan)

        # 2. Primary table: inject user_id filter if the table is user-scoped
        if self._table_has_user_id(table):
            if user_id is not None:
                query_plan.where_conditions.setdefault(
                    "user_id", {"_eq": user_id}
                )
                print(f"  🔒 Security: Enforced user_id={user_id} filter on '{table}'")
            else:
                query_plan.confidence = 0.0
                query_plan.reasoning = f"[SECURITY BLOCKED: user_id required for '{table}' but not provided]"
                print(f"  ⛔ Security: user_id required for table '{table}' but not provided")

        # 3. Identity table guard (users table): restrict to own row
        if self._is_identity_table(table):
            if user_id is not None:
                query_plan.where_conditions.setdefault(
                    "id", {"_eq": user_id}
                )
                print(f"  🔒 Security: Enforced id={user_id} on identity table '{table}'")
            else:
                query_plan.confidence = 0.0
                query_plan.reasoning = f"[SECURITY BLOCKED: identity table '{table}' requires user_id]"
                print(f"  ⛔ Security: blocked identity table '{table}' (no user_id)")

        # 4. Walk relationships and enforce security at every level
        self._enforce_relationship_security(query_plan.relationships, user_id)

    def _enforce_relationship_security(
        self, relationships: List[Dict[str, Any]], user_id: Optional[int]
    ) -> None:
        """
        Recursively enforce user_id filters on nested relationships if the
        related table has a user_id column.
        Skips OBJECT relationships since they don't accept 'where' in Hasura.
        """
        for rel in relationships:
            rel_name = rel.get("name", "")

            # Try to find the remote table and relationship type via introspection
            remote_table, rel_type = self._resolve_remote_table(rel_name)
            if not remote_table:
                continue

            # OBJECT relationships do NOT accept 'where' in Hasura — skip them
            if rel_type == RelationshipType.OBJECT:
                # Recurse into nested relationships (the nested ones might be ARRAY)
                nested = rel.get("relationships", [])
                if nested:
                    self._enforce_relationship_security(nested, user_id)
                continue

            # Only ARRAY relationships can have 'where' filters
            # Inject user_id filter if the related table is user-scoped
            if self._table_has_user_id(remote_table):
                if user_id is not None:
                    where = rel.setdefault("where", {})
                    where.setdefault("user_id", {"_eq": user_id})
                    print(f"  🔒 Security: Enforced user_id={user_id} on relationship '{rel_name}' → '{remote_table}'")

            # Identity table guard on ARRAY relationships too
            if self._is_identity_table(remote_table):
                if user_id is not None:
                    where = rel.setdefault("where", {})
                    where.setdefault("id", {"_eq": user_id})
                    print(f"  🔒 Security: Enforced id={user_id} on identity relationship '{rel_name}'")

            # Recurse into nested relationships
            nested = rel.get("relationships", [])
            if nested:
                self._enforce_relationship_security(nested, user_id)

    def _table_has_user_id(self, table_name: str) -> bool:
        """Check if a table has a 'user_id' column (making it user-scoped)."""
        table_info = self.introspector.get_table_info(table_name)
        if not table_info:
            return False
        return "user_id" in table_info.get_field_names()

    def _is_identity_table(self, table_name: str) -> bool:
        """
        Heuristic: detect if a table is a user-identity table by checking for
        personal fields like email, phone, password_hash alongside an id column.
        This avoids hardcoding 'users' as the table name.
        """
        table_info = self.introspector.get_table_info(table_name)
        if not table_info:
            return False
        field_names = set(table_info.get_field_names())
        identity_markers = {"email", "phone", "password_hash", "full_name"}
        # If the table has 'id' and at least 2 identity markers, it is an identity table
        return "id" in field_names and len(field_names & identity_markers) >= 2

    def _resolve_remote_table(self, relationship_name: str) -> Tuple[Optional[str], Optional[RelationshipType]]:
        """
        Try to resolve a relationship name to its remote table name and type.
        Uses the schema introspector to look up the primary table's relationships.

        Returns:
            Tuple of (remote_table_name, relationship_type) or (None, None) if not found.
        """
        # Check all tables for a relationship with this name
        all_tables = self.introspector.get_all_table_names()
        for tbl in all_tables:
            table_info = self.introspector.get_table_info(tbl)
            if not table_info:
                continue
            for rel in table_info.relationships:
                if rel.name == relationship_name:
                    return rel.remote_table, rel.type
        return None, None

    def _strip_sensitive_fields(self, query_plan: QueryPlan) -> None:
        """
        Remove fields that should never be returned (passwords, SSNs, etc.).
        Works on the primary table fields and recursively on relationships.
        """
        query_plan.fields = [
            f for f in query_plan.fields if f not in self._SENSITIVE_FIELDS
        ]
        self._strip_sensitive_from_relationships(query_plan.relationships)

    def _strip_sensitive_from_relationships(
        self, relationships: List[Dict[str, Any]]
    ) -> None:
        """Recursively strip sensitive fields from relationship selections."""
        for rel in relationships:
            fields = rel.get("fields", [])
            rel["fields"] = [
                f for f in fields if f not in self._SENSITIVE_FIELDS
            ]
            nested = rel.get("relationships", [])
            if nested:
                self._strip_sensitive_from_relationships(nested)

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
        if primary_table is not None and primary_table not in available_tables:
            print(f"  ⚠️ Invalid table '{primary_table}' requested by LLM")
            primary_table = None
            result["confidence"] = 0.0
            result["reasoning"] = f"Requested table '{primary_table}' does not exist in the schema."
        
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
        primary_table: Optional[str] = None
    ) -> Dict[str, Any]:
        """Clean and validate WHERE conditions."""
        cleaned = {}
        
        # Also allow relationship names as valid WHERE keys (for Hasura nested filtering)
        valid_rel_names = []
        if primary_table is not None:
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
        primary_table: Optional[str]
    ) -> List[Dict[str, Any]]:
        """Clean and validate relationships."""
        if primary_table is None:
            return []
            
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
