import os
import requests
from typing import Dict, Any, List, Optional
from abc import ABC, abstractmethod

from utilities.config_loader import get_config


class GraphQLClientBase(ABC):
    """Abstract base class for GraphQL clients."""
    
    @abstractmethod
    def query(self, query_type: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a query against the GraphQL endpoint."""
        pass
    
    @abstractmethod
    def get_available_types(self) -> List[str]:
        """Get list of available query types (legacy method)."""
        pass
    
    @abstractmethod
    def get_available_tables(self) -> List[str]:
        """Get list of all available table names."""
        pass
    
    @abstractmethod
    def query_table(self, table_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Query a specific table by name with optional parameters."""
        pass
    
    @abstractmethod
    def query_all_tables(self) -> Dict[str, Any]:
        """Query all tables and return combined data."""
        pass
    
    @abstractmethod
    def get_table_schema(self, table_name: str) -> Dict[str, Any]:
        """Get schema/structure information for a table."""
        pass


class MockGraphQLClient(GraphQLClientBase):
    """Mock GraphQL client for development and testing."""
    
    def __init__(self):
        # Table name to handler mapping
        self._table_handlers = {
            "menu_items": self._query_menu_items,
            "categories": self._query_categories,
            "orders": self._query_orders,
            "policies": self._query_policies
        }
        
        # Table schemas for LLM context
        self._table_schemas = {
            "menu_items": {
                "description": "Food menu items available for order",
                "columns": ["id", "name", "category", "description", "price", "sizes", 
                           "toppings", "is_vegetarian", "is_available", "prep_time_minutes",
                           "calories", "rating", "reviews_count"]
            },
            "categories": {
                "description": "High-level menu groupings only (e.g., 'Pizzas', 'Drinks', 'Desserts'). Use this table only when the user explicitly asks for a list of categories or menu sections, not when asking for actual products or dishes.",
                "columns": ["id", "name", "description"]
            },
            "orders": {
                "description": "User order history and status",
                "columns": ["id", "user_id", "items", "total", "status", "created_at", 
                           "delivered_at", "estimated_delivery"]
            },
            "policies": {
                "description": "Store policies and information",
                "columns": ["id", "type", "title", "content"]
            }
        }
    
    # ==================== NEW TABLE-BASED METHODS ====================
    
    def get_available_tables(self) -> List[str]:
        """Get list of all available table names."""
        return list(self._table_handlers.keys())
    
    def query_table(self, table_name: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Query a specific table by name.
        
        Args:
            table_name: Name of the table to query
            params: Optional filter parameters
            
        Returns:
            Query result with success status and data
        """
        params = params or {}
        
        if table_name not in self._table_handlers:
            return {
                "success": False,
                "error": f"Unknown table: {table_name}. Available tables: {self.get_available_tables()}",
                "data": None,
                "table": table_name
            }
        
        try:
            data = self._table_handlers[table_name](params)
            return {
                "success": True,
                "error": None,
                "data": data,
                "table": table_name,
                "query_type": table_name  # For backward compatibility
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "data": None,
                "table": table_name
            }
    
    def query_all_tables(self) -> Dict[str, Any]:
        """
        Query all tables and return combined data.
        Useful for full database context.
        """
        all_data = {}
        errors = []
        
        for table_name in self._table_handlers.keys():
            try:
                data = self._table_handlers[table_name]({})
                all_data[table_name] = data
            except Exception as e:
                errors.append(f"{table_name}: {str(e)}")
        
        return {
            "success": len(errors) == 0,
            "error": "; ".join(errors) if errors else None,
            "data": all_data,
            "tables_queried": list(self._table_handlers.keys())
        }
    
    def get_table_schema(self, table_name: str) -> Dict[str, Any]:
        """Get schema information for a table."""
        if table_name not in self._table_schemas:
            return {
                "success": False,
                "error": f"Unknown table: {table_name}",
                "schema": None
            }
        
        return {
            "success": True,
            "error": None,
            "schema": self._table_schemas[table_name]
        }
    
    # ==================== LEGACY METHODS ====================
    
    def query(self, query_type: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Execute a mock query (legacy method, redirects to query_table)."""
        return self.query_table(query_type, params)
    
    def get_available_types(self) -> List[str]:
        """Get available query types (legacy method)."""
        return self.get_available_tables()
    
    # ==================== TABLE HANDLERS ====================
    
    def _query_menu_items(self, params: Dict[str, Any]) -> List[Dict]:
        from services.graphql.mock_data import get_mock_menu_items
        return get_mock_menu_items(
            category=params.get("category"),
            search_term=params.get("search"),
            vegetarian_only=params.get("vegetarian", False)
        )
    
    def _query_categories(self, params: Dict[str, Any]) -> List[Dict]:
        from services.graphql.mock_data import get_mock_categories
        return get_mock_categories()
    
    def _query_orders(self, params: Dict[str, Any]) -> List[Dict]:
        from services.graphql.mock_data import get_mock_orders
        return get_mock_orders(user_id=params.get("user_id"))
    
    def _query_policies(self, params: Dict[str, Any]) -> List[Dict]:
        from services.graphql.mock_data import get_mock_policies
        return get_mock_policies(policy_type=params.get("type"))


class HasuraClient(GraphQLClientBase):   
    def __init__(self, endpoint: str, admin_secret: Optional[str] = None):
        self.role = "WebVox-User"
        self.endpoint = os.environ.get('HASURA_ENDPOINT', endpoint)
        self.jwt_token = os.environ.get('JWT_TOKEN', admin_secret)
        self._HEADERS = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.jwt_token or ''}", 
            "X-Hasura-Role": self.role
        }

    def _execute_graphql(self, query: str) -> Dict[str, Any]:
        """Helper function to execute a GraphQL query against the endpoint."""
        try:
            res = requests.post(self.endpoint, json={"query": query}, headers=self._HEADERS)
            res.raise_for_status()
            resp_json = res.json()
            
            if "errors" in resp_json:
                raise Exception(f"GraphQL Errors: {resp_json['errors']}")
                
            return resp_json

        except requests.exceptions.RequestException as e:
            print(f"HTTP Error executing GraphQL: {e}")
            raise
        except Exception as e:
            print(f"Error executing GraphQL: {e}")
            raise

    def get_available_tables(self) -> List[str]:
        query = """
        query {
          __type(name: "query_root") {
            fields {
              name
            }
          }
        }
        """
        
        try:
            resp_json = self._execute_graphql(query)
            
            fields = resp_json["data"]["__type"]["fields"]

            main_tables = [
                f["name"] for f in fields
                if not f["name"].startswith("_") 
                and not f["name"].endswith("_aggregate") 
                and not f["name"].endswith("_by_pk")
                and not f["name"].endswith("_stream")
            ]
            return main_tables
        except Exception:
            return [] 


    def get_table_schema(self, table_name: str) -> Dict[str, Any]:
        query = f"""
        query {{
          __type(name: "{table_name}") {{
            fields {{
              name
            }}
          }}
        }}
        """
        
        try:
            resp_json = self._execute_graphql(query)
            
            fields = resp_json["data"]["__type"]["fields"]
            column_names = [f["name"] for f in fields]
            
            return {"success": True, "schema": {"columns": column_names}}
        except Exception as e:
            return {"success": False, "error": str(e), "schema": None}


    def query_table(self, table_name: str, columns: List[str]) -> Dict[str, Any]:
        if not columns: return {"success": False, "error": "Columns list cannot be empty", "data": None}
            
        query = f"""
        query {{
          {table_name} {{
            {" ".join(columns)}
          }}
        }}
        """
        
        try:
            resp_json = self._execute_graphql(query)
            
            rows = resp_json["data"].get(table_name, [])
            return {"success": True, "data": rows}
        except Exception as e:
            return {"success": False, "error": str(e), "data": None}

    def query(self, query_type: str, params: Dict[str, Any]) -> Dict[str, Any]:
        # This generic 'query' method is too broad for the introspection focus,
        # but as per the original stub, we can return an error or implement
        # a more general GraphQL execution based on the input.
        # Sticking to the stub's original purpose:
        return {"success": False, "error": "Use get_available_tables or query_table for specific actions.", "data": None}

    def get_available_types(self) -> List[str]:
        # This would typically list all types, not just table query roots.
        # For simplicity and sticking close to the original script,
        # we'll return the same list as get_available_tables.
        return self.get_available_tables()

    def query_all_tables(self) -> Dict[str, Any]:
        tables = self.get_available_tables()
        
        all_data = {}
        all_successful = True
        
        for table in tables:
            schema_res = self.get_table_schema(table)
            
            if not schema_res["success"]:
                all_successful = False
                continue

            columns = schema_res["schema"]["columns"]
            print(f"Columns: {columns}")

            rows_res = self.query_table(table, columns)
            
            if rows_res["success"]:
                all_data[table] = rows_res["data"]
            else:
                all_successful = False

        if all_successful:
            return {"success": True, "data": all_data}
        else:
            return {"success": False, "error": "One or more table queries failed.", "data": all_data}


