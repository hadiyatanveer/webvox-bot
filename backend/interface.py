"""
WebVox Bot - MINIMAL BACKEND (No Voice Processing)
=================================================

Since both STT and TTS are now handled in the frontend,
this backend is now minimal and just serves as a placeholder
for future AI/chat functionality.

Author: WebVox Bot Team
Date: October 2025
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

# Minimal FastAPI app
app = FastAPI(
    title="WebVox Bot - Minimal Backend",
    description="Minimal backend since all voice processing is now frontend",
    version="1.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    message: str
    session_id: str
    input_type: Optional[str] = "text"

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy", 
        "module": "minimal_backend", 
        "version": "1.0.0",
        "message": "Backend ready! All voice processing is done in frontend.",
        "features": {
            "text_to_speech": "frontend",
            "speech_to_text": "frontend", 
            "chat_processing": "placeholder"
        }
    }

@app.post("/api/v1/chat")
async def chat_endpoint(request: ChatRequest):
    """Simple chat endpoint - replace with your AI logic"""
    return {
        "success": True,
        "response": f"Echo: {request.message}",
        "session_id": request.session_id,
        "processing_time": 0.1
    }

if __name__ == "__main__":
    import uvicorn
    print("=" * 60)
    print("🤖 WebVox Bot - MINIMAL BACKEND")
    print("=" * 60)
    print("✅ No voice processing - all done in frontend!")
    print("✅ Ready for AI/chat integration")
    print("🌐 Server running on http://localhost:8001")
    print("=" * 60)
    uvicorn.run(app, host="0.0.0.0", port=8001)