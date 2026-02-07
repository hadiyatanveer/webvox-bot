import re
import json
from utilities.llm_configure import generate_content
from utilities.config_loader import get_config


def clean_json_output(raw_text: str) -> str:
    """Extract JSON from LLM response, handling markdown code blocks."""
    match = re.search(r'```json\s*(\{[\s\S]*?\})\s*```', raw_text)
    
    if match:
        json_block = match.group(1)
        json_block = re.sub(r'//.*', '', json_block)
        return json_block.strip()
    
    match = re.search(r'(\{[\s\S]*\})', raw_text)
    if match:
        json_block = match.group(1)
        json_block = re.sub(r'//.*', '', json_block)
        return json_block.strip()
    
    return ""


def detect_intent(user_text: str, rag_context=None, user_role: str = "basic") -> dict:
    """
    Detect user intent with confidence scoring and entity extraction.
    
    Args:
        user_text: The user's voice command text
        rag_context: Optional RAG context for better intent detection
        user_role: User role for authorization checks
        
    Returns:
        Dictionary containing intent classification, confidence, entities, and clarification info
    """
    config = get_config()
    confidence_threshold = config.get('intent_detection.confidence_threshold', 0.7)
    
    context_snippet = ""
    if rag_context:
        context_snippet = "Relevant product/service info:\n" + "\n".join(
            [f"- {r.get('text', str(r))}" for r in rag_context]
        )

    prompt = f"""You are an advanced NLU module for a **voice-based web accessibility assistant**.

You will receive a user's voice command, and you must:

1. Classify it into **one of four high-level intent categories**:
   - "retrieve_information": user wants to get details about a product/service (e.g., "Tell me about Margherita pizza", "What's in the Caesar salad?")
   - "perform_action": user wants to take an action (e.g., "Order two pizzas", "Cancel my order")
   - "view_webpage": user wants to navigate to a page (e.g., "Show me my orders", "Go to desserts")
   - "unknown": intent is unclear or doesn't fit other categories

2. Assign a **confidence score** (0.0 to 1.0):
   - 0.9-1.0: Very clear intent with all needed information
   - 0.7-0.9: Clear intent but may need minor clarification
   - 0.5-0.7: Ambiguous intent, likely needs clarification
   - Below 0.5: Very unclear, definitely needs clarification

3. Extract **entities** from the query:
   - product_name: specific product mentioned
   - category: product category (pizza, burger, etc.)
   - quantity: number of items
   - order_id: order number if mentioned
   - Any other relevant entities

4. Identify **clarification needs**:
   - Set needs_clarification = true if confidence < {confidence_threshold} OR required entities are missing
   - Provide specific clarification_questions

5. Apply authorization check for user role "{user_role}".

Respond in this exact JSON format:

{{
    "category": "retrieve_information" | "perform_action" | "view_webpage" | "unknown",
    "intent": "specific intent name (e.g., get_menu_item, get_policies, get_order_status)",
    "confidence": 0.0 to 1.0,
    "entities": {{
        "product_name": "string or null",
        "category": "string or null",
        "quantity": "number or null",
        "order_id": "string or null"
    }},
    "needs_clarification": boolean,
    "clarification_questions": ["question1", "question2"],
    "authorized": boolean
}}

User input:
"{user_text}"

{context_snippet}
"""

    response = generate_content(prompt)

    # Extract response text from different LLM formats
    if hasattr(response, "candidates"):
        raw_text = response.candidates[0].content.parts[0].text
    elif hasattr(response, "content"):
        raw_text = response.content
    else:
        raw_text = str(response)

    cleaned = clean_json_output(raw_text)

    try:
        result = json.loads(cleaned)
        
        # Apply confidence threshold logic
        confidence = result.get("confidence", 0.5)
        if confidence < confidence_threshold and not result.get("needs_clarification"):
            result["needs_clarification"] = True
            if not result.get("clarification_questions"):
                result["clarification_questions"] = [
                    "Could you please be more specific about what you're looking for?"
                ]
        
        # Ensure all required fields exist
        result.setdefault("category", "unknown")
        result.setdefault("intent", "unknown")
        result.setdefault("confidence", 0.5)
        result.setdefault("entities", {})
        result.setdefault("needs_clarification", False)
        result.setdefault("clarification_questions", [])
        result.setdefault("authorized", True)
        
        return result
        
    except Exception as e:
        print("⚠️ JSON parse error, fallback:", e)
        print("Raw LLM output:", raw_text)
        return {
            "category": "unknown",
            "intent": "unknown",
            "confidence": 0.0,
            "entities": {},
            "needs_clarification": True,
            "clarification_questions": ["I didn't quite understand that. Could you please rephrase?"],
            "authorized": True
        }


def get_detected_entities(intent_data: dict) -> dict:
    entities = intent_data.get("entities", {})
    return {k: v for k, v in entities.items() if v is not None}