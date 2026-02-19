"""
GraphQL Query Generator for WebVox.
Converts query plans into valid Hasura GraphQL syntax with WHERE clauses,
filters, and nested queries.
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field


@dataclass
class QueryPlan:
    """Represents a planned database query."""
    primary_table: str
    fields: List[str]
    where_conditions: Dict[str, Any] = field(default_factory=dict)
    relationships: List[Dict[str, Any]] = field(default_factory=list)
    limit: Optional[int] = None
    offset: Optional[int] = None
    order_by: Optional[Dict[str, str]] = None
    confidence: float = 0.8
    reasoning: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "primary_table": self.primary_table,
            "fields": self.fields,
            "where_conditions": self.where_conditions,
            "relationships": self.relationships,
            "limit": self.limit,
            "offset": self.offset,
            "order_by": self.order_by,
            "confidence": self.confidence,
            "reasoning": self.reasoning
        }


class QueryGenerator:
    """
    Generates valid Hasura GraphQL queries from QueryPlan objects.
    Supports WHERE operators, logical operators, and nested queries.
    """
    
    def __init__(self):
        pass
    def generate_query(self, query_plan: QueryPlan) -> str:
        """
        Generate a complete GraphQL query from a QueryPlan.
        
        Args:
            query_plan: QueryPlan object containing query specifications
            
        Returns:
            Valid GraphQL query string
        """
        table = query_plan.primary_table
        
        # Build query arguments (where, limit, offset, order_by)
        args = []
        
        if query_plan.where_conditions:
            where_clause = self.build_where_clause(query_plan.where_conditions)
            args.append(f"where: {where_clause}")
        
        if query_plan.limit:
            args.append(f"limit: {query_plan.limit}")
        
        if query_plan.offset:
            args.append(f"offset: {query_plan.offset}")
        
        if query_plan.order_by:
            order_clause = self._build_order_by(query_plan.order_by)
            args.append(f"order_by: {order_clause}")
        
        args_str = f"({', '.join(args)})" if args else ""
        
        # Build field selection
        selection = self._build_selection(
            query_plan.fields,
            query_plan.relationships
        )
        
        # Assemble final query
        query = f"""query {{
  {table}{args_str} {{
{selection}
  }}
}}"""
        
        return query
    
    def build_where_clause(self, conditions: Dict[str, Any]) -> str:
        """
        Build a WHERE clause from conditions dictionary.
        
        Supports operators:
        - _eq, _neq: Equality/inequality
        - _ilike, _like: Pattern matching
        - _in, _nin: Array membership
        - _gt, _gte, _lt, _lte: Comparisons
        - _is_null: Null check
        - _and, _or, _not: Logical operators
        
        Args:
            conditions: Dictionary of filter conditions
            
        Returns:
            Formatted WHERE clause string
        """
        if not conditions:
            return "{}"
        
        return self._format_object(conditions)
    
    def _build_selection(
        self,
        fields: List[str],
        relationships: List[Dict[str, Any]]
    ) -> str:
        """
        Build the field selection part of the query.
        
        Args:
            fields: List of field names to select
            relationships: List of relationship selections
            
        Returns:
            Formatted field selection string
        """
        lines = []
        
        # Add regular fields
        for field in fields:
            lines.append(f"    {field}")
        
        # Add nested relationship queries
        for rel in relationships:
            rel_name = rel.get('name')
            rel_fields = rel.get('fields', ['id'])
            rel_where = rel.get('where', {})
            
            if rel_where:
                where_str = self.build_where_clause(rel_where)
                lines.append(f"    {rel_name}(where: {where_str}) {{")
            else:
                lines.append(f"    {rel_name} {{")
            
            for field in rel_fields:
                lines.append(f"      {field}")
            
            lines.append("    }")
        
        return "\n".join(lines)
    
    def _build_order_by(self, order_by: Dict[str, str]) -> str:
        """
        Build ORDER BY clause.
        
        Args:
            order_by: Dictionary mapping field names to 'asc' or 'desc'
            
        Returns:
            Formatted order_by clause
        """
        if not order_by:
            return "{}"
        
        order_items = []
        for field, direction in order_by.items():
            order_items.append(f"{field}: {direction}")
        
        return "{" + ", ".join(order_items) + "}"
    
    def _format_value(self, value: Any) -> str:
        """
        Format a value for GraphQL query.
        
        Args:
            value: Python value
            
        Returns:
            GraphQL-formatted string
        """
        if value is None:
            return "null"
        elif isinstance(value, bool):
            return "true" if value else "false"
        elif isinstance(value, str):
            # Escape quotes and format as string
            escaped = value.replace('"', '\\"')
            return f'"{escaped}"'
        elif isinstance(value, (int, float)):
            return str(value)
        elif isinstance(value, list):
            formatted_items = [self._format_value(item) for item in value]
            return "[" + ", ".join(formatted_items) + "]"
        elif isinstance(value, dict):
            return self._format_object(value)
        else:
            return f'"{str(value)}"'
    
    def _format_object(self, obj: Dict[str, Any]) -> str:
        """
        Format a dictionary as a GraphQL object.
        
        Args:
            obj: Dictionary to format
            
        Returns:
            GraphQL-formatted object string
        """
        if not obj:
            return "{}"
        
        items = []
        for key, value in obj.items():
            formatted_value = self._format_value(value)
            items.append(f"{key}: {formatted_value}")
        
        return "{" + ", ".join(items) + "}"


# Global instance
_query_generator = None


def get_query_generator() -> QueryGenerator:
    """Get the global query generator instance."""
    global _query_generator
    if _query_generator is None:
        _query_generator = QueryGenerator()
    return _query_generator