class DirectusClient(GraphQLClientBase):
    """Directus GraphQL client for MySQL databases."""
    
    def __init__(self, endpoint: str, access_token: Optional[str] = None):
        self.endpoint = endpoint
        self.access_token = access_token
    
    def query(self, query_type: str, params: Dict[str, Any]) -> Dict[str, Any]:
        return {"success": False, "error": "Directus client not yet implemented", "data": None}
    
    def get_available_types(self) -> List[str]:
        return []
    
    def get_available_tables(self) -> List[str]:
        return []
    
    def query_table(self, table_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        return {"success": False, "error": "Directus client not yet implemented", "data": None}
    
    def query_all_tables(self) -> Dict[str, Any]:
        return {"success": False, "error": "Directus client not yet implemented", "data": None}
    
    def get_table_schema(self, table_name: str) -> Dict[str, Any]:
        return {"success": False, "error": "Directus client not yet implemented", "schema": None}


def get_graphql_client() -> GraphQLClientBase:
    """Get the appropriate GraphQL client based on configuration."""
    config = get_config()
    mode = config.get('graphql.mode', 'mock')
    
    if mode == 'mock':
        return MockGraphQLClient()
    elif mode == 'hasura':
        endpoint = config.get('graphql.hasura.endpoint')
        admin_secret = config.get('graphql.hasura.admin_secret')
        return HasuraClient(endpoint, admin_secret)
    elif mode == 'directus':
        endpoint = config.get('graphql.directus.endpoint')
        access_token = config.get('graphql.directus.access_token')
        return DirectusClient(endpoint, access_token)
    else:
        print(f"⚠️ Unknown GraphQL mode: {mode}, falling back to mock")
        return MockGraphQLClient()
