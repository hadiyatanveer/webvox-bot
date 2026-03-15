// src/services/VoiceService.js
class VoiceService {
  constructor() {
    this.chatApiUrl = 'http://localhost:8001'; // Sahrish's Logic
    this.utilityApiUrl = 'http://localhost:8000'; // TTS & Translation
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

      if (!response.ok) throw new Error('Backend connection failed');
      const data = await response.json();
      return { success: true, response: data.response };
    } catch (error) {
      return { success: false, error: error.message };
    }
  }

  // --- 3. AZURE NEURAL TTS ---
  async getBackendAudio(text, lang) {
    try {
      // Send the full locale (e.g., 'en-US', 'ur-IN') to map to specific Azure voices
      const response = await fetch(`${this.utilityApiUrl}/api/tts`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text, lang: lang })
      });

      if (!response.ok) throw new Error('Backend Azure TTS failed');
      const audioBlob = await response.blob();
      return { success: true, audioUrl: URL.createObjectURL(audioBlob) };
    } catch (error) {
      return { success: false, error: error.message };
    }
  }
  // --- 4. AZURE STT (New) ---
  async transcribeAudio(audioBlob, lang) {
    try {
      const formData = new FormData();
      // Append the blob. The backend will convert it regardless of the browser's native mimeType
      formData.append('audio', audioBlob, 'recording.webm');
      formData.append('lang', lang);

      const response = await fetch(`${this.utilityApiUrl}/api/stt`, {
        method: 'POST',
        // Note: Do NOT set 'Content-Type' when sending FormData in React; the browser sets the boundary automatically.
        body: formData 
      });

      if (!response.ok) throw new Error('Backend Azure STT failed');
      return await response.json();
    } catch (error) {
      console.error('STT Service Error:', error);
      return { success: false, error: error.message };
    }
  }
}
const voiceServiceInstance = new VoiceService();
export default voiceServiceInstance;