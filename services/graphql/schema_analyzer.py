"""
Schema Analyzer for WebVox.
LLM-powered component that understands table purposes and relationships
by analyzing field names, types, and schema structure.

Supports file-based caching of the schema context string (including LLM-generated
table descriptions) to avoid repeated API calls on every user prompt.
Cache TTL and file path are controlled via config.yaml under graphql.schema_cache.
"""

import json
import os
import time
from typing import Dict, Any, List, Optional

from utilities.config_loader import get_config
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

    File-based cache
    ----------------
    On the first call to build_schema_context() the full context string
    (including LLM-generated table descriptions) is written to disk at the
    path configured in graphql.schema_cache.cache_file.  Subsequent calls
    read that file directly — no LLM calls — until the TTL expires or
    force_refresh_schema is enabled.

    Config knobs (config.yaml → graphql):
        force_refresh_schema: false   # bypass cache entirely when true
        schema_cache:
            enabled: true             # master switch
            ttl_seconds: 3600         # seconds before cache is rebuilt
            cache_file: "data/schema_cache.json"
    """
    
    def __init__(self, introspector=None):
        """
        Initialize schema analyzer.
        
        Args:
            introspector: SchemaIntrospector instance (uses global if None)
        """
        self.introspector = introspector or get_schema_introspector()
        # In-memory fallback — still useful when disk cache is disabled
        self._descriptions_cache: Dict[str, str] = {}

        self.config = get_config()
        self._cache_enabled: bool = self.config.get("graphql.schema_cache.enabled", True)
        self._cache_ttl: int = self.config.get("graphql.schema_cache.ttl_seconds", 3600)
        self._cache_file: str = self.config.get(
            "graphql.schema_cache.cache_file", "data/schema_cache.json"
        )
        self._force_refresh: bool = self.config.get("graphql.force_refresh_schema", False)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze_table_purpose(self, table_name: str) -> str:
        """
        Analyze and generate a human-readable description of what a table contains.
        
        Args:
            table_name: Name of the table to analyze
            
        Returns:
            Human-readable description of the table's purpose
        """
        # Check in-memory cache first (populated from disk cache during build_schema_context)
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

    def get_relationship_description(self, from_table: str, to_table: str, relationship_type: RelationshipType) -> str:
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

        Results are persisted to a JSON cache file so that the expensive LLM calls
        for table descriptions only happen when the cache is cold or has expired.

        Args:
            tables: List of table names to include (all if None)
            
        Returns:
            Formatted schema context string with full column/relationship detail
        """
        # --- Disk cache fast path ---
        if not self._force_refresh and self._cache_enabled:
            cached = self._load_disk_cache()
            if cached is not None:
                # Warm the in-memory descriptions cache from disk so that
                # analyze_table_purpose() calls don't trigger extra LLM calls.
                self._descriptions_cache.update(cached.get("descriptions", {}))
                print("  📦 Using cached schema context (disk)")
                return cached["schema_context"]

        # --- Cold path: build everything from scratch ---
        if tables is None:
            tables = self.introspector.get_all_table_names()

        schema_parts = []

        for table_name in tables:
            table_info = self.introspector.get_table_info(table_name)
            if not table_info:
                continue
            
            # Table header with description (may trigger LLM call)
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

        schema_context = "\n".join(schema_parts)

        # Persist to disk (only when caching is enabled)
        if self._cache_enabled:
            self._save_disk_cache(schema_context, self._descriptions_cache)

        return schema_context

    def suggest_fields_for_query(self, table_name: str, user_query: str) -> List[str]:
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
        
        return list(set(essential_fields))

    def suggest_relationships_for_query(self, table_name: str, user_query: str) -> List[str]:
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

    def clear_cache(self):
        """Clear both the in-memory and disk caches."""
        self._descriptions_cache.clear()
        self.clear_disk_cache()

    def clear_disk_cache(self):
        """Delete the on-disk schema cache file."""
        cache_path = self._resolve_cache_path()
        if os.path.exists(cache_path):
            os.remove(cache_path)
            print(f"  🗑️ Disk schema cache cleared: {cache_path}")
        else:
            print(f"  ℹ️ No disk cache file found at: {cache_path}")

    # ------------------------------------------------------------------
    # Disk cache helpers
    # ------------------------------------------------------------------

    def _resolve_cache_path(self) -> str:
        """Resolve cache file path relative to the project root (cwd)."""
        path = self._cache_file
        if not os.path.isabs(path):
            path = os.path.join(os.getcwd(), path)
        return path

    def _is_disk_cache_valid(self, cache_data: Dict[str, Any]) -> bool:
        """Return True if the cache data was generated within the TTL window."""
        generated_at = cache_data.get("generated_at")
        if generated_at is None:
            return False
        age = time.time() - generated_at
        return age < self._cache_ttl

    def _load_disk_cache(self) -> Optional[Dict[str, Any]]:
        """
        Load and validate the disk cache.

        Returns:
            The cache dict if valid, otherwise None.
        """
        cache_path = self._resolve_cache_path()
        if not os.path.exists(cache_path):
            return None

        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            print(f"  ⚠️ Could not read schema cache file: {e}")
            return None

        if not self._is_disk_cache_valid(data):
            ttl_mins = self._cache_ttl // 60
            print(f"  ⏰ Schema cache expired (TTL={ttl_mins}m). Rebuilding…")
            return None

        if "schema_context" not in data:
            print("  ⚠️ Schema cache is malformed. Rebuilding…")
            return None

        return data

    def _save_disk_cache(self, schema_context: str, descriptions: Dict[str, str]) -> None:
        """Persist the schema context and descriptions to the cache file."""
        cache_path = self._resolve_cache_path()

        # Ensure parent directory exists
        os.makedirs(os.path.dirname(cache_path), exist_ok=True)

        payload = {
            "generated_at": time.time(),
            "ttl_seconds": self._cache_ttl,
            "schema_context": schema_context,
            "descriptions": descriptions,
        }

        try:
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
            print(f"  💾 Schema context cached to disk: {cache_path}")
        except Exception as e:
            print(f"  ⚠️ Could not write schema cache file: {e}")

    # ------------------------------------------------------------------
    # LLM description generation
    # ------------------------------------------------------------------

    def _generate_table_description(self, table_info: TableInfo) -> str:
        """
        Use LLM to generate a description of a table based on its structure.
        
        Args:
            table_info: TableInfo object
            
        Returns:
            Generated description
        """
        # Permissions line
        can_insert = getattr(table_info, 'can_insert', False)
        can_update = getattr(table_info, 'can_update', False)
        permissions_info = (
            f"can_insert={can_insert}, can_update={can_update} "
            f"({'writable' if can_insert or can_update else 'read-only'})"
        )

        # Prepare field information with mutability tags
        field_info = []
        for f in table_info.fields[:10]:  # Limit to first 10 fields
            tag = "[immutable]" if not f.is_mutable else "[writable]"
            field_info.append(f"- {f.name} ({f.type})  {tag}")

        # Prepare relationship information with mutability tags
        rel_info = []
        for rel in table_info.relationships:
            rel_info.append(
                f"- {rel.name} → {rel.remote_table} ({rel.type.value})  [writable, relationship]"
            )

        prompt = load_prompt("schema_analyzer", "describe_table.prompt.txt", {
            "table_name": table_info.name,
            "permissions_info": permissions_info,
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
