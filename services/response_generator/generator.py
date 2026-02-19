"""
Response Generator for WebVox.
Synthesizes LLM responses using assembled RAG context.
"""

from typing import Dict, Any, Optional, List

from utilities.config_loader import get_config
from utilities.llm_configure import generate_content
from utilities.prompt_loader import load_prompt


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
        retrieval_result: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Generate a response based on intent and retrieved context.
        
        Args:
            user_query: Original user query
            intent_data: Detected intent information
            retrieval_result: Results from information retrieval (if applicable)
            
        Returns:
            Generated response with metadata
        """
        category = intent_data.get("category", "unknown")
        
        # Route to appropriate generator based on intent category
        if category == "information":
            return self._generate_information_response(user_query, intent_data, retrieval_result)
        
        elif category == "action":
            return self._generate_action_not_supported_response()
        
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
    
    def _generate_information_response(
        self,
        user_query: str,
        intent_data: Dict[str, Any],
        retrieval_result: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Generate response for information retrieval intent."""
        
        # Check if retrieval was successful
        if not retrieval_result or retrieval_result.get("status") != "success":
            # Use fallback or clarification
            if retrieval_result and retrieval_result.get("message"):
                return {
                    "response": retrieval_result["message"],
                    "status": "no_results",
                    "needs_clarification": True
                }
            return self._generate_clarification_response(user_query, intent_data)
        
        # Build prompt with context
        context = retrieval_result.get("context", "")
        print("context given to user:", context)
        
        prompt = load_prompt("response_generator", "generate_response.prompt.txt", {
            "context": context,
            "user_query": user_query,
        })

        try:
            response = generate_content(prompt)
            
            # Extract response text
            if hasattr(response, "candidates"):
                response_text = response.candidates[0].content.parts[0].text
            elif hasattr(response, "content"):
                response_text = response.content
            else:
                response_text = str(response)
            
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
    
    def _generate_action_not_supported_response(self) -> Dict[str, Any]:
        """Generate response when action execution is not supported."""
        message = self.config.get(
            'response.fallback.action_not_supported',
            "I can currently only help with information retrieval. Actions like ordering or booking are not yet available."
        )
        
        return {
            "response": message,
            "status": "not_supported",
            "intent_category": "perform_action"
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
        
        # Check if intent detector already provided clarification questions
        clarification_questions = intent_data.get("clarification_questions", [])
        
        if clarification_questions:
            questions_text = "\n".join(f"• {q}" for q in clarification_questions)
            response = f"I'd like to help you, but I need a bit more information:\n{questions_text}"
        else:
            # Use default clarification
            response = self.config.get(
                'clarification.templates.general',
                "Could you clarify what you want to access? For example: menu items, your orders, or something else?"
            )
        
        return {
            "response": response,
            "status": "needs_clarification",
            "needs_clarification": True,
            "original_query": user_query
        }


# Global instance
_response_generator = None


def get_response_generator() -> ResponseGenerator:
    """Get the global response generator instance."""
    global _response_generator
    if _response_generator is None:
        _response_generator = ResponseGenerator()
    return _response_generator
