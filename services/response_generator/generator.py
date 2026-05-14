"""
Response Generator for WebVox.
Synthesizes LLM responses using assembled RAG context.
"""

from typing import Dict, Any, Optional, List

from utilities.config_loader import get_config
from utilities.llm_configure import generate_content
from utilities.prompt_loader import load_prompt
from utilities.history_formatter import format_history_for_prompt


class ResponseGenerator:
    """
    Generates natural language responses using LLM and RAG context.
    Handles different intent types and includes clarification logic.
    """
    
    def __init__(self):
        self.config = get_config()
    
    def generate(
        self,
        user_query: str,
        intent_data: Dict[str, Any],
        retrieval_result: Optional[Dict[str, Any]] = None,
        action_data: Optional[Dict[str, Any]] = None,
        mutation_result: Optional[Dict[str, Any]] = None,
        chat_history: Optional[List[Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        """
        Generate a response based on intent and retrieved context.
        
        Args:
            user_query: Original user query
            intent_data: Detected intent information
            retrieval_result: Results from information retrieval (if applicable)
            action_data: Data from action intent classification (if applicable)
            mutation_result: Results from database mutation (if applicable)
            chat_history: Prior conversation turns for contextual responses
            
        Returns:
            Generated response with metadata
        """
        category = intent_data.get("category", "unknown")
        
        # Route to appropriate generator based on intent category
        if category == "information":
            return self._generate_information_response(
                user_query, intent_data, retrieval_result, chat_history
            )
        
        elif category == "action":
            return self._generate_action_response(
                user_query, action_data, mutation_result, chat_history
            )
        
        elif category == "webpage":
            return self._generate_webpage_not_supported_response()
        
        elif category == "greeting":
            # Greetings are fully handled by voicebot_manager; this is a safety fallback
            return {
                "response": "Hey there! I'm WebVox, your voice assistant. Ask me anything about our menu, prices, or policies!",
                "status": "greeting"
            }
        
        else:
            return self._generate_clarification_response(user_query, intent_data)

    # ── Private helpers ───────────────────────────────────────────────────────

    def _build_history_block(
        self, chat_history: Optional[List[Dict[str, str]]]
    ) -> str:
        """
        Format history for prompt injection, excluding the current user turn
        (which is already present in {user_query}).
        """
        # The current user message is the last entry; exclude it so it isn't
        # duplicated in the prompt.
        prior = chat_history[:-1] if chat_history else []
        return format_history_for_prompt(prior)

    def _load_response_prompt(
        self,
        context: str,
        user_query: str,
        chat_history: Optional[List[Dict[str, str]]],
    ) -> str:
        """Load the response generator prompt with history injected."""
        return load_prompt("response_generator", "generate_response.prompt.txt", {
            "context": context,
            "user_query": user_query,
            "chat_history_block": self._build_history_block(chat_history),
        })

    def _generate_information_response(
        self,
        user_query: str,
        intent_data: Dict[str, Any],
        retrieval_result: Optional[Dict[str, Any]],
        chat_history: Optional[List[Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        """Generate response for information retrieval intent."""
        
        # Check if retrieval was successful
        if not retrieval_result or retrieval_result.get("status") != "success":
            if retrieval_result and retrieval_result.get("message"):
                return {
                    "response": retrieval_result["message"],
                    "status": "no_results",
                    "needs_clarification": True
                }
            return self._generate_clarification_response(user_query, intent_data)
        
        # Build prompt with context
        context = retrieval_result.get("context", "")
        query_desc = retrieval_result.get("query_description", "")
        if query_desc:
            context = f"[Database filter applied: {query_desc}]\n\n{context}"
        print("context given to user:", context)
        
        prompt = self._load_response_prompt(context, user_query, chat_history)

        try:
            response_text = self._call_llm(prompt)
            
            return {
                "response": response_text,
                "status": "success",
                "source_path": retrieval_result.get("source_path", "unknown"),
                "metadata": retrieval_result.get("metadata", {})
            }
            
        except Exception as e:
            print(f"⚠️ LLM generation error: {e}")
            return {
                "response": "I found some information but had trouble formulating a response. Let me try again.",
                "status": "error",
                "error": str(e)
            }
    
    def _generate_action_response(
        self,
        user_query: str,
        action_data: Optional[Dict[str, Any]],
        mutation_result: Optional[Dict[str, Any]] = None,
        chat_history: Optional[List[Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        """Generate response for action intent, handling errors, missing info, and execution results."""
        if not action_data:
            return {
                "response": "I understand you want to perform an action, but I'm having trouble understanding exactly what. Could you be more specific?",
                "status": "error"
            }
        
        if action_data.get("error"):
            return {
                "response": action_data["error"],  # Already a user-facing message
                "status": "disallowed"
            }
        
        # 1. Handle Execution Result
        if mutation_result:
            prompt = self._load_response_prompt(
                f"MUTATION_RESULT: {mutation_result}", user_query, chat_history
            )
            try:
                response_text = self._call_llm(prompt)
                return {
                    "response": response_text,
                    "status": "success" if mutation_result.get("success") else "error"
                }
            except Exception:
                return {
                    "response": "Your request has been processed.",
                    "status": "success"
                }

        # 2. Handle Missing Information
        missing_info = action_data.get("missing_info", {})
        if not missing_info.get("is_complete", True):
            questions = missing_info.get("clarification_questions", [])
            response_text = " ".join(questions) if questions else "I need a bit more info to help with that."
            return {
                "response": response_text,
                "status": "needs_info",
                "needs_clarification": True
            }
        
        # 3. Handle Successful Data Collection (Ready to Execute)
        prompt = self._load_response_prompt(
            f"ACTION_DATA: {action_data}\n\nSTATUS: ACTION_READY (Awaiting confirmation)",
            user_query,
            chat_history,
        )
        try:
            response_text = self._call_llm(prompt)
            return {
                "response": response_text,
                "status": "action_ready",
                "action_data": action_data
            }
        except Exception:
            op = action_data.get("operation", "action")
            return {
                "response": f"I've noted your request. Would you like me to proceed with the {op}?",
                "status": "action_ready",
                "action_data": action_data
            }
    
    def _generate_webpage_not_supported_response(self) -> Dict[str, Any]:
        """Generate response when webpage navigation is not supported."""
        message = self.config.get(
            'response.fallback.webpage_not_supported',
            "Webpage navigation is not yet available. Please ask me about specific information instead."
        )
        return {
            "response": message,
            "status": "not_supported",
            "intent_category": "view_webpage"
        }
    
    def _generate_clarification_response(
        self,
        user_query: str,
        intent_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate a clarification request when intent is unclear."""
        clarification_questions = intent_data.get("clarification_questions", [])
        
        if clarification_questions:
            questions_text = "\n".join(f"• {q}" for q in clarification_questions)
            response = f"I'd like to help you, but I need a bit more information:\n{questions_text}"
        else:
            response = self.config.get(
                'clarification.templates.general',
                "Could you clarify what you want to access? For example: menu items, your orders, or something else?"
            )

        return {
            "response": response,
            "status": "clarification",
            "needs_clarification": True
        }
        
    def _call_llm(self, prompt: str) -> str:
        """Helper to call LLM and extract text."""
        response = generate_content(prompt)
        
        if hasattr(response, "candidates"):
            return response.candidates[0].content.parts[0].text
        elif hasattr(response, "content"):
            return response.content
        return str(response)


# Global instance
_response_generator = None


def get_response_generator() -> ResponseGenerator:
    """Get the global response generator instance."""
    global _response_generator
    if _response_generator is None:
        _response_generator = ResponseGenerator()
    return _response_generator
