"""
Test cases for LLM-Based Database Router Agent.
Tests the new LLM-based routing system for database queries.

Run with: python -m services.graphql.test_database_agent
"""

import sys
import os
from typing import Dict, Any, List


def test_graphql_client():
    """Test the GraphQL client table-based methods."""
    print("\n" + "="*60)
    print("Testing GraphQL Client")
    print("="*60)
    
    from services.graphql.client import MockGraphQLClient
    client = MockGraphQLClient()
    
    # Test 1: Get available tables
    print("\n[Test 1] get_available_tables()")
    tables = client.get_available_tables()
    print(f"  Available tables: {tables}")
    assert "menu_items" in tables, "menu_items should be available"
    assert "categories" in tables, "categories should be available"
    assert "orders" in tables, "orders should be available"
    assert "policies" in tables, "policies should be available"
    print("  ✓ PASSED")
    
    # Test 2: Query menu_items table
    print("\n[Test 2] query_table('menu_items', {})")
    result = client.query_table("menu_items", {})
    print(f"  Success: {result['success']}")
    print(f"  Items returned: {len(result['data'])}")
    assert result["success"], "Query should succeed"
    assert len(result["data"]) > 0, "Should return menu items"
    print("  ✓ PASSED")
    
    # Test 3: Query with filter
    print("\n[Test 3] query_table('menu_items', {'category': 'Pizza'})")
    result = client.query_table("menu_items", {"category": "Pizza"})
    print(f"  Success: {result['success']}")
    print(f"  Items returned: {len(result['data'])}")
    for item in result["data"]:
        assert item["category"] == "Pizza", f"Item should be Pizza: {item['name']}"
    print("  ✓ PASSED")
    
    # Test 4: Query invalid table
    print("\n[Test 4] query_table('invalid_table', {})")
    result = client.query_table("invalid_table", {})
    print(f"  Success: {result['success']}")
    print(f"  Error: {result['error']}")
    assert not result["success"], "Query should fail"
    assert "Unknown table" in result["error"], "Should indicate unknown table"
    print("  ✓ PASSED")
    
    # Test 5: Query all tables
    print("\n[Test 5] query_all_tables()")
    result = client.query_all_tables()
    print(f"  Success: {result['success']}")
    print(f"  Tables queried: {result['tables_queried']}")
    assert result["success"], "Query should succeed"
    assert "menu_items" in result["data"], "Should have menu_items"
    print("  ✓ PASSED")
    
    # Test 6: Get table schema
    print("\n[Test 6] get_table_schema('menu_items')")
    result = client.get_table_schema("menu_items")
    print(f"  Success: {result['success']}")
    print(f"  Schema: {result['schema']}")
    assert result["success"], "Query should succeed"
    assert "columns" in result["schema"], "Should have columns"
    print("  ✓ PASSED")
    
    print("\n✅ All GraphQL Client tests passed!")


def test_database_agent():
    """Test the LLM database router agent."""
    print("\n" + "="*60)
    print("Testing Database Router Agent")
    print("="*60)
    
    from services.graphql.database_agent import DatabaseRouterAgent
    agent = DatabaseRouterAgent()
    available_tables = ["menu_items", "categories", "orders", "policies"]
    
    # Test 1: Schema description
    print("\n[Test 1] get_table_schema_description()")
    description = agent.get_table_schema_description(available_tables)
    print(f"  Description length: {len(description)} chars")
    assert "menu_items" in description, "Should include menu_items"
    assert "policies" in description, "Should include policies"
    print("  ✓ PASSED")
    
    # Test 2: Parse LLM response
    print("\n[Test 2] _parse_llm_response() with valid JSON")
    valid_response = '{"table": "menu_items", "params": {"search": "pizza"}, "confidence": 0.9}'
    result = agent._parse_llm_response(valid_response, available_tables)
    print(f"  Parsed result: {result}")
    assert result["table"] == "menu_items", "Should parse table"
    assert result["confidence"] == 0.9, "Should parse confidence"
    print("  ✓ PASSED")
    
    # Test 3: Parse invalid table
    print("\n[Test 3] _parse_llm_response() with invalid table")
    invalid_response = '{"table": "nonexistent_table", "params": {}, "confidence": 0.8}'
    result = agent._parse_llm_response(invalid_response, available_tables)
    print(f"  Parsed result: {result}")
    assert result["table"] == "menu_items", "Should fallback to menu_items"
    print("  ✓ PASSED")
    
    # Test 4: Parse malformed JSON
    print("\n[Test 4] _parse_llm_response() with malformed JSON")
    malformed_response = 'This is not valid JSON at all'
    result = agent._parse_llm_response(malformed_response, available_tables)
    print(f"  Parsed result: {result}")
    assert result["table"] == "menu_items", "Should fallback to menu_items"
    assert result["confidence"] == 0.5, "Should have low confidence"
    print("  ✓ PASSED")
    
    print("\n✅ All Database Agent tests passed!")


def test_live_routing():
    """Test live LLM routing (requires API access)."""
    print("\n" + "="*60)
    print("Testing Live LLM Routing")
    print("="*60)
    print("Note: This test makes actual LLM API calls\n")
    
    try:
        from services.graphql.database_agent import DatabaseRouterAgent
        from services.graphql.client import MockGraphQLClient
        
        agent = DatabaseRouterAgent()
        client = MockGraphQLClient()
        available_tables = client.get_available_tables()
        
        test_queries = [
            ("Tell me about Margherita Pizza", "menu_items"),
            ("What is your delivery policy?", "policies"),
            ("Show my orders", "orders"),
            ("What categories do you have?", "categories"),
            ("Show me all pizzas", "menu_items"),
            ("What are your refund terms?", "policies"),
        ]
        
        for query, expected_table in test_queries:
            print(f"\nQuery: '{query}'")
            table, params, confidence = agent.route(query, available_tables)
            print(f"  → Table: {table}")
            print(f"  → Params: {params}")
            print(f"  → Confidence: {confidence:.2f}")
            
            if table == expected_table:
                print(f"  ✓ Matched expected table: {expected_table}")
            else:
                print(f"  ⚠️ Expected: {expected_table}, Got: {table}")
        
        print("\n✅ Live routing tests completed!")
        
    except Exception as e:
        print(f"\n⚠️ Live test error: {e}")
        print("This may be expected if LLM API is not configured")


def run_all_tests():
    """Run all test suites."""
    print("\n" + "="*60)
    print("LLM DATABASE AGENT TEST SUITE")
    print("="*60)
    
    test_graphql_client()
    test_database_agent()
    
    # Ask user if they want to run live tests
    print("\n" + "-"*60)
    response = input("Run live LLM routing tests? (y/n): ").strip().lower()
    if response == 'y':
        test_live_routing()
    else:
        print("Skipping live tests")
    
    print("\n" + "="*60)
    print("ALL TESTS COMPLETED")
    print("="*60)


if __name__ == "__main__":
    run_all_tests()
