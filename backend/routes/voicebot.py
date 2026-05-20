# backend/routes/voicebot.py
from fastapi import APIRouter, HTTPException
from backend.schemas.voicebot import ChatRequest
from utilities.globalvariables import LLM
from services.voicebot.voicebot_manager import VoiceBotManager

# Initialize the router
router_voicebot = APIRouter()

# Initialize the VoiceBotManager (which now boots up LangGraph)
voice_bot = VoiceBotManager(llm=LLM)

@router_voicebot.post("/api/v1/chat")
async def chat_endpoint(request: ChatRequest):
    try:
        # Process the input using the LangGraph-powered VoiceBotManager
        result = voice_bot.process_input(
            session_id=request.session_id, 
            user_input=request.message
        )

        return {
            "success": True,
            "response": result.get('response', ''),
            "session_id": request.session_id,
            "processing_time": 0.1 # You can add actual timing logic later if needed
        }
    
    except Exception as e:
        print(f"API Route Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))