// src/hooks/useWebSpeechSynthesis.js
import { useState, useRef, useCallback, useEffect } from 'react';

const useWebSpeechSynthesis = () => {
  const [isPlaying, setIsPlaying] = useState(false);
  const [error, setError] = useState(null);
  const [isSupported, setIsSupported] = useState(false);
  const [voices, setVoices] = useState([]);
  
  const utteranceRef = useRef(null);

  useEffect(() => {
    const synth = window.speechSynthesis;
    setIsSupported(!!synth);
    
    if (synth) {
      const loadVoices = () => {
        const availableVoices = synth.getVoices();
        setVoices(availableVoices);
      };
      
      loadVoices();
      if (synth.onvoiceschanged !== undefined) {
        synth.onvoiceschanged = loadVoices;
      }
    }
  }, []);

  const speak = useCallback(async (text, options = {}) => {
    return new Promise((resolve, reject) => {
      if (!isSupported) return reject(new Error('TTS not supported'));
      if (!text || !text.trim()) return reject(new Error('No text provided'));

      if (window.speechSynthesis.speaking) {
        window.speechSynthesis.cancel();
      }

      try {
        const utterance = new SpeechSynthesisUtterance(text.trim());
        const targetLang = options.lang || 'en-US';
        
        // --- SMART VOICE MATCHING LOGIC ---

        // 1. Exact Match (e.g., 'ur-PK')
        let selectedVoice = voices.find(v => v.lang === targetLang);
        
        // 2. Loose Match (e.g., 'ur')
        if (!selectedVoice) {
           const baseLang = targetLang.split('-')[0].toLowerCase();
           selectedVoice = voices.find(v => v.lang.toLowerCase().startsWith(baseLang));
        }

        // 3. SPECIAL FALLBACK: If Urdu is missing, use Hindi (hi-IN)
        // (Spoken Urdu and Hindi are mutually intelligible)
        if (!selectedVoice && targetLang.includes('ur')) {
           console.log("⚠️ Urdu voice missing. Falling back to Hindi (hi-IN).");
           selectedVoice = voices.find(v => v.lang === 'hi-IN' || v.lang.includes('hi'));
        }

        // 4. Ultimate Fallback: English
        if (!selectedVoice) {
          console.warn(`⚠️ No voice found for ${targetLang}. Using Default/English.`);
          selectedVoice = voices.find(v => v.lang.startsWith('en')) || voices[0];
        } else {
          console.log(`✅ Using Voice: ${selectedVoice.name} (${selectedVoice.lang})`);
        }
        
        if (selectedVoice) {
          utterance.voice = selectedVoice;
          utterance.lang = selectedVoice.lang;
        }

        utterance.rate = options.speed || 1.0;
        utterance.pitch = options.pitch || 1.0;

        utterance.onstart = () => setIsPlaying(true);
        utterance.onend = () => {
          setIsPlaying(false);
          utteranceRef.current = null;
          resolve();
        };
        utterance.onerror = (e) => {
          console.error("TTS Error:", e);
          setIsPlaying(false);
          if (e.error !== 'interrupted' && e.error !== 'canceled') {
            reject(e);
          }
        };

        utteranceRef.current = utterance;
        window.speechSynthesis.speak(utterance);

      } catch (err) {
        console.error("TTS Exception:", err);
        setIsPlaying(false);
        reject(err);
      }
    });
  }, [isSupported, voices]);

  const stop = useCallback(() => {
    if (window.speechSynthesis) {
      window.speechSynthesis.cancel();
      setIsPlaying(false);
    }
  }, []);

  return { speak, stop, isPlaying, isSupported, error };
};

export default useWebSpeechSynthesis;