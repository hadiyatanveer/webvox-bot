"""
VoiceBotManager - Main orchestrator for the WebVox voice assistant.
Coordinates intent detection, RAG pipeline, and response generation.
"""

from langchain.prompts import PromptTemplate
from langchain.memory import ConversationBufferMemory
from langchain.schema.runnable import RunnablePassthrough
from langchain.schema.output_parser import StrOutputParser

from services.intent_detection.intent_detector import detect_intent, get_detected_entities
from services.information_retrieval.retriever import get_information_retriever
from services.response_generator.generator import get_response_generator


class VoiceBotManager:
    """
    Main orchestrator for the WebVox voice assistant.
    Integrates intent detection, RAG pipeline, and response generation.
    """
    
    def __init__(self, llm=None):
        # Initialize LLM for general conversation
        self.llm = llm
        self.memory = ConversationBufferMemory(return_messages=True, input_key="input", output_key="output")

        # Initialize service modules
        self.information_retriever = get_information_retriever()
        self.response_generator = get_response_generator()

        # Prompt template for general conversation fallback
        self.prompt = PromptTemplate(
            input_variables=["chat_history", "user_input"],
            template=(
                "You are WebVox, a helpful voice assistant integrated into e-commerce and food delivery websites.\n"
                "You can answer user questions, guide them to perform actions, and confirm requests.\n\n"
                "Conversation so far:\n{chat_history}\n\n"
                "User: {user_input}\n"
                "Assistant:"
            ),
        )

        # Build the Runnable sequence for fallback responses
        if self.llm:
            self.chain = (
                {
                    "chat_history": RunnablePassthrough() | (lambda _: self.get_history()),
                    "user_input": RunnablePassthrough(),
                }
                | self.prompt
                | self.llm
                | StrOutputParser()
            )
        else:
            self.chain = None

    def process_input(self, session_id: str, user_input: str) -> dict:
        # Step 1: Detect user intent with confidence scoring
        print(f"\n🎤 Processing: '{user_input}'")
        intent_data = detect_intent(user_input)
        
        # Extract key fields
        category = intent_data.get("category", "unknown")
        intent = intent_data.get("intent", "")
        confidence = intent_data.get("confidence", 0.5)
        authorized = intent_data.get("authorized", True)
        needs_clarification = intent_data.get("needs_clarification", False)
        clarification_questions = intent_data.get("clarification_questions", [])
        entities = get_detected_entities(intent_data)
        
        print(f"   → Category: {category}, Intent: {intent}, Confidence: {confidence:.2f}")

        # Step 2: Handle unauthorized actions
        if not authorized:
            response_text = "Sorry, you're not authorized to perform this action."
            status = "unauthorized"
            metadata = {"intent": intent, "category": category}
        
        # Step 3: Handle clarification if needed
        elif needs_clarification:
            questions = "\n".join(f"• {q}" for q in clarification_questions)
            response_text = f"I need a bit more information to help you:\n{questions}"
            status = "needs_clarification"
            metadata = {"clarification_questions": clarification_questions, "confidence": confidence}
        
        # Step 4: Route to appropriate handler based on intent category
        else:
            result = self._route_intent(category, user_input, intent_data, entities)
            response_text = result.get("response", "")
            status = result.get("status", "success")
            metadata = result.get("metadata", {})

        # Step 5: Save conversation for memory continuity
        self.memory.save_context({"input": user_input}, {"output": response_text})

        # Step 6: Return structured API response
        return {
            "session_id": session_id,
            "category": category,
            "intent": intent,
            "confidence": confidence,
            "response": response_text,
            "status": status,
            "metadata": metadata
        }

    def _route_intent(self, category: str, user_input: str, intent_data: dict, entities: dict) -> dict:
        if category == "information":
            return self._handle_retrieve_information(user_input, intent_data, entities)
        
        elif category == "action":
            return self._handle_action_not_supported()
        
        elif category == "webpage":
            return self._handle_webpage_not_supported()
        
        elif category == "greeting":
            return self._handle_greeting()
        
        else:
            return self._handle_unknown(user_input, intent_data)

    def _handle_retrieve_information(self, user_input: str, intent_data: dict, entities: dict) -> dict:
        print("Retrieving information via RAG pipeline...")
        
        # Use information retriever to get context
        retrieval_result = self.information_retriever.retrieve(
            user_query=user_input,
            detected_entities=entities
        )
        
        # Generate response using retrieved context
        response = self.response_generator.generate(
            user_query=user_input,
            intent_data=intent_data,
            retrieval_result=retrieval_result
        )
        
        return {
            "response": response.get("response", ""),
            "status": response.get("status", "success"),
            "metadata": {
                "source_path": retrieval_result.get("source_path", "unknown"),
                "retrieval_metadata": retrieval_result.get("metadata", {}),
                **response.get("metadata", {})
            }
        }

    def _handle_action_not_supported(self) -> dict:
        """Handle action requests (currently not supported)."""
        print("   ⚠️ Action execution not yet implemented")
        return {
            "response": "I can currently only help with information retrieval. Actions like ordering, cancelling, or booking are not yet available. Please ask me about our menu, policies, or other information instead.",
            "status": "not_supported",
            "metadata": {"reason": "action_execution_not_implemented"}
        }

    def _handle_webpage_not_supported(self) -> dict:
        """Handle webpage navigation requests (currently not supported)."""
        print("   ⚠️ Webpage navigation not yet implemented")
        return {
            "response": "Webpage navigation is not yet available. Please ask me about specific information you're looking for, and I'll help you find it.",
            "status": "not_supported",
            "metadata": {"reason": "webpage_navigation_not_implemented"}
        }

    def _handle_greeting(self) -> dict:
        """Handle greetings and conversational openers with a warm introduction."""
        print("   👋 Greeting detected, sending introduction")
        response = (
            "Hey there! 👋 I'm WebVox, your voice assistant for this restaurant. "
            "I'm here to make your experience easier and hands-free!\n\n"
            "Here's what I can help you with:\n"
            "• **Explore the menu** — e.g., 'What pizzas do you have?' or 'Tell me about the Seafood Platter'\n"
            "• **Check prices** — e.g., 'How much is the Chicken Alfredo Pasta?'\n"
            "• **Dietary info** — e.g., 'Do you have vegetarian options?'\n"
            "• **Restaurant policies** — e.g., 'What is your refund policy?' or 'What are your delivery hours?'\n\n"
            "Just ask me anything and I'll do my best to help! 😊"
        )
        return {
            "response": response,
            "status": "greeting",
            "metadata": {}
        }

    def _handle_unknown(self, user_input: str, intent_data: dict) -> dict:
        """Handle unknown intents with clarification."""
        print("   ❓ Unknown intent, requesting clarification")
        
        clarification_questions = intent_data.get("clarification_questions", [])
        if clarification_questions:
            questions = "\n".join(f"• {q}" for q in clarification_questions)
            response = f"I'd like to help you, but I'm not sure what you're looking for. Could you clarify?\n{questions}"
        else:
            response = (
                "I'm here to help you with anything related to our restaurant! 😊 "
                "Here are some things you can try:\n"
                "• Ask about our menu — e.g., 'What pizzas do you have?' or 'Tell me about the Seafood Platter'\n"
                "• Check prices — e.g., 'How much is the Chicken Alfredo Pasta?'\n"
                "• Learn about our policies — e.g., 'What is your refund policy?' or 'What are your delivery hours?'\n"
                "• Browse categories — e.g., 'Show me all desserts' or 'Do you have vegetarian options?'\n\n"
                "Just ask away and I'll do my best to help!"
            )
        
        return {
            "response": response,
            "status": "needs_clarification",
            "metadata": {"original_query": user_input}
        }

    def get_history(self) -> list:
        """Return the current conversation history."""
        return self.memory.load_memory_variables({}).get("chat_history", [])
    
    def clear_history(self) -> None:
        """Clear the conversation history."""
        self.memory.clear()