// src/services/VoiceService.js - SIMPLIFIED FOR TTS ONLY
class VoiceService {
  constructor(apiUrl = 'http://localhost:8001') {
    this.apiUrl = apiUrl;
    this.sessionId = this.generateSessionId();
  }

  generateSessionId() {
    return `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }

  // Text-to-Speech - Still uses backend
  async textToSpeech(text) {
    try {
      const response = await fetch(`${this.apiUrl}/api/v1/text-to-speech`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          text: text,
          session_id: this.sessionId,
          voice: 'default',
          speed: 1.0
        })
      });

      if (response.ok) {
        const audioBlob = await response.blob();
        return {
          success: true,
          audioBlob: audioBlob
        };
      } else {
        const errorData = await response.json();
        return {
          success: false,
          error_message: errorData.error_message || 'TTS failed'
        };
      }
    } catch (error) {
      console.error('Text to speech error:', error);
      return {
        success: false,
        error_message: `Text to speech failed: ${error.message}`
      };
    }
  }

  // Check if backend is available
  async healthCheck() {
    try {
      const response = await fetch(`${this.apiUrl}/health`);
      return response.ok;
    } catch (error) {
      return false;
    }
  }
}

export default VoiceService;