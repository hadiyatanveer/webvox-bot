from fastapi import APIRouter, HTTPException

from backend.schemas.voicebot import ChatRequest

from utilities.globalvariables import LLM
from services.voicebot.voicebot_manager import VoiceBotManager

# Initialize the router
router_voicebot = APIRouter()

# Initialize the VoiceBotManager with a default LLM.
voice_bot = VoiceBotManager(llm=LLM)

@router_voicebot.post("/webvox/chat")
async def chat_endpoint(request: ChatRequest):
    try:
        # Process the input using VoiceBotManager
        result = voice_bot.process_input(session_id=request.session_id, user_input=request.message)

        return {
            "success": True,
            "response": f"{result.get('response', '')}",
            "session_id": request.session_id,
            "processing_time": 0.1
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))