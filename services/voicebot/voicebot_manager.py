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

        History strategy:
          - We inject the current user turn into chat_history at the START of
            the invocation so every node in this turn can read it.
          - After the graph finishes, we append the bot's response to
            chat_history via a second graph update so it is persisted for the
            NEXT turn.
        """
        config = {"configurable": {"thread_id": session_id}}

        # ── Turn input: seed the user message into history ────────────────────
        input_data = {
            "user_input": user_input,
            "session_id": session_id,
            "user_context": {"user_id": 1},
            # The _append_messages reducer will merge this with the existing
            # history stored by the checkpointer for this session.
            "chat_history": [{"role": "user", "content": user_input}],
        }

        try:
            print(f"\n🚀 --- STARTING LANGGRAPH EXECUTION [Session: {session_id}] ---")

            # ── Run the full agentic pipeline ─────────────────────────────────
            final_state = self.graph.invoke(input_data, config=config)

            print("✅ --- LANGGRAPH EXECUTION COMPLETE ---\n")

            # ── Extract the bot response ──────────────────────────────────────
            if final_state.get("error"):
                response_text = (
                    f"I'm sorry, my database agent encountered an error: {final_state['error']}"
                )
            else:
                response_text = final_state.get(
                    "final_response", "I'm sorry, I couldn't generate a response."
                )

            # ── Persist the assistant turn into history ───────────────────────
            # We do a lightweight graph update (no node execution) by passing
            # only the new history entry.  The reducer appends it to the list
            # that was already saved after the main invoke above.
            self.graph.update_state(
                config,
                {"chat_history": [{"role": "assistant", "content": response_text}]},
            )

            return {
                "response": response_text,
                "status": "success",
                "state": final_state,
            }

        except Exception as e:
            print(f"❌ Graph execution crashed: {e}")
            return {
                "response": "I encountered a critical error while trying to process your request.",
                "status": "error",
            }