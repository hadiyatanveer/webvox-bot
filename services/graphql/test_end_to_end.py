"""
End-to-End Test Cases for WebVox RAG Voice Accessibility System.
Tests the complete flow from user prompts to response generation.

Run with: python -m services.graphql.test_end_to_end

Logs are saved to: logs/test_end_to_end_TIMESTAMP.log
"""

import sys
import os
import time
import logging

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from utilities.logger import setup_logger

# Initialize logger
logger = setup_logger(
    name="test_end_to_end",
    log_to_file=True,
    log_to_console=True,
    level=logging.DEBUG
)


def log(message: str, level: str = "info"):
    """Log a message with the specified level."""
    if level == "debug":
        logger.debug(message)
    elif level == "warning":
        logger.warning(message)
    elif level == "error":
        logger.error(message)
    else:
        logger.info(message)


def log_header(title: str):
    """Log a formatted header."""
    log("")
    log("=" * 70)
    log(f" {title}")
    log("=" * 70)


def log_test(name: str, query: str):
    """Log test info."""
    log("")
    log("─" * 70)
    log(f"📝 Test: {name}")
    log(f"🎤 User Query: \"{query}\"")
    log("─" * 70)


def test_voicebot_manager():
    """Test the complete VoiceBotManager flow."""
    log_header("VoiceBotManager End-to-End Tests")
    
    from services.voicebot.voicebot_manager import VoiceBotManager
    
    # Initialize without LLM for chain (we'll use the modules directly)
    manager = VoiceBotManager(llm=None)
    session_id = "test_session_001"
    
    test_cases = [
        {
            "name": "Menu Item Query - Specific Item",
            "query": "Tell me about Margherita Pizza",
            "expected_category": "retrieve_information",
            "expected_table": "menu_items"
        },
        {
            "name": "Menu Item Query - All Items",
            "query": "What menu items do you have?",
            "expected_category": "retrieve_information",
            "expected_table": "menu_items"
        },
        {
            "name": "Menu Item Query - Category Filter",
            "query": "Tell me about all pizzas",
            "expected_category": "retrieve_information",
            "expected_table": "menu_items"
        },
        {
            "name": "Policy Query - Delivery",
            "query": "What is your delivery policy?",
            "expected_category": "retrieve_information",
            "expected_table": "policies"
        },
        {
            "name": "Policy Query - Refund",
            "query": "Tell me about your refund policy",
            "expected_category": "retrieve_information",
            "expected_table": "policies"
        },
        {
            "name": "Order Query",
            "query": "Show me my orders",
            "expected_category": "view_webpage",
            "expected_table": "not_supported"
        },
        {
            "name": "Categories Query",
            "query": "What food categories do you have?",
            "expected_category": "retrieve_information",
            "expected_table": "categories"
        },
        {
            "name": "Action Request (Should be unsupported)",
            "query": "Order two Pepperoni pizzas",
            "expected_category": "perform_action",
            "expected_status": "not_supported"
        },
        {
            "name": "Navigation Request (Should be unsupported)",
            "query": "Go to the desserts page",
            "expected_category": "view_webpage",
            "expected_status": "not_supported"
        },
        {
            "name": "Vegetarian Filter",
            "query": "What vegetarian options do you have?",
            "expected_category": "retrieve_information",
            "expected_table": "menu_items"
        },
    ]
    
    results = []
    
    for test in test_cases:
        log_test(test["name"], test["query"])
        
        start_time = time.time()
        
        try:
            result = manager.process_input(session_id, test["query"])
            elapsed = time.time() - start_time
            
            log("")
            log("📊 Result:")
            log(f"   Category: {result.get('category', 'N/A')}")
            log(f"   Intent: {result.get('intent', 'N/A')}")
            log(f"   Confidence: {result.get('confidence', 'N/A')}")
            log(f"   Status: {result.get('status', 'N/A')}")
            log(f"   Time: {elapsed:.2f}s")
            
            # Show response (truncated)
            response = result.get('response', '')
            if len(response) > 200:
                log(f"")
                log(f"💬 Response (truncated): {response[:200]}...")
            else:
                log(f"")
                log(f"💬 Response: {response}")
            
            # Show metadata
            metadata = result.get('metadata', {})
            if metadata:
                log(f"")
                log(f"📦 Metadata: {metadata}")
            
            # Check expectations
            passed = True
            if "expected_category" in test:
                if result.get("category") != test["expected_category"]:
                    log(f"")
                    log(f"   ⚠️ Expected category: {test['expected_category']}, got: {result.get('category')}", "warning")
                    passed = False
            
            if "expected_status" in test:
                if result.get("status") != test["expected_status"]:
                    log(f"")
                    log(f"   ⚠️ Expected status: {test['expected_status']}, got: {result.get('status')}", "warning")
                    passed = False
            
            if passed:
                log("")
                log("   ✅ Test PASSED")
            else:
                log("")
                log("   ❌ Test FAILED", "warning")
            
            results.append({
                "name": test["name"],
                "passed": passed,
                "time": elapsed
            })
            
        except Exception as e:
            log("")
            log(f"   ❌ Test ERROR: {e}", "error")
            import traceback
            logger.error(traceback.format_exc())
            results.append({
                "name": test["name"],
                "passed": False,
                "error": str(e)
            })
    
    # Summary
    log_header("Test Summary")
    passed = sum(1 for r in results if r["passed"])
    failed = len(results) - passed
    
    for r in results:
        status = "✅" if r["passed"] else "❌"
        time_str = f"{r.get('time', 0):.2f}s" if "time" in r else "N/A"
        log(f"   {status} {r['name']} ({time_str})")
    
    log("")
    log(f"   Total: {len(results)} | Passed: {passed} | Failed: {failed}")
    
    return results


