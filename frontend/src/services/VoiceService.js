// src/services/VoiceService.js
class VoiceService {
  constructor() {
    this.chatApiUrl = 'http://localhost:8001'; 
    this.utilityApiUrl = 'http://localhost:8000'; 
    this.sessionId = this.generateSessionId();
  }

  generateSessionId() {
    return `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }

  // --- 1. TRANSLATION (New) ---
  async translateText(text, targetLang) {
    try {
      const response = await fetch(`${this.utilityApiUrl}/api/translate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text, target_lang: targetLang })
      });

      if (!response.ok) throw new Error('Translation failed');
      const data = await response.json();
      return { success: true, text: data.translated_text };
    } catch (error) {
      console.error('Translation Error:', error);
      return { success: false, error: error.message };
    }
  }

  // --- 2. SEND CHAT (Existing) ---
  async sendChatMessage(text) {
    try {
      const response = await fetch(`${this.chatApiUrl}/api/v1/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: text,
          session_id: this.sessionId,
          input_type: 'text' 
        })
      });

      if (!response.ok) {
        console.error('Backend returned status:', response.status); // <--- ADD THIS
        // Try to read the body for more info (if the server sends JSON errors)
        const errorText = await response.text(); 
        console.error('Backend error details:', errorText); // <--- AND THIS
        throw new Error('Backend connection failed');
      }
      const data = await response.json();
      return { success: true, response: data.response };
    } catch (error) {
      return { success: false, error: error.message };
    }
  }

  // --- 3. HYBRID TTS (Urdu & Arabic) ---
  async getBackendAudio(text, lang) {
    try {
      // Map full codes to 2-letter codes for gTTS (e.g., 'ar-SA' -> 'ar')
      const shortLang = lang.split('-')[0]; 
      
      const response = await fetch(`${this.utilityApiUrl}/api/tts`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text, lang: shortLang })
      });

      if (!response.ok) throw new Error('Backend TTS failed');
      const audioBlob = await response.blob();
      return { success: true, audioUrl: URL.createObjectURL(audioBlob) };
    } catch (error) {
      return { success: false, error: error.message };
    }
  }
}

export default new VoiceService();