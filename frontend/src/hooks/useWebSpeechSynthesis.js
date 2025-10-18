// src/hooks/useWebSpeechSynthesis.js - FRONTEND TTS
import { useState, useRef, useCallback, useEffect } from 'react';

const useWebSpeechSynthesis = () => {
  const [isPlaying, setIsPlaying] = useState(false);
  const [error, setError] = useState(null);
  const [isSupported, setIsSupported] = useState(false);
  const [voices, setVoices] = useState([]);
  
  const utteranceRef = useRef(null);

  // Check if Web Speech Synthesis is supported
  useEffect(() => {
    const speechSynthesis = window.speechSynthesis;
    setIsSupported(!!speechSynthesis);
    
    if (speechSynthesis) {
      const loadVoices = () => {
        const availableVoices = speechSynthesis.getVoices();
        setVoices(availableVoices);
      };
      
      // Load voices
      loadVoices();
      
      // Some browsers load voices asynchronously
      if (speechSynthesis.onvoiceschanged !== undefined) {
        speechSynthesis.onvoiceschanged = loadVoices;
      }
    }
  }, []);

  const speak = useCallback(async (text, options = {}) => {
    return new Promise((resolve, reject) => {
      if (!isSupported) {
        const error = 'Speech synthesis is not supported in this browser';
        setError(error);
        reject(new Error(error));
        return;
      }

      if (!text || !text.trim()) {
        const error = 'No text provided';
        setError(error);
        reject(new Error(error));
        return;
      }

      // Stop any current speech
      if (isPlaying) {
        stop();
      }

      try {
        const utterance = new SpeechSynthesisUtterance(text.trim());
        
        // Configure utterance
        utterance.rate = options.speed || 1.0;
        utterance.pitch = options.pitch || 1.0;
        utterance.volume = options.volume || 1.0;
        
        // Set voice if specified
        if (options.voiceName && voices.length > 0) {
          const selectedVoice = voices.find(voice => 
            voice.name.toLowerCase().includes(options.voiceName.toLowerCase())
          );
          if (selectedVoice) {
            utterance.voice = selectedVoice;
          }
        } else if (voices.length > 0) {
          // Use first available English voice or just first voice
          const englishVoice = voices.find(voice => voice.lang.startsWith('en'));
          utterance.voice = englishVoice || voices[0];
        }

        // Set up event handlers
        utterance.onstart = () => {
          console.log('Speech synthesis started');
          setIsPlaying(true);
          setError(null);
        };

        utterance.onend = () => {
          console.log('Speech synthesis ended');
          setIsPlaying(false);
          utteranceRef.current = null;
          resolve();
        };

        utterance.onerror = (event) => {
          console.error('Speech synthesis error:', event);
          setError(`Speech synthesis error: ${event.error}`);
          setIsPlaying(false);
          utteranceRef.current = null;
          reject(new Error(`Speech synthesis error: ${event.error}`));
        };

        utteranceRef.current = utterance;
        window.speechSynthesis.speak(utterance);

      } catch (err) {
        console.error('Error creating speech:', err);
        setError(err.message);
        setIsPlaying(false);
        reject(err);
      }
    });
  }, [isSupported, isPlaying, voices]);

  const stop = useCallback(() => {
    if (window.speechSynthesis) {
      window.speechSynthesis.cancel();
      setIsPlaying(false);
      utteranceRef.current = null;
    }
  }, []);

  const pause = useCallback(() => {
    if (window.speechSynthesis && isPlaying) {
      window.speechSynthesis.pause();
    }
  }, [isPlaying]);

  const resume = useCallback(() => {
    if (window.speechSynthesis && isPlaying) {
      window.speechSynthesis.resume();
    }
  }, [isPlaying]);

  return {
    speak,
    stop,
    pause,
    resume,
    isPlaying,
    isSupported,
    voices,
    error
  };
};

export default useWebSpeechSynthesis;