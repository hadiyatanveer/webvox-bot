from langchain.prompts import PromptTemplate
from langchain.memory import ConversationBufferMemory
from langchain.schema.runnable import RunnablePassthrough
from langchain.schema.output_parser import StrOutputParser

from services.intent_detection.intent_detector import detect_intent


class VoiceBotManager:
    def __init__(self, llm=None):
        # Initialize LLM
        self.llm = llm
        self.memory = ConversationBufferMemory(return_messages=True, memory_key="chat_history")

        # Prompt template
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

        # Build the Runnable sequence
        self.chain = (
            {
                "chat_history": RunnablePassthrough() | (lambda _: self.get_history()),
                "user_input": RunnablePassthrough(),
            }
            | self.prompt
            | self.llm
            | StrOutputParser()
        )

    # Process user input and return structured response with detected intent.
    def process_input(self, session_id: str, user_input: str):
        # Step 1: Detect the user intent (returns structured dict)
        intent_data = detect_intent(user_input)

        # Extract key fields for readability
        intent = intent_data.get("intent", "")
        authorized = intent_data.get("authorized", True)
        category = intent_data.get("category", "unknown")
        needs_clarification = intent_data.get("needs_clarification", False)
        clarification_questions = intent_data.get("clarification_questions", [])
        user_prompt_response = intent_data.get("response_to_user", "")


        # Step 2: Handle clarification if information is missing
        if needs_clarification:
            # Combine clarification questions into a coherent message
            questions = "\n".join(clarification_questions)
            response_text = (
                user_prompt_response or 
                f"I need a bit more information to continue:\n{questions}"
            )
            status = "need_clarification"
            metadata = {"clarification_questions": clarification_questions}

        # Step 3: Handle unauthorized or restricted actions
        elif not authorized:
            response_text = (
                user_prompt_response or
                "Sorry, you’re not authorized to perform this action."
            )
            status = "unauthorized"
            metadata = {"intent": intent, "category": category}

        # Step 4: Route to corresponding module based on intent category
        else:
            module_response = self._invoke_module(category, user_input)

            # Extract info from module
            status = module_response.get("status", "success")
            message = module_response.get("message", "")
            metadata = module_response.get("metadata", {})

            # TODO: The modules will return the relevant response directly.
            dynamic_prompt = (
                f"Context metadata:\n{metadata}\n\n"
                f"Intent category: {category}\nIntent: {intent}"
                f"User input:\n{user_input}\n\n"
                "Generate a helpful, context-aware response."
            )
            response_text = self.chain.invoke({
                "user_input": dynamic_prompt,
                "chat_history": self.get_history(),
            })

        # Step 5: Save conversation for memory continuity
        self.memory.save_context({"input": user_input}, {"output": response_text})

        # Step 6: Return a fully structured API response
        return {
            "session_id": session_id,
            "category": category,
            "response": response_text,
        }

    # Return the current conversation history.
    def get_history(self):
        return self.memory.load_memory_variables({}).get("chat_history", [])
    
    # TODO: Will be removed when actual modules are integrated.
    def _invoke_module(self, intent, user_input):
        if intent == "retrieve_information":
            return {
                "status": "success",
                "message": "Here’s the price and availability you asked for.",
                "metadata": {
                    "item_name": "iPhone 15",
                    "price": "$999",
                    "availability": "In stock"
                }
            }

        elif intent == "action_execution":
            return {
                "status": "need_clarification",
                "message": "Would you like to confirm placing this order?",
                "metadata": {"pending_action": "order_confirmation"}
            }

        elif intent == "check_status":
            return {
                "status": "success",
                "message": "Your last order is being prepared for delivery.",
                "metadata": {"order_id": "1234", "expected_time": "30 minutes"}
            }

        else:
            return {
                "status": "unknown",
                "message": "I’m not sure what you mean. Could you rephrase?",
                "metadata": {}
            }