def test_fast_path_caching():
    """Test that the fast path caching works correctly."""
    log_header("Fast Path Caching Test")
    
    from services.voicebot.voicebot_manager import VoiceBotManager
    from services.vector_db.vector_store import get_vector_store
    
    manager = VoiceBotManager(llm=None)
    vector_store = get_vector_store()
    session_id = "test_cache_session"
    
    query = "Tell me about refund policies"
    
    # First query - should use slow path
    log("")
    log("[Query 1] First request (should use SLOW path)")
    log(f"   Query: \"{query}\"")
    
    start1 = time.time()
    result1 = manager.process_input(session_id, query)
    time1 = time.time() - start1
    
    log(f"   Time: {time1:.2f}s")
    log(f"   Source path: {result1.get('metadata', {}).get('source_path', 'unknown')}")
    
    # Check vector store
    stats = vector_store.get_stats()
    log(f"   Vector store after query: {stats}")
    
    # Second query - should use fast path (if data was cached)
    log("")
    log("[Query 2] Second request (should use FAST path if cached)")
    log(f"   Query: \"{query}\"")
    
    start2 = time.time()
    result2 = manager.process_input(session_id, query)
    time2 = time.time() - start2
    
    log(f"   Time: {time2:.2f}s")
    log(f"   Source path: {result2.get('metadata', {}).get('source_path', 'unknown')}")
    
    # Compare times
    if time2 < time1:
        log("")
        log(f"   ✅ Fast path is faster! ({time1:.2f}s → {time2:.2f}s)")
    else:
        log("")
        log(f"   ⚠️ Fast path not faster (may not have been cached)", "warning")
    
    return True


def test_individual_components():
    """Test individual components in isolation."""
    log_header("Component Tests")
    
    # Test 1: Intent Detection
    log("")
    log("[Component] Intent Detection")
    from services.intent_detection.intent_detector import detect_intent
    
    queries = [
        ("Tell me about pizza", "retrieve_information"),
        ("Order a burger", "perform_action"),
        ("Go to cart", "view_webpage"),
    ]
    
    for query, expected in queries:
        result = detect_intent(query)
        category = result.get("category", "unknown")
        confidence = result.get("confidence", 0)
        log(f"   '{query}' → {category} (conf: {confidence:.2f})")
        if category == expected:
            log(f"      ✅ Matched")
        else:
            log(f"      ⚠️ Expected: {expected}", "warning")
    
    # Test 2: Database Agent
    log("")
    log("[Component] Database Agent")
    from services.graphql.database_agent import get_database_router_agent
    from services.graphql.client import MockGraphQLClient
    
    agent = get_database_router_agent()
    client = MockGraphQLClient()
    tables = client.get_available_tables()
    
    query_tests = [
        ("What pizzas do you have?", "menu_items"),
        ("Tell me about your refund policy", "policies"),
        ("Show my recent orders", "orders"),
    ]
    
    for query, expected_table in query_tests:
        table, params, confidence = agent.route(query, tables)
        log(f"   '{query}' → {table} (conf: {confidence:.2f})")
        if table == expected_table:
            log(f"      ✅ Matched")
        else:
            log(f"      ⚠️ Expected: {expected_table}", "warning")
    
    # Test 3: Information Retrieval
    log("")
    log("[Component] Information Retrieval")
    from services.information_retrieval.retriever import get_information_retriever
    
    retriever = get_information_retriever()
    result = retriever.retrieve("Tell me about Caesar Salad")
    log(f"   Status: {result.get('status')}")
    log(f"   Source path: {result.get('source_path', 'N/A')}")
    log(f"   Context length: {len(result.get('context', ''))}")
    
    return True


def run_all_tests():
    """Run all end-to-end tests."""
    log("")
    log("=" * 70)
    log(" WEBVOX RAG SYSTEM - END-TO-END TEST SUITE")
    log("=" * 70)
    
    try:
        # Run component tests
        test_individual_components()
        
        # Run full flow tests
        test_voicebot_manager()
        
        # Run caching tests
        test_fast_path_caching()
        
        log_header("ALL TESTS COMPLETED")
        
    except Exception as e:
        log(f"❌ Test suite error: {e}", "error")
        import traceback
        logger.error(traceback.format_exc())


if __name__ == "__main__":
    run_all_tests()

