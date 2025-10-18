import re
import json
from utilities.llm_configure import generate_content


def clean_json_output(raw_text: str) -> str:
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

def detect_intent(user_text, rag_context=None, user_role="basic"):
    context_snippet = ""
    if rag_context:
        context_snippet = "Relevant product/service info:\n" + "\n".join(
            [f"- {r['text']}" for r in rag_context]
        )

    prompt = f"""
        You are an advanced NLU module for a **voice-based web accessibility assistant**.

        You will receive a user's voice command, and you must:
        1. Classify it into **one of three high-level intent categories**:
        - "retrieve_information": user wants to get details about a product/service. (e.g., "Tell me about Margherita pizza")
        - "perform_action": user wants to take an action on the website. (e.g., "Order two Pepperoni pizzas", "Cancel my order", "Open my cart")
        - "view_webpage": user wants to open or view a section/page of the site. (e.g., "Show me my orders", "View cart", "Go to the desserts page")

        2. Identify the **specific intent** under that category (like order_product, cancel_order, view_cart, get_product_info, etc.)

        3. If any required information is missing or unclear, set:
        - needs_clarification = true
        - and provide clarification_questions[].

        5. Apply a security check: given user role "{user_role}", decide if the action is authorized.

        Use this format:

        {{
        "category": "retrieve_information" | "perform_action" | "view_webpage" | "unknown",
        "intent": "string",
        "needs_clarification": boolean,
        "clarification_questions": ["question1", "question2"],
        "authorized": boolean,
        }}

        User input:
        "{user_text}"

        {context_snippet}
        """

    response = generate_content(prompt)

    # Gemini / Groq / fallback handling
    if hasattr(response, "candidates"):
        raw_text = response.candidates[0].content.parts[0].text
    elif hasattr(response, "content"):
        raw_text = response.content
    else:
        raw_text = str(response)

    cleaned = clean_json_output(raw_text)

    try:
        return json.loads(cleaned)
    except Exception as e:
        print("⚠️ JSON parse error, fallback:", e)
        print("Raw LLM output:", raw_text)
        return {
            "category": "unknown",
            "intent": "unknown",
            "needs_clarification": False,
            "clarification_questions": [],
            "authorized": True
        }