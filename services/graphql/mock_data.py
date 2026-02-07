"""
Mock GraphQL data for development and testing.
Simulates responses from Hasura/Directus for menu items, orders, etc.
"""

from typing import Dict, Any, List, Optional

# Mock menu data (food delivery example)
MOCK_MENU_ITEMS = [
    {
        "id": "pizza_001",
        "name": "Margherita Pizza",
        "category": "Pizza",
        "description": "Classic pizza with fresh tomatoes, mozzarella cheese, and basil",
        "price": 12.99,
        "sizes": ["Small", "Medium", "Large"],
        "toppings": ["Extra Cheese", "Mushrooms", "Olives"],
        "is_vegetarian": True,
        "is_available": True,
        "prep_time_minutes": 20,
        "calories": 850,
        "rating": 4.5,
        "reviews_count": 234
    },
    {
        "id": "pizza_002",
        "name": "Pepperoni Pizza",
        "category": "Pizza",
        "description": "Loaded with pepperoni slices and melted mozzarella",
        "price": 14.99,
        "sizes": ["Small", "Medium", "Large"],
        "toppings": ["Extra Pepperoni", "Jalapeños", "Onions"],
        "is_vegetarian": False,
        "is_available": True,
        "prep_time_minutes": 20,
        "calories": 1050,
        "rating": 4.7,
        "reviews_count": 456
    },
    {
        "id": "pizza_003",
        "name": "BBQ Chicken Pizza",
        "category": "Pizza",
        "description": "Grilled chicken with BBQ sauce, red onions, and cilantro",
        "price": 15.99,
        "sizes": ["Small", "Medium", "Large"],
        "toppings": ["Extra Chicken", "Bacon", "Pineapple"],
        "is_vegetarian": False,
        "is_available": True,
        "prep_time_minutes": 25,
        "calories": 980,
        "rating": 4.6,
        "reviews_count": 189
    },
    {
        "id": "burger_001",
        "name": "Classic Cheeseburger",
        "category": "Burgers",
        "description": "Juicy beef patty with cheddar, lettuce, tomato, and special sauce",
        "price": 9.99,
        "sizes": ["Regular", "Double"],
        "toppings": ["Bacon", "Extra Cheese", "Fried Egg"],
        "is_vegetarian": False,
        "is_available": True,
        "prep_time_minutes": 15,
        "calories": 680,
        "rating": 4.4,
        "reviews_count": 312
    },
    {
        "id": "burger_002",
        "name": "Veggie Burger",
        "category": "Burgers",
        "description": "Plant-based patty with avocado, sprouts, and vegan mayo",
        "price": 10.99,
        "sizes": ["Regular"],
        "toppings": ["Extra Avocado", "Grilled Onions", "Jalapeños"],
        "is_vegetarian": True,
        "is_available": True,
        "prep_time_minutes": 15,
        "calories": 520,
        "rating": 4.3,
        "reviews_count": 156
    },
    {
        "id": "pasta_001",
        "name": "Spaghetti Carbonara",
        "category": "Pasta",
        "description": "Creamy pasta with bacon, egg, and parmesan cheese",
        "price": 13.99,
        "sizes": ["Regular", "Large"],
        "toppings": ["Extra Bacon", "Truffle Oil"],
        "is_vegetarian": False,
        "is_available": True,
        "prep_time_minutes": 18,
        "calories": 920,
        "rating": 4.6,
        "reviews_count": 278
    },
    {
        "id": "pasta_002",
        "name": "Penne Arrabbiata",
        "category": "Pasta",
        "description": "Spicy tomato sauce with garlic and chili flakes",
        "price": 11.99,
        "sizes": ["Regular", "Large"],
        "toppings": ["Grilled Chicken", "Parmesan"],
        "is_vegetarian": True,
        "is_available": True,
        "prep_time_minutes": 15,
        "calories": 680,
        "rating": 4.4,
        "reviews_count": 198
    },
    {
        "id": "salad_001",
        "name": "Caesar Salad",
        "category": "Salads",
        "description": "Crisp romaine lettuce with caesar dressing, croutons, and parmesan",
        "price": 8.99,
        "sizes": ["Regular", "Large"],
        "toppings": ["Grilled Chicken", "Shrimp", "Bacon Bits"],
        "is_vegetarian": True,
        "is_available": True,
        "prep_time_minutes": 10,
        "calories": 380,
        "rating": 4.5,
        "reviews_count": 167
    },
    {
        "id": "drink_001",
        "name": "Fresh Lemonade",
        "category": "Beverages",
        "description": "House-made lemonade with fresh lemons and mint",
        "price": 3.99,
        "sizes": ["Regular", "Large"],
        "toppings": [],
        "is_vegetarian": True,
        "is_available": True,
        "prep_time_minutes": 5,
        "calories": 120,
        "rating": 4.8,
        "reviews_count": 89
    },
    {
        "id": "dessert_001",
        "name": "Chocolate Lava Cake",
        "category": "Desserts",
        "description": "Warm chocolate cake with a molten center, served with vanilla ice cream",
        "price": 7.99,
        "sizes": ["Regular"],
        "toppings": ["Extra Ice Cream", "Whipped Cream"],
        "is_vegetarian": True,
        "is_available": True,
        "prep_time_minutes": 12,
        "calories": 580,
        "rating": 4.9,
        "reviews_count": 345
    }
]

