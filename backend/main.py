import io
import uvicorn

from gtts import gTTS
from deep_translator import GoogleTranslator

from pydantic import BaseModel
from fastapi import FastAPI, Response, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from backend.routes.voicebot import router_voicebot

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_methods=["*"],
    allow_headers=["*"],
)

class TTSRequest(BaseModel):
    text: str
    lang: str = "ur"

class TranslateRequest(BaseModel):
    text: str
    target_lang: str  # 'en', 'ur', 'ar'

# --- 1. TTS ENDPOINT (Urdu & Arabic support) ---
@app.post("/api/tts")
async def text_to_speech(request: TTSRequest):
    try:
        # gTTS supports both 'ur' and 'ar'
        tts = gTTS(text=request.text, lang=request.lang, slow=False)
        buffer = io.BytesIO()
        tts.write_to_fp(buffer)
        buffer.seek(0)
        return Response(content=buffer.read(), media_type="audio/mp3")
    except Exception as e:
        print(f"TTS Error: {e}")
        return Response(content=str(e), status_code=500)

# --- 2. TRANSLATION ENDPOINT (New) ---
@app.post("/api/translate")
async def translate_text(request: TranslateRequest):
    try:
        translator = GoogleTranslator(source='auto', target=request.target_lang)
        translated_text = translator.translate(request.text)
        return {"translated_text": translated_text}
    except Exception as e:
        print(f"Translation Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

app.include_router(router_voicebot)

if __name__ == "__main__":
    uvicorn.run("backend.main:app", host="localhost", port=8001, reload=True)