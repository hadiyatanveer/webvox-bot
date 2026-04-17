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
        Persistence is managed via thread_id (session_id).
        """
        # 1. Prepare only the updates for the current turn
        # The checkpointer will load the previous state for this thread_id
        input_data = {
            "user_input": user_input,
            "session_id": session_id,
            "user_context": {"user_id": 1} 
        }

        # 2. Configure the graph execution with the thread_id
        config = {"configurable": {"thread_id": session_id}}

        try:
            print(f"\n🚀 --- STARTING LANGGRAPH EXECUTION [Session: {session_id}] ---")
            
            # 3. Invoke the graph with the thread config
            final_state = self.graph.invoke(input_data, config=config)
            
            print("✅ --- LANGGRAPH EXECUTION COMPLETE ---\n")

            # 3. Extract the response or handle graph-level errors
            if final_state.get("error"):
                response_text = f"I'm sorry, my database agent encountered an error: {final_state['error']}"
            else:
                response_text = final_state.get("final_response", "I'm sorry, I couldn't generate a response.")

            return {
                "response": response_text,
                "status": "success",
                "state": final_state
            }
            
        except Exception as e:
            print(f"❌ Graph execution crashed: {e}")
            return {
                "response": "I encountered a critical error while trying to process your request.",
                "status": "error"
            }