# Mock categories
MOCK_CATEGORIES = [
    {"id": "cat_001", "name": "Pizza", "description": "Hand-tossed pizzas with fresh ingredients"},
    {"id": "cat_002", "name": "Burgers", "description": "Juicy burgers made with premium beef"},
    {"id": "cat_003", "name": "Pasta", "description": "Authentic Italian pasta dishes"},
    {"id": "cat_004", "name": "Salads", "description": "Fresh and healthy salads"},
    {"id": "cat_005", "name": "Beverages", "description": "Refreshing drinks and beverages"},
    {"id": "cat_006", "name": "Desserts", "description": "Sweet treats to end your meal"}
]

# Mock orders (for user-specific queries)
MOCK_ORDERS = [
    {
        "id": "order_001",
        "user_id": "user_123",
        "items": [
            {"item_id": "pizza_001", "name": "Margherita Pizza", "quantity": 2, "size": "Large"},
            {"item_id": "drink_001", "name": "Fresh Lemonade", "quantity": 2, "size": "Regular"}
        ],
        "total": 33.96,
        "status": "delivered",
        "created_at": "2025-01-03T15:30:00Z",
        "delivered_at": "2025-01-03T16:15:00Z"
    },
    {
        "id": "order_002",
        "user_id": "user_123",
        "items": [
            {"item_id": "burger_001", "name": "Classic Cheeseburger", "quantity": 1, "size": "Double"},
            {"item_id": "salad_001", "name": "Caesar Salad", "quantity": 1, "size": "Regular"}
        ],
        "total": 18.98,
        "status": "preparing",
        "created_at": "2025-01-03T20:00:00Z",
        "estimated_delivery": "2025-01-03T20:45:00Z"
    }
]

# Mock store policies
MOCK_POLICIES = [
    {
        "id": "policy_001",
        "type": "delivery",
        "title": "Delivery Policy",
        "content": "We deliver within a 10-mile radius. Free delivery on orders over $25. Delivery typically takes 30-45 minutes depending on location and order volume. Hot food guarantee: if your order arrives cold, we'll replace it for free."
    },
    {
        "id": "policy_002",
        "type": "refund",
        "title": "Refund Policy",
        "content": "We offer full refunds for orders cancelled within 5 minutes of placing. For quality issues, please contact us within 30 minutes of delivery for a replacement or refund. Photos may be required for quality complaints."
    },
    {
        "id": "policy_003",
        "type": "allergens",
        "title": "Allergen Information",
        "content": "Our kitchen handles nuts, dairy, gluten, and shellfish. While we take precautions, cross-contamination may occur. Please inform us of any allergies when ordering. Detailed allergen information is available for each menu item."
    }
]


def get_mock_menu_items(category: Optional[str] = None, search_term: Optional[str] = None, vegetarian_only: bool = False) -> List[Dict[str, Any]]:
    """Get mock menu items with optional filtering."""
    items = MOCK_MENU_ITEMS.copy()
    
    if category:
        items = [i for i in items if i["category"].lower() == category.lower()]
    
    if search_term:
        search_lower = search_term.lower().strip()
        
        # Skip filtering for generic/broad terms that mean "show all"
        generic_terms = [
            "menu", "items", "food", "products", "all", "available",
            "menu items", "all menu items", "all items", "everything",
            "all menu items available", "what you have", "what's available"
        ]
        
        if search_lower not in generic_terms and search_lower:
            # Only filter if it's a specific search term
            items = [i for i in items if 
                     search_lower in i["name"].lower() or 
                     search_lower in i["description"].lower() or
                     search_lower in i["category"].lower()]
    
    if vegetarian_only:
        items = [i for i in items if i["is_vegetarian"]]
    
    return items


def get_mock_categories() -> List[Dict[str, Any]]:
    """Get all mock categories."""
    return MOCK_CATEGORIES.copy()


def get_mock_orders(user_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Get mock orders for a user."""
    if user_id:
        return [o for o in MOCK_ORDERS if o["user_id"] == user_id]
    return MOCK_ORDERS.copy()


def get_mock_policies(policy_type: Optional[str] = None) -> List[Dict[str, Any]]:
    """Get mock policies with optional type filter."""
    if policy_type:
        policy_type_lower = policy_type.lower()
        
        # Handle exact match first
        exact_matches = [p for p in MOCK_POLICIES if p["type"].lower() == policy_type_lower]
        if exact_matches:
            return exact_matches
        
        # Handle partial match (e.g., "refund policy" should match "refund")
        partial_matches = [p for p in MOCK_POLICIES if p["type"].lower() in policy_type_lower or policy_type_lower in p["type"].lower()]
        if partial_matches:
            return partial_matches
        
        # Handle keyword matching (e.g., "return" or "money back" should match "refund")
        keyword_map = {
            "refund": ["return", "money back", "cancel order", "refund"],
            "delivery": ["deliver", "shipping", "arrival", "delivery"],
            "allergens": ["allergy", "allergen", "dietary", "ingredients"]
        }
        
        for policy_key, keywords in keyword_map.items():
            if any(kw in policy_type_lower for kw in keywords):
                return [p for p in MOCK_POLICIES if p["type"] == policy_key]
    
    return MOCK_POLICIES.copy()


def get_mock_item_by_id(item_id: str) -> Optional[Dict[str, Any]]:
    """Get a specific menu item by ID."""
    for item in MOCK_MENU_ITEMS:
        if item["id"] == item_id:
            return item.copy()
    return None
