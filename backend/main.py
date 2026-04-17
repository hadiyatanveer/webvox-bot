import os
import io
import tempfile
from dotenv import load_dotenv

load_dotenv()  # Load environment variables from .env file

# Silences the oneDNN info message
os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'
# Silences the TensorFlow deprecation warnings (0 = all logs, 1 = filter INFO, 2 = filter WARNINGS, 3 = filter ERRORS)
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'

from fastapi import FastAPI, Response, HTTPException, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from deep_translator import GoogleTranslator
import azure.cognitiveservices.speech as speechsdk
from pydub import AudioSegment
import uvicorn

# Include the router added in the langgraph branch
from backend.routes.voicebot import router_voicebot

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_methods=["*"],
    allow_headers=["*"],
)

# 🔐 Set these in your environment variables or a .env file
AZURE_SPEECH_KEY = os.getenv("AZURE_SPEECH_KEY")
AZURE_SPEECH_REGION = os.getenv("AZURE_SPEECH_REGION")

if not AZURE_SPEECH_KEY or not AZURE_SPEECH_REGION:
    # Changed from raise ValueError to a print so the app doesn't crash if you are just testing the router
    print("⚠️ Azure Speech credentials not found. Please check your .env file.")

class TTSRequest(BaseModel):
    text: str
    lang: str = "en-US"

class TranslateRequest(BaseModel):
    text: str
    target_lang: str

# Map the frontend locales to high-quality Azure Neural Voices
VOICE_MAP = {
    "en-US": "en-US-AriaNeural",      # Standard American Female
    "ur-IN": "ur-PK-UzmaNeural",      # Route to Pakistani Urdu Female
    "ur-PK": "ur-PK-UzmaNeural",      # Pakistani Urdu Female
    "ur": "ur-PK-UzmaNeural",         # Fallback for Urdu
    "ar-SA": "ar-SA-HamedNeural",     # Arabic (Saudi) Male
    "ar": "ar-SA-HamedNeural"         # Fallback for Arabic
}

# --- 1. AZURE NEURAL TTS ENDPOINT ---
@app.post("/api/tts")
async def text_to_speech(request: TTSRequest):
    try:
        # Initialize Azure Speech Config
        speech_config = speechsdk.SpeechConfig(subscription=AZURE_SPEECH_KEY, region=AZURE_SPEECH_REGION)
        
        # Output as MP3 for easy web playback
        speech_config.set_speech_synthesis_output_format(speechsdk.SpeechSynthesisOutputFormat.Audio16Khz32KBitRateMonoMp3)
        
        # Select Neural Voice based on language
        voice_name = VOICE_MAP.get(request.lang) or VOICE_MAP.get(request.lang.split('-')[0]) or "en-US-AriaNeural"
        speech_config.speech_synthesis_voice_name = voice_name
        
        # Create Synthesizer with no audio output (we want the memory stream to send to frontend)
        synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=None)
        
        # Synthesize
        result = synthesizer.speak_text_async(request.text).get()
        
        if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
            audio_data = result.audio_data
            return Response(content=audio_data, media_type="audio/mp3")
        elif result.reason == speechsdk.ResultReason.Canceled:
            cancellation_details = result.cancellation_details
            error_msg = f"Speech synthesis canceled: {cancellation_details.reason}. {cancellation_details.error_details}"
            print(error_msg)
            raise HTTPException(status_code=500, detail=error_msg)
            
    except Exception as e:
        print(f"Azure TTS Error: {e}")
        return Response(content=str(e), status_code=500)

# --- 2. TRANSLATION ENDPOINT ---
@app.post("/api/translate")
async def translate_text(request: TranslateRequest):
    try:
        translator = GoogleTranslator(source='auto', target=request.target_lang)
        translated_text = translator.translate(request.text)
        return {"translated_text": translated_text}
    except Exception as e:
        print(f"Translation Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# --- 3. AZURE STT ENDPOINT ---
@app.post("/api/stt")
async def speech_to_text(
    audio: UploadFile = File(...),
    lang: str = Form("en-US")
):
    temp_input = None
    temp_wav = None
    try:
        # 1. Save uploaded webm/mp4 file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as f:
            f.write(await audio.read())
            temp_input = f.name
        
        # 2. Convert to PCM WAV (16kHz, mono) for Azure using pydub
        temp_wav = temp_input + ".wav"
        audio_segment = AudioSegment.from_file(temp_input)
        audio_segment = audio_segment.set_frame_rate(16000).set_channels(1)
        audio_segment.export(temp_wav, format="wav")

        # 3. Configure Azure Speech STT
        speech_config = speechsdk.SpeechConfig(subscription=AZURE_SPEECH_KEY, region=AZURE_SPEECH_REGION)
        speech_config.speech_recognition_language = lang
        
        audio_config = speechsdk.AudioConfig(filename=temp_wav)
        speech_recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config, audio_config=audio_config)
        
        # 4. Perform recognition (single utterance)
        result = speech_recognizer.recognize_once_async().get()
        
        if result.reason == speechsdk.ResultReason.RecognizedSpeech:
            return {"success": True, "text": result.text}
        elif result.reason == speechsdk.ResultReason.NoMatch:
            return {"success": False, "error": "No speech could be recognized."}
        elif result.reason == speechsdk.ResultReason.Canceled:
            return {"success": False, "error": f"STT Canceled: {result.cancellation_details.reason}"}
            
    except Exception as e:
        print(f"STT Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # 1. Force Azure to release the Windows file lock
        if 'speech_recognizer' in locals():
            del speech_recognizer
        if 'audio_config' in locals():
            del audio_config
            
        # 2. Cleanup temp files safely
        if temp_input and os.path.exists(temp_input):
            try:
                os.remove(temp_input)
            except Exception as e:
                print(f"Warning: Could not remove {temp_input}: {e}")
                
        if temp_wav and os.path.exists(temp_wav):
            try:
                os.remove(temp_wav)
            except Exception as e:
                print(f"Warning: Could not remove {temp_wav}: {e}")

# --- 4. DEBUG ENDPOINTS ---
@app.post("/api/debug/clear-cache")
async def handle_clear_cache():
    from utilities.prompt_loader import clear_prompt_cache
    clear_prompt_cache()
    return {"status": "success", "message": "Prompt cache cleared"}

# Include the langgraph router
app.include_router(router_voicebot)

if __name__ == "__main__":
    # Uses the langgraph approach to run via module string (allows for hot-reloading)
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)