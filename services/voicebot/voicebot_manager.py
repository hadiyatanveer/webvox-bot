"""
VoiceBotManager - LangGraph Orchestrator for the WebVox voice assistant.
"""
from services.voicebot.graph import build_voicebot_graph

class VoiceBotManager:
    """
    Main orchestrator that wraps the compiled LangGraph architecture.
    """
    
    def __init__(self, llm=None):
        self.llm = llm
        # Compile the graph once when the server starts
        self.graph = build_voicebot_graph()

    def process_input(self, session_id: str, user_input: str) -> dict:
        """
        Feeds the user input into the LangGraph and extracts the final response.
        """
        # 1. Define the initial state exactly as required by GraphState
        initial_state = {
            "user_input": user_input,
            "session_id": session_id,
            "intent_data": {},
            "needs_clarification": False,
            "vector_results": None,
            "requires_graphql": False,
            "rag_context": None,
            "final_response": "",
            "error": None
        }

        try:
            print(f"\n🚀 --- STARTING LANGGRAPH EXECUTION [Session: {session_id}] ---")
            
            # 2. Invoke the graph (this runs the nodes and conditional edges)
            final_state = self.graph.invoke(initial_state)
            
            print("✅ --- LANGGRAPH EXECUTION COMPLETE ---\n")

            # 3. Extract the response or handle graph-level errors
            if final_state.get("error"):
                response_text = f"I'm sorry, my database agent encountered an error: {final_state['error']}"
            else:
                response_text = final_state.get("final_response", "I'm sorry, I couldn't generate a response.")

            return {
                "response": response_text,
                "status": "success"
            }
            
        except Exception as e:
            print(f"❌ Graph execution crashed: {e}")
            return {
                "response": "I encountered a critical error while trying to process your request.",
                "status": "error"
            }