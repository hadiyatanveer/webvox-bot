"""
Schema Introspection Service for WebVox.
Dynamically retrieves database schema from Hasura/GraphQL including tables, 
fields, types, and relationships.
"""

import time
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

from utilities.config_loader import get_config
import json
import os


class RelationshipType(Enum):
    """Types of relationships between tables."""
    OBJECT = "object"  # Many-to-one (foreign key)
    ARRAY = "array"    # One-to-many


@dataclass
class FieldInfo:
    """Information about a table field."""
    name: str
    type: str
    is_nullable: bool = True
    is_primary_key: bool = False
    is_mutable: bool = True  # Can appear in update _set clause


@dataclass
class RelationshipInfo:
    """Information about a relationship between tables."""
    name: str
    type: RelationshipType
    remote_table: str
    field_mapping: Dict[str, str] = field(default_factory=dict)  # local_field -> remote_field
    
    def __repr__(self):
        return f"RelationshipInfo(name={self.name}, type={self.type.value}, remote_table={self.remote_table}, field_mapping={self.field_mapping})"


@dataclass
class TableInfo:
    """Complete information about a database table."""
    name: str
    fields: List[FieldInfo]
    relationships: List[RelationshipInfo]
    description: Optional[str] = None
    # Mutation permissions for the current user role
    can_insert: bool = False
    can_update: bool = False
    
    def get_field_names(self) -> List[str]:
        """Get list of field names."""
        return [f.name for f in self.fields]

    def get_relationship_names(self) -> List[str]:
        """Get list of relationship names."""
        return [r.name for r in self.relationships]

    def get_mutable_fields(self) -> List[str]:
        """
        Return all names that may be written in a mutation.
        Includes:
        - Scalar fields with is_mutable=True (direct columns)
        - Relationship names (FK / nested insert targets)
        The LLM decides which of these are actually required.
        """
        scalar_mutable = [f.name for f in self.fields if f.is_mutable]
        rel_names = [r.name for r in self.relationships]
        return scalar_mutable + rel_names


