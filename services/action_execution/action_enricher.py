"""
Action Enricher - Resolves entity lookups and calculates fields before mutation.
"""
import json
from typing import Dict, Any, List, Optional
import re

from services.graphql.client import get_graphql_client
from services.graphql.query_planner import get_query_planner_agent
from services.graphql.query_generator import get_query_generator

class ActionEnricher:
    """
    Service that 'enriches' ActionIntent data by resolving entity IDs and calculating fields.
    """
    
    def __init__(self):
        self.client = get_graphql_client()
        self.query_planner = get_query_planner_agent()
        self.query_generator = get_query_generator()

    def enrich_intent(self, action_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Processes action_data to resolve 'lookup_by' fields and calculate totals.
        """
        if not action_data or "tables_data" not in action_data:
            return action_data

        # 1. Resolve Foreign Keys via Lookups
        for table_name, table_state in action_data["tables_data"].items():
            filled = table_state.get("filled", {})
            for field_name, value in list(filled.items()):
                if isinstance(value, dict) and "lookup_by" in value:
                    resolved_id, extra_data = self._resolve_entity(table_name, field_name, value["lookup_by"])
                    if resolved_id:
                        # Replace the lookup dict with the actual ID
                        filled[field_name] = resolved_id
                        # Store extra data (like price) for calculations
                        if extra_data:
                            table_state.setdefault("metadata", {}).update(extra_data)
                    else:
                        # If resolution fails, maybe move it to missing?
                        # For now, we'll mark a failure in the status
                        print(f"  ⚠️ Failed to resolve entity for {table_name}.{field_name}")

        # 2. Calculate Business Logic (Total, Price)
        self._calculate_business_logic(action_data)

        return action_data

    def _resolve_entity(self, table_name: str, field_name: str, lookup: Dict[str, str]) -> tuple:
        """
        Uses QueryPlanner to find an ID based on a name or other unique field.
        """
        # Improved table inference
        remote_table = None
        if field_name == "menu_item_id":
            remote_table = "menu_items"
        elif field_name == "category_id":
            remote_table = "categories"
        elif field_name == "user_id":
            remote_table = "users"
        
        if not remote_table:
            # Fallback: strip _id and pluralize
            remote_table = field_name.replace("_id", "") + "s"

        search_term = next(iter(lookup.values()))
        # Use a more natural prompt for the QueryPlanner to encourage ILIKE/fuzzy matching
        user_query = f"Find the id and price of {remote_table} where the {list(lookup.keys())[0]} is similar to '{search_term}'"
        
        try:
            # QueryPlannerAgent.plan_query returns (QueryPlan, graphql_query)
            plan, query_str = self.query_planner.plan_query(user_query)
            result_wrapper = self.client.execute_graphql_query(query_str)
            
            if not result_wrapper.get("success"):
                print(f"  ⚠️ GraphQL lookup failed: {result_wrapper.get('error')}")
                return None, None

            data = result_wrapper.get("data")
            if data and isinstance(data, list):
                row = data[0]
                resolved_id = row.get("id")
                # Return ID and any other useful fields like price
                metadata = {k: v for k, v in row.items() if k != "id"}
                return resolved_id, metadata
            elif data and isinstance(data, dict):
                # Handle single-object return if applicable
                resolved_id = data.get("id")
                metadata = {k: v for k, v in data.items() if k != "id"}
                return resolved_id, metadata

        except Exception as e:
            print(f"  ⚠️ Lookup failed for {remote_table}: {e}")
            
        return None, None

    def _calculate_business_logic(self, action_data: Dict[str, Any]):
        """
        Implements total = quantity * price and other derivations.
        """
        tables = action_data["tables_data"]
        
        # Order Item Price and Order Total logic
        if "order_items" in tables and "orders" in tables:
            items_state = tables["order_items"]
            order_state = tables["orders"]
            
            qty = items_state.get("filled", {}).get("quantity", 1)
            price = items_state.get("metadata", {}).get("price")
            
            if price is not None:
                # Update order_items price_at_order
                items_state["filled"]["price_at_order"] = float(price)
                # Calculate total
                total = float(qty) * float(price)
                order_state["filled"]["total"] = total
                print(f"  💰 Calculated Total: {total} ({qty} x {price})")

_enricher = None

def get_action_enricher() -> ActionEnricher:
    global _enricher
    if _enricher is None:
        _enricher = ActionEnricher()
    return _enricher
