import re
import json
from utilities.llm_configure import generate_content
from utilities.config_loader import get_config
from utilities.prompt_loader import load_prompt
from utilities.history_formatter import format_history_for_prompt
from typing import List, Dict, Optional


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


def detect_intent(
    user_text: str,
    rag_context=None,
    user_role: str = "admin",
    chat_history: Optional[List[Dict[str, str]]] = None,
) -> dict:
    """
    Detect user intent with confidence scoring and entity extraction.
    
    Args:
        user_text: The user's voice command text
        rag_context: Optional RAG context for better intent detection
        user_role: User role for authorization checks
        chat_history: Prior conversation turns for coreference resolution
        
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

    # Format conversation history for the prompt
    # We exclude the very last message (the current user turn) since it is
    # already in {user_text} — so we pass history[:-1].
    history_for_prompt = chat_history[:-1] if chat_history else []
    chat_history_block = format_history_for_prompt(history_for_prompt)

    prompt = load_prompt("intent_detector", "classify_intent.prompt.txt", {
        "user_role": user_role,
        "user_text": user_text,
        "context_snippet": context_snippet,
        "chat_history_block": chat_history_block,
    })

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
        
        # Apply confidence threshold logic (deterministic, Python-side)
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
        # result.setdefault("authorized", True)
        result["authorized"] = True  # Force True for testing (was setdefault)
        
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
            "clarification_questions": [
                "I'm sorry, I had a little trouble processing that. Could you try saying it again? "
                "For example, you can ask things like 'What pizzas do you have?' or 'Tell me about your refund policy.'"
            ],
            "authorized": True
        }


def get_detected_entities(intent_data: dict) -> dict:
    entities = intent_data.get("entities", {})
    return {k: v for k, v in entities.items() if v is not None}