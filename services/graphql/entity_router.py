import re
from typing import Dict, Any, List, Optional, Tuple

from utilities.config_loader import get_config


# Entity to GraphQL type mappings
ENTITY_MAPPINGS = {
    # Menu/Product related
    "menu": "menu_items",
    "menu_item": "menu_items",
    "food": "menu_items",
    "dish": "menu_items",
    "pizza": "menu_items",
    "burger": "menu_items",
    "pasta": "menu_items",
    "salad": "menu_items",
    "dessert": "menu_items",
    "drink": "menu_items",
    "beverage": "menu_items",
    "product": "menu_items",
    "item": "menu_items",
    
    # Category related
    "category": "categories",
    "categories": "categories",
    "section": "categories",
    
    # Order related
    "order": "orders",
    "orders": "orders",
    "purchase": "orders",
    "transaction": "orders",
    
    # Policy related
    "policy": "policies",
    "policies": "policies",
    "delivery": "policies",
    "refund": "policies",
    "return": "policies",
    "allergen": "policies",
    "allergy": "policies"
}

# Keywords that suggest specific query types
QUERY_KEYWORDS = {
    "menu_items": [
        "menu", "food", "eat", "order", "hungry", "pizza", "burger",
        "pasta", "salad", "dessert", "drink", "beverage", "available",
        "vegetarian", "vegan", "price", "cost", "calories", "ingredients"
    ],
    "categories": [
        "categories", "sections", "types of food", "what kinds", "menu sections"
    ],
    "orders": [
        "my order", "order status", "track order", "order history",
        "previous order", "last order", "recent order"
    ],
    "policies": [
        "delivery policy", "refund policy", "return policy", "allergen",
        "allergy", "how long", "delivery time", "can I cancel"
    ]
}

class EntityRouter:
    """Routes detected entities to appropriate GraphQL queries."""
    
    def __init__(self):
        self.config = get_config()
        self.entity_mappings = ENTITY_MAPPINGS
        self.query_keywords = QUERY_KEYWORDS
    
    def route(self, user_query: str, detected_entities: Optional[Dict[str, Any]] = None) -> Tuple[str, Dict[str, Any]]:
        """
        Route a user query to the appropriate GraphQL query type.
        
        Args:
            user_query: The user's query text
            detected_entities: Entities extracted from the query
            
        Returns:
            Tuple of (query_type, query_params)
        """
        detected_entities = detected_entities or {}
        query_lower = user_query.lower()
        
        # First, check explicit entity mappings
        for entity, query_type in self.entity_mappings.items():
            if entity in query_lower:
                params = self._extract_params(query_lower, query_type, detected_entities)
                return query_type, params
        
        # Second, check keyword patterns
        for query_type, keywords in self.query_keywords.items():
            for keyword in keywords:
                if keyword in query_lower:
                    params = self._extract_params(query_lower, query_type, detected_entities)
                    return query_type, params
        
        # Default: assume menu items query
        return "menu_items", self._extract_params(query_lower, "menu_items", detected_entities)
    
    def _extract_params(self, query: str, query_type: str, detected_entities: Dict[str, Any]) -> Dict[str, Any]:
        """Extract query parameters from the user query."""
        params = {}
        
        if query_type == "menu_items":
            # Check if user wants ALL items (no filtering)
            all_items_patterns = [
                r"\ball\b.*(?:menu|items|products|food)",
                r"(?:menu|items|products|food).*\bavailable\b",
                r"(?:show|list|what).*(?:menu|items|products)",
                r"what do you (?:have|offer|serve)",
                r"what(?:'s| is) on the menu",
                r"entire menu",
                r"full menu",
                r"complete menu"
            ]
            
            wants_all = any(re.search(p, query, re.IGNORECASE) for p in all_items_patterns)
            
            if wants_all:
                # User wants all items - don't add search filter
                pass
            else:
                # Check for category filter
                categories = ["pizza", "burger", "pasta", "salad", "dessert", "beverage"]
                for cat in categories:
                    if cat in query:
                        params["category"] = cat.title()
                        break
                
                # Check for vegetarian filter
                if "vegetarian" in query or "vegan" in query:
                    params["vegetarian"] = True
                
                # Extract specific item search term only if not asking for "all"
                search_patterns = [
                    r"about (?:the )?([A-Z][a-z]+(?:\s+[A-Z]?[a-z]+)*)",  # Proper noun (e.g., "Margherita Pizza")
                    r"what is (?:the )?([A-Z][a-z]+(?:\s+[A-Z]?[a-z]+)*)",
                    r"information on ([A-Z][a-z]+(?:\s+[A-Z]?[a-z]+)*)"
                ]
                for pattern in search_patterns:
                    match = re.search(pattern, query)
                    if match:
                        search_term = match.group(1).strip()
                        # Filter out generic words
                        generic_terms = ["menu", "items", "food", "products", "all", "available"]
                        if search_term.lower() not in generic_terms:
                            params["search"] = search_term
                            break
        
        elif query_type == "orders":
            # Add user_id from detected entities
            if "user_id" in detected_entities:
                params["user_id"] = detected_entities["user_id"]
            else:
                # Default user for demo
                params["user_id"] = "user_123"
        
        elif query_type == "policies":
            # Determine policy type
            if "delivery" in query:
                params["type"] = "delivery"
            elif "refund" in query or "return" in query:
                params["type"] = "refund"
            elif "allergen" in query or "allergy" in query:
                params["type"] = "allergens"
        
        # Add any explicitly detected entities
        params.update(detected_entities)
        
        return params
    
    def get_query_description(self, query_type: str) -> str:
        """Get a human-readable description of a query type."""
        descriptions = {
            "menu_items": "menu items and products",
            "categories": "menu categories",
            "orders": "order history and status",
            "policies": "store policies and information"
        }
        return descriptions.get(query_type, query_type)


# Global entity router instance
_entity_router = None


def get_entity_router() -> EntityRouter:
    """Get the global entity router instance."""
    global _entity_router
    if _entity_router is None:
        _entity_router = EntityRouter()
    return _entity_router
