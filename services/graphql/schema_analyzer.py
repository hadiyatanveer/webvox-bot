"""
Schema Analyzer for WebVox.
LLM-powered component that understands table purposes and relationships
by analyzing field names, types, and schema structure.
"""

import json
from typing import Dict, Any, List, Optional

from utilities.llm_configure import generate_content
from utilities.prompt_loader import load_prompt
from services.graphql.schema_introspector import (
    get_schema_introspector, 
    TableInfo, 
    RelationshipInfo,
    RelationshipType
)


class SchemaAnalyzer:
    """
    Analyzes database schema to provide semantic understanding
    of tables, fields, and relationships.
    """
    
    def __init__(self, introspector=None):
        """
        Initialize schema analyzer.
        
        Args:
            introspector: SchemaIntrospector instance (uses global if None)
        """
        self.introspector = introspector or get_schema_introspector()
        self._descriptions_cache: Dict[str, str] = {}
    
    def analyze_table_purpose(self, table_name: str) -> str:
        """
        Analyze and generate a human-readable description of what a table contains.
        
        Args:
            table_name: Name of the table to analyze
            
        Returns:
            Human-readable description of the table's purpose
        """
        # Check cache
        if table_name in self._descriptions_cache:
            return self._descriptions_cache[table_name]
        
        table_info = self.introspector.get_table_info(table_name)
        if not table_info:
            return f"Table containing {table_name.replace('_', ' ')}"
        
        # Use existing description if available
        if table_info.description:
            self._descriptions_cache[table_name] = table_info.description
            return table_info.description
        
        # Generate description using LLM
        description = self._generate_table_description(table_info)
        self._descriptions_cache[table_name] = description
        return description
    
    def get_relationship_description(
        self,
        from_table: str,
        to_table: str,
        relationship_type: RelationshipType
    ) -> str:
        """
        Get a human-readable description of how two tables relate.
        
        Args:
            from_table: Source table name
            to_table: Target table name
            relationship_type: Type of relationship (OBJECT or ARRAY)
            
        Returns:
            Description of the relationship
        """
        if relationship_type == RelationshipType.OBJECT:
            # Many-to-one
            return f"Each {from_table.rstrip('s')} belongs to a {to_table.rstrip('s')}"
        else:
            # One-to-many
            return f"Each {from_table.rstrip('s')} has multiple {to_table}"
    
    def build_schema_context(self, tables: Optional[List[str]] = None) -> str:
        """
        Build a comprehensive, Hasura-specific schema description for the query planner.
        
        Args:
            tables: List of table names to include (all if None)
            
        Returns:
            Formatted schema context string with full column/relationship detail
        """
        if tables is None:
            tables = self.introspector.get_all_table_names()
        
        schema_parts = []
        
        for table_name in tables:
            table_info = self.introspector.get_table_info(table_name)
            if not table_info:
                continue
            
            # Table header with description
            description = self.analyze_table_purpose(table_name)
            schema_parts.append(f"TABLE: {table_name}")
            schema_parts.append(f"  Description: {description}")
            
            # Columns with full detail: type, PK, NOT NULL
            schema_parts.append("  COLUMNS:")
            for f in table_info.fields:
                annotations = []
                if f.is_primary_key:
                    annotations.append("PRIMARY KEY")
                if not f.is_nullable:
                    annotations.append("NOT NULL")
                ann_str = f" [{', '.join(annotations)}]" if annotations else ""
                schema_parts.append(f"    - {f.name} ({f.type}{ann_str})")
            
            # Relationships with Hasura-specific detail
            if table_info.relationships:
                schema_parts.append("  RELATIONSHIPS:")
                for rel in table_info.relationships:
                    if rel.type == RelationshipType.OBJECT:
                        rel_label = "OBJECT"
                        hasura_note = "Returns single row. Does NOT accept 'where' argument at selection level. To filter by this related table, use it inside the PARENT table's where clause."
                    else:
                        rel_label = "ARRAY"
                        hasura_note = "Returns multiple rows. Accepts 'where' argument at selection level for filtering."
                    
                    schema_parts.append(f"    - {rel.name} ({rel_label} → {rel.remote_table})")
                    
                    # Join condition
                    if rel.field_mapping:
                        for local_col, remote_col in rel.field_mapping.items():
                            schema_parts.append(f"      Join: {table_name}.{local_col} = {rel.remote_table}.{remote_col}")
                    
                    schema_parts.append(f"      Hasura rule: {hasura_note}")
            
            schema_parts.append("")  # Blank line between tables
        
        return "\n".join(schema_parts)
    
    def suggest_fields_for_query(
        self,
        table_name: str,
        user_query: str
    ) -> List[str]:
        """
        Suggest which fields should be included in a query based on user intent.
        
        Args:
            table_name: Name of the table being queried
            user_query: User's natural language query
            
        Returns:
            List of field names to include
        """
        table_info = self.introspector.get_table_info(table_name)
        if not table_info:
            return []
        
        # Always include id
        essential_fields = ['id']
        
        # Add commonly useful fields
        common_fields = ['name', 'title', 'description', 'status', 'type']
        for field in table_info.fields:
            if field.name in common_fields:
                essential_fields.append(field.name)
        
        # For now, return essential fields
        # In a more sophisticated version, this could use LLM to determine
        # which fields are relevant based on user_query
        return list(set(essential_fields))
    
    def suggest_relationships_for_query(
        self,
        table_name: str,
        user_query: str
    ) -> List[str]:
        """
        Suggest which relationships should be followed in a query.
        
        Args:
            table_name: Name of the table being queried
            user_query: User's natural language query
            
        Returns:
            List of relationship names to follow
        """
        table_info = self.introspector.get_table_info(table_name)
        if not table_info:
            return []
        
        # Simple heuristic: check if user query mentions related table names
        query_lower = user_query.lower()
        relevant_relationships = []
        
        for rel in table_info.relationships:
            # Check if remote table is mentioned in query
            remote_table_singular = rel.remote_table.rstrip('s')
            if (rel.remote_table.lower() in query_lower or 
                remote_table_singular.lower() in query_lower or
                rel.name.lower() in query_lower):
                relevant_relationships.append(rel.name)
        
        return relevant_relationships
    
    def _generate_table_description(self, table_info: TableInfo) -> str:
        """
        Use LLM to generate a description of a table based on its structure.
        
        Args:
            table_info: TableInfo object
            
        Returns:
            Generated description
        """
        # Prepare field information
        field_info = []
        for field in table_info.fields[:10]:  # Limit to first 10 fields
            field_info.append(f"- {field.name} ({field.type})")
        
        # Prepare relationship information
        rel_info = []
        for rel in table_info.relationships:
            rel_info.append(f"- {rel.name} → {rel.remote_table} ({rel.type.value})")
        
        prompt = load_prompt("schema_analyzer", "describe_table.prompt.txt", {
            "table_name": table_info.name,
            "field_info": chr(10).join(field_info),
            "rel_info": chr(10).join(rel_info) if rel_info else "None",
        })
        
        try:
            response = generate_content(prompt)
            
            # Extract response text
            if hasattr(response, "candidates"):
                description = response.candidates[0].content.parts[0].text.strip()
            elif hasattr(response, "content"):
                description = response.content.strip()
            else:
                description = str(response).strip()
            
            # Clean up the description
            description = description.replace('\n', ' ').strip()
            if description.startswith('"') and description.endswith('"'):
                description = description[1:-1]
            
            return description
            
        except Exception as e:
            print(f"  ⚠️ Error generating table description: {e}")
            # Fallback description
            return f"Contains {table_info.name.replace('_', ' ')} data"
    
    def clear_cache(self):
        """Clear the descriptions cache."""
        self._descriptions_cache.clear()


# Global instance
_schema_analyzer = None


def get_schema_analyzer(introspector=None) -> SchemaAnalyzer:
    """Get the global schema analyzer instance."""
    global _schema_analyzer
    if _schema_analyzer is None:
        _schema_analyzer = SchemaAnalyzer(introspector)
    return _schema_analyzer


def reset_schema_analyzer():
    """Reset the global schema analyzer (useful for testing)."""
    global _schema_analyzer
    _schema_analyzer = None