class SchemaIntrospector:
    """
    Service to introspect database schema from GraphQL/Hasura.
    Caches schema information to avoid repeated API calls.
    """
    
    def __init__(self, client, cache_ttl: int = None):
        """
        Initialize schema introspector.
        
        Args:
            client: GraphQL client instance (must have _execute_graphql method for Hasura)
            cache_ttl: Cache time-to-live in seconds. If None, reads from
                       graphql.schema_cache.ttl_seconds in config.yaml (default: 3600).
        """
        self.client = client
        self.config = get_config()
        # Use caller-supplied TTL or read from config so this in-memory cache
        # stays in sync with the disk cache in SchemaAnalyzer.
        self.cache_ttl = cache_ttl if cache_ttl is not None else self.config.get(
            "graphql.schema_cache.ttl_seconds", 3600
        )
        self._schema_cache: Optional[Dict[str, TableInfo]] = None
        self._cache_timestamp: Optional[float] = None
        self._is_mock = hasattr(client, '_table_schemas')  # Detect mock client
        self.force_refresh_schema = self.config.get("graphql.force_refresh_schema", False)
    
    def introspect_schema(self) -> Dict[str, TableInfo]:
        """
        Introspect the complete database schema.
        
        Args:
            force_refresh: If True, bypass cache and fetch fresh schema
            
        Returns:
            Dictionary mapping table names to TableInfo objects
        """
        # Check cache validity
        if not self.force_refresh_schema and self._is_cache_valid():
            # print("  📦 Using cached schema:")
            #print(self._schema_cache)
            return self._schema_cache
        
        #print("  🔍 Introspecting database schema...")
        
        if self._is_mock:
            schema = self._introspect_mock_schema()
        else:
            schema = self._introspect_hasura_schema()
        
        # Update cache
        self._schema_cache = schema
        self._cache_timestamp = time.time()
        
        #print(f"  ✓ Discovered {len(schema)} tables")
        #print(self._schema_cache)
        return schema
    
    def get_table_info(self, table_name: str) -> Optional[TableInfo]:
        """
        Get information about a specific table.
        
        Args:
            table_name: Name of the table
            
        Returns:
            TableInfo object or None if table not found
        """
        schema = self.introspect_schema()
        return schema.get(table_name)
    
    def get_table_relationships(self, table_name: str) -> List[RelationshipInfo]:
        """
        Get all relationships for a specific table.
        
        Args:
            table_name: Name of the table
            
        Returns:
            List of RelationshipInfo objects
        """
        table_info = self.get_table_info(table_name)
        return table_info.relationships if table_info else []
    
    def get_all_table_names(self) -> List[str]:
        """Get list of all table names."""
        schema = self.introspect_schema()
        return list(schema.keys())

    # ------------------------------------------------------------------
    # Mutation helpers (consumed by MutationPlannerAgent)
    # ------------------------------------------------------------------

    def get_mutable_tables(self) -> Dict[str, Dict[str, bool]]:
        """
        Return tables that the current role can write to.

        Returns:
            Dict mapping table_name → {can_insert: bool, can_update: bool}
            Only tables with at least one True permission are included.
        """
        schema = self.introspect_schema()
        return {
            name: {'can_insert': info.can_insert, 'can_update': info.can_update}
            for name, info in schema.items()
            if info.can_insert or info.can_update
        }

    def get_mutable_fields(self, table_name: str) -> List[str]:
        """
        Return all writable field and relationship names for a table.
        Includes mutable scalar columns AND relationship names (FK / nested targets).
        Returns [] if the table is not found or has no write permission at all.

        The LLM (MutationPlannerAgent) decides which subset is actually needed.
        """
        table_info = self.get_table_info(table_name)
        if not table_info or (not table_info.can_insert and not table_info.can_update):
            return []
        return table_info.get_mutable_fields()
    
    def clear_cache(self):
        """Clear the schema cache."""
        self._schema_cache = None
        self._cache_timestamp = None
        print("  🗑️ Schema cache cleared")
    
    def _is_cache_valid(self) -> bool:
        """Check if cached schema is still valid."""
        if self._schema_cache is None or self._cache_timestamp is None:
            return False
        
        elapsed = time.time() - self._cache_timestamp
        return elapsed < self.cache_ttl
    
    # Columns that are never writable — auto-managed by the DB
    _IMMUTABLE_COLUMNS = {'id', 'created_at', 'updated_at', 'delivered_at'}

    # Per-table mutation permission defaults for the mock client
    _MOCK_PERMISSIONS: Dict[str, Dict[str, bool]] = {
        'menu_items': {'can_insert': True,  'can_update': True},
        'orders':     {'can_insert': True,  'can_update': True},
        'categories': {'can_insert': False, 'can_update': False},
        'policies':   {'can_insert': False, 'can_update': False},
    }

    def _introspect_mock_schema(self) -> Dict[str, TableInfo]:
        """Introspect schema from mock client (simulated data)."""
        schema = {}
        
        # Get table schemas from mock client
        for table_name in self.client.get_available_tables():
            schema_info = self.client.get_table_schema(table_name)
            if not schema_info.get('success'):
                continue
            
            table_schema = schema_info['schema']
            perms = self._MOCK_PERMISSIONS.get(table_name, {'can_insert': False, 'can_update': False})

            # Convert columns to FieldInfo objects
            fields = []
            for col_name in table_schema.get('columns', []):
                field_type = self._infer_field_type(col_name)
                is_pk = col_name == 'id'
                is_immutable = col_name in self._IMMUTABLE_COLUMNS

                fields.append(FieldInfo(
                    name=col_name,
                    type=field_type,
                    is_nullable=not is_pk,
                    is_primary_key=is_pk,
                    is_mutable=not is_immutable and not is_pk  # PKs are always immutable
                ))
            
            # Mock relationships (hardcoded for common patterns)
            relationships = self._get_mock_relationships(table_name)
            
            schema[table_name] = TableInfo(
                name=table_name,
                fields=fields,
                relationships=relationships,
                description=table_schema.get('description'),
                can_insert=perms['can_insert'],
                can_update=perms['can_update']
            )
        
        return schema
    
    def _introspect_hasura_schema(self) -> Dict[str, TableInfo]:
        """Introspect schema from Hasura using GraphQL introspection API."""
        schema = {}

        tables = self.client.get_available_tables()

        # Step A: detect which tables the current role can insert / update
        mutation_permissions = self._introspect_mutation_permissions()

        for table_name in tables:
            try:
                table_info_query = f"""
                query {{
                __type(name: "{table_name}") {{
                    name
                    fields {{
                    name
                    type {{
                        name
                        kind
                        ofType {{
                        name
                        kind
                        ofType {{
                            name
                            kind
                            ofType {{
                            name
                            kind
                            }}
                        }}
                        }}
                    }}
                    }}
                }}
                }}
                """

                result = self.client._execute_graphql(table_info_query)
                type_info = result.get("data", {}).get("__type")

                if not type_info:
                    continue

                perms = mutation_permissions.get(table_name, {'can_insert': False, 'can_update': False})
                can_insert = perms['can_insert']
                can_update = perms['can_update']

                # Step B: fetch mutable update fields from <table>_set_input
                update_mutable: set = set()
                if can_update:
                    update_mutable = self._introspect_set_input_fields(table_name)

                fields: List[FieldInfo] = []
                relationships: List[RelationshipInfo] = []

                for field_data in type_info.get("fields", []):
                    field_name = field_data["name"]
                    field_type_info = field_data["type"]

                    analyzed = self._analyze_graphql_type(field_type_info)

                    base_kind = analyzed["base_kind"]
                    base_name = analyzed["base_name"]
                    is_list = analyzed["is_list"]
                    is_non_null = analyzed["is_non_null"]

                    # Detect relationships
                    if base_kind == "OBJECT":
                        if is_list:
                            relationships.append(
                                RelationshipInfo(
                                    name=field_name,
                                    type=RelationshipType.ARRAY,
                                    remote_table=base_name
                                )
                            )
                        else:
                            relationships.append(
                                RelationshipInfo(
                                    name=field_name,
                                    type=RelationshipType.OBJECT,
                                    remote_table=base_name
                                )
                            )
                    else:
                        # Scalar field — determine mutability
                        # If we have set_input data, use it; otherwise fall back to
                        # excluding known auto-managed columns.
                        is_pk = (field_name == "id")
                        if update_mutable:
                            field_is_mutable = field_name in update_mutable
                        else:
                            field_is_mutable = field_name not in self._IMMUTABLE_COLUMNS

                        fields.append(
                            FieldInfo(
                                name=field_name,
                                type=base_name if base_name else "String",
                                is_nullable=not is_non_null,
                                is_primary_key=is_pk,
                                is_mutable=field_is_mutable and not is_pk  # PKs are always immutable
                            )
                        )

                schema[table_name] = TableInfo(
                    name=table_name,
                    fields=fields,
                    relationships=relationships,
                    can_insert=can_insert,
                    can_update=can_update
                )

            except Exception as e:
                print(f"  ⚠️ Error introspecting table {table_name}: {e}")
                continue
        
        schema = self._apply_metadata_field_mappings(schema)
        return schema

    def _introspect_mutation_permissions(self) -> Dict[str, Dict[str, bool]]:
        """
        Query the mutation_root type to discover which tables the current
        JWT role may insert into or update.

        Returns:
            Dict mapping table_name → {can_insert: bool, can_update: bool}
        """
        permissions: Dict[str, Dict[str, bool]] = {}
        query = """
        query {
          __type(name: "mutation_root") {
            fields {
              name
            }
          }
        }
        """
        try:
            result = self.client._execute_graphql(query)
            mutation_fields = (
                result.get("data", {}).get("__type") or {}
            ).get("fields", [])

            for f in mutation_fields:
                name = f["name"]
                # insert_<table> or insert_<table>_one
                if name.startswith("insert_") and not name.endswith("_one"):
                    table = name[len("insert_"):]
                    permissions.setdefault(table, {'can_insert': False, 'can_update': False})
                    permissions[table]['can_insert'] = True
                elif name.startswith("update_") and not name.endswith("_by_pk") and not name.endswith("_many"):
                    table = name[len("update_"):]
                    permissions.setdefault(table, {'can_insert': False, 'can_update': False})
                    permissions[table]['can_update'] = True

        except Exception as e:
            print(f"  ⚠️ Could not introspect mutation_root: {e}")

        return permissions

    def _introspect_set_input_fields(self, table_name: str) -> set:
        """
        Introspect <table_name>_set_input to find which fields are exposed
        for update mutations (i.e., are mutable).

        Returns:
            Set of field names that may appear in an update _set clause.
        """
        mutable: set = set()
        input_type = f"{table_name}_set_input"
        query = f"""
        query {{
          __type(name: "{input_type}") {{
            inputFields {{
              name
            }}
          }}
        }}
        """
        try:
            result = self.client._execute_graphql(query)
            type_data = (result.get("data", {}).get("__type") or {})
            for f in type_data.get("inputFields", []):
                mutable.add(f["name"])
        except Exception as e:
            print(f"  ⚠️ Could not introspect {input_type}: {e}")

        return mutable

    def _load_relational_metadata(self) -> Dict[str, Any]:
        """
        Load client-provided relational metadata file.
        """
        try:
            metadata_path = os.path.join(os.getcwd(), "relational_metadata.json")
            if not os.path.exists(metadata_path):
                print("  ⚠️ relational_metadata.json not found.")
                return {}

            with open(metadata_path, "r") as f:
                metadata = json.load(f)

            return metadata.get("tables", {})
        except Exception as e:
            print(f"  ⚠️ Failed to load relational metadata: {e}")
            return {}
    
    def _apply_metadata_field_mappings(self, schema: Dict[str, TableInfo]) -> Dict[str, TableInfo]:
        """
        Enrich relationships with exact local → remote field mappings
        from relational_metadata.json.
        """
        metadata_tables = self._load_relational_metadata()

        if not metadata_tables:
            print("  ⚠️ No relational metadata loaded — field mappings will be empty.")
            return schema

        #print(f"  📎 Loaded relational metadata for {len(metadata_tables)} tables.")

        for table_name, table_info in schema.items():

            table_meta = metadata_tables.get(table_name)
            if not table_meta:
                continue

            relationships_meta = table_meta.get("relationships", [])

            for rel in table_info.relationships:
                matched = False
                for meta_rel in relationships_meta:
                    if meta_rel["target_table"] == rel.remote_table and not rel.field_mapping:
                        local_cols = meta_rel.get("local_columns", [])
                        target_cols = meta_rel.get("target_columns", [])

                        if len(local_cols) == len(target_cols) and local_cols:
                            rel.field_mapping = dict(zip(local_cols, target_cols))
                            matched = True
                            #print(f"    ✓ {table_name}.{rel.name} → {rel.remote_table}: {rel.field_mapping}")
                            break  # Only match the first metadata entry per relationship

                if not matched and not rel.field_mapping:
                    print(f"    ✗ No metadata match for {table_name}.{rel.name} → {rel.remote_table}")

        return schema


    def _analyze_graphql_type(self, type_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Recursively analyze GraphQL type structure.

        Returns:
            {
                "base_kind": str,
                "base_name": str,
                "is_list": bool,
                "is_non_null": bool
            }
        """
        is_list = False
        is_non_null = False

        current = type_info

        while current:
            kind = current.get("kind")
            name = current.get("name")

            if kind == "NON_NULL":
                is_non_null = True
                current = current.get("ofType")
                continue

            if kind == "LIST":
                is_list = True
                current = current.get("ofType")
                continue

            # Base type reached
            return {
                "base_kind": kind,
                "base_name": name,
                "is_list": is_list,
                "is_non_null": is_non_null
            }

        return {
            "base_kind": None,
            "base_name": None,
            "is_list": False,
            "is_non_null": False
        }
    
    
    def _infer_field_type(self, field_name: str) -> str:
        """Infer field type from field name (for mock data)."""
        field_lower = field_name.lower()
        
        if 'id' in field_lower:
            return 'Int'
        elif field_lower in ['price', 'total', 'rating', 'calories']:
            return 'Float'
        elif field_lower in ['is_vegetarian', 'is_available']:
            return 'Boolean'
        elif 'count' in field_lower or field_lower.endswith('_minutes'):
            return 'Int'
        elif field_lower in ['created_at', 'updated_at', 'delivered_at', 'estimated_delivery']:
            return 'String'  # timestamps as strings
        elif field_lower in ['sizes', 'toppings', 'items']:
            return 'Array'
        else:
            return 'String'
    
    def _get_mock_relationships(self, table_name: str) -> List[RelationshipInfo]:
        """Get mock relationships for common table patterns."""
        relationships = []
        
        if table_name == 'menu_items':
            # menu_items has a category relationship
            relationships.append(RelationshipInfo(
                name='category_rel',
                type=RelationshipType.OBJECT,
                remote_table='categories',
                field_mapping={'category': 'name'}
            ))
        
        elif table_name == 'orders':
            # orders has relationships to users and order_items
            relationships.append(RelationshipInfo(
                name='items',
                type=RelationshipType.ARRAY,
                remote_table='order_items',
                field_mapping={'id': 'order_id'}
            ))
        
        elif table_name == 'order_items':
            # order_items has relationships to orders and menu_items
            relationships.append(RelationshipInfo(
                name='order',
                type=RelationshipType.OBJECT,
                remote_table='orders',
                field_mapping={'order_id': 'id'}
            ))
            relationships.append(RelationshipInfo(
                name='menu_item',
                type=RelationshipType.OBJECT,
                remote_table='menu_items',
                field_mapping={'menu_item_id': 'id'}
            ))
        
        return relationships


# Global instance
_schema_introspector = None


def get_schema_introspector(client=None) -> SchemaIntrospector:
    """Get the global schema introspector instance."""
    global _schema_introspector
    
    if _schema_introspector is None:
        if client is None:
            from services.graphql.client import get_graphql_client
            client = get_graphql_client()
        _schema_introspector = SchemaIntrospector(client)
    
    return _schema_introspector


def reset_schema_introspector():
    """Reset the global schema introspector (useful for testing)."""
    global _schema_introspector
    _schema_introspector = None
