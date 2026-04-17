"""
Response handler for normalizing GraphQL responses to RAG-friendly text.
Handles JSON flattening, PII removal, and text formatting.
"""

from typing import Dict, Any, List, Optional
import json

from utilities.config_loader import get_config


class ResponseHandler:
    """Handles normalization and formatting of GraphQL responses."""
    
    def __init__(self):
        self.config = get_config()
        self.pii_fields = self.config.get('graphql.normalize.pii_fields', [])
        self.system_fields = self.config.get('graphql.normalize.remove_system_fields', [])
    
    def normalize(self, response: Dict[str, Any], query_type: str) -> Dict[str, Any]:
        """
        Normalize a GraphQL response for RAG processing.
        
        Args:
            response: Raw GraphQL response
            query_type: Type of query that produced this response
            
        Returns:
            Normalized response with text representations
        """
        if not response.get("success") or not response.get("data"):
            return {
                "success": False,
                "text": "",
                "chunks": [],
                "raw_data": response.get("data")
            }
        
        data = response["data"]
        
        # Handle list or single item
        if isinstance(data, list):
            chunks = [self._normalize_item(item, query_type) for item in data]
            text = "\n\n".join(chunk["text"] for chunk in chunks if chunk["text"])
        else:
            chunk = self._normalize_item(data, query_type)
            chunks = [chunk] if chunk["text"] else []
            text = chunk["text"]
        
        return {
            "success": True,
            "text": text,
            "chunks": chunks,
            "raw_data": data,
            "query_type": query_type
        }
    
    def _normalize_item(self, item: Dict[str, Any], query_type: str) -> Dict[str, Any]:
        """Normalize a single item to text."""
        if not item:
            return {"text": "", "entity_id": None, "entity_type": query_type}
        
        # Remove PII and system fields
        filtered = self._filter_fields(item)
        
        # Convert to readable text based on query type
        if query_type == "menu_items":
            text = self._format_menu_item(filtered)
        elif query_type == "categories":
            text = self._format_category(filtered)
        elif query_type == "orders":
            text = self._format_order(filtered)
        elif query_type == "policies":
            text = self._format_policy(filtered)
        else:
            text = self._format_generic(filtered)
        
        return {
            "text": text,
            "entity_id": item.get("id"),
            "entity_type": query_type,
            "filtered_data": filtered
        }
    
    def _filter_fields(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """Remove PII and system fields from an item."""
        filtered = {}
        
        for key, value in item.items():
            # Skip PII fields
            if key in self.pii_fields:
                continue
            
            # Skip system fields
            if key in self.system_fields:
                continue
            
            # Skip fields starting with underscore
            if key.startswith("_"):
                continue
            
            # Recursively filter nested dicts
            if isinstance(value, dict):
                value = self._filter_fields(value)
            elif isinstance(value, list):
                value = [
                    self._filter_fields(v) if isinstance(v, dict) else v
                    for v in value
                ]
            
            filtered[key] = value
        
        return filtered
    
    def _format_menu_item(self, item: Dict[str, Any]) -> str:
        """Format a menu item as readable text."""
        lines = []
        
        name = item.get("name", "Unknown Item")
        lines.append(f"**{name}**")
        
        if item.get("category"):
            lines.append(f"Category: {item['category']}")
        
        if item.get("description"):
            lines.append(f"Description: {item['description']}")
        
        if item.get("price"):
            lines.append(f"Price: ${item['price']:.2f}")
        
        if item.get("sizes"):
            sizes = ", ".join(item["sizes"]) if isinstance(item["sizes"], list) else item["sizes"]
            lines.append(f"Available sizes: {sizes}")
        
        if item.get("is_vegetarian"):
            lines.append("✓ Vegetarian")
        
        if item.get("calories"):
            lines.append(f"Calories: {item['calories']}")
        
        if item.get("prep_time_minutes"):
            lines.append(f"Preparation time: {item['prep_time_minutes']} minutes")
        
        if item.get("rating"):
            lines.append(f"Rating: {item['rating']}/5 ({item.get('reviews_count', 0)} reviews)")
        
        if item.get("is_available") is False:
            lines.append("⚠️ Currently unavailable")
        
        return "\n".join(lines)
    
    def _format_category(self, item: Dict[str, Any]) -> str:
        """Format a category as readable text."""
        name = item.get("name", "Unknown Category")
        description = item.get("description", "")
        return f"**{name}**: {description}"
    
    def _format_order(self, item: Dict[str, Any]) -> str:
        """Format an order as readable text."""
        lines = []
        
        order_id = item.get("id", "Unknown")
        lines.append(f"**Order #{order_id}**")
        
        if item.get("status"):
            status_emoji = {
                "preparing": "🍳",
                "on_the_way": "🚗",
                "delivered": "✅",
                "cancelled": "❌"
            }
            emoji = status_emoji.get(item["status"], "")
            lines.append(f"Status: {emoji} {item['status'].replace('_', ' ').title()}")
        
        if item.get("items"):
            lines.append("Items:")
            for order_item in item["items"]:
                qty = order_item.get("quantity", 1)
                name = order_item.get("name", "Unknown")
                size = order_item.get("size", "")
                size_str = f" ({size})" if size else ""
                lines.append(f"  • {qty}x {name}{size_str}")
        
        if item.get("total"):
            lines.append(f"Total: ${item['total']:.2f}")
        
        if item.get("estimated_delivery"):
            lines.append(f"Estimated delivery: {item['estimated_delivery']}")
        
        return "\n".join(lines)
    
    def _format_policy(self, item: Dict[str, Any]) -> str:
        """Format a policy as readable text."""
        title = item.get("title", "Policy")
        content = item.get("content", "")
        return f"**{title}**\n{content}"
    
    def _format_generic(self, item: Dict[str, Any]) -> str:
        """Format a generic item as readable text."""
        lines = []
        
        for key, value in item.items():
            if value is None:
                continue
            
            key_readable = key.replace("_", " ").title()
            
            if isinstance(value, list):
                value = ", ".join(str(v) for v in value)
            elif isinstance(value, dict):
                value = json.dumps(value, indent=2)
            
            lines.append(f"{key_readable}: {value}")
        
        return "\n".join(lines)


# Global response handler instance
_response_handler = None


def get_response_handler() -> ResponseHandler:
    """Get the global response handler instance."""
    global _response_handler
    if _response_handler is None:
        _response_handler = ResponseHandler()
    return _response_handler
