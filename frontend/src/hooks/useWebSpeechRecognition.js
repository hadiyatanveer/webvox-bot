// src/hooks/useWebSpeechRecognition.js
import { useState, useRef, useCallback, useEffect } from 'react';

const useWebSpeechRecognition = ({ onTranscriptChange, language = 'en-US', silenceTimeout = 2000 }) => {
  const [isListening, setIsListening] = useState(false);
  const [transcript, setTranscript] = useState('');
  const [error, setError] = useState(null);
  const [isSupported, setIsSupported] = useState(false);
  
  // Refs to hold mutable state without triggering re-renders
  const recognitionRef = useRef(null);
  const silenceTimerRef = useRef(null);
  const isListeningRef = useRef(false); // Track listening state for internal logic

  // Helper to clear timer
  const clearSilenceTimer = () => {
    if (silenceTimerRef.current) {
      clearTimeout(silenceTimerRef.current);
      silenceTimerRef.current = null;
    }
  };

  useEffect(() => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    setIsSupported(!!SpeechRecognition);
    
    if (!SpeechRecognition) return;

    const recognition = new SpeechRecognition();
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = language;
    
    recognition.onstart = () => {
      console.log('🎤 Speech Started');
      setIsListening(true);
      isListeningRef.current = true; // Update ref
      setError(null);
    };
    
    recognition.onresult = (event) => {
      clearSilenceTimer(); // Reset timer because user spoke

      let interimTranscript = '';
      let finalForThisChunk = '';
      
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const transcriptChunk = event.results[i][0].transcript;
        if (event.results[i].isFinal) {
          finalForThisChunk += transcriptChunk + ' ';
        } else {
          interimTranscript += transcriptChunk;
        }
      }
      
      // Update transcript state
      const fullTranscript = finalForThisChunk + interimTranscript; 
      // Note: We are simplifying transcript handling here to avoid accumulation bugs
      setTranscript(prev => prev + finalForThisChunk);
      
      if (onTranscriptChange) {
        onTranscriptChange(finalForThisChunk + interimTranscript, !interimTranscript);
      }

      // Auto-Stop Timer
      // Only set timer if we are actually listening
      if (isListeningRef.current) {
        silenceTimerRef.current = setTimeout(() => {
          console.log("🤫 Silence detected. Auto-stopping...");
          recognition.stop(); 
        }, silenceTimeout);
      }
    };
    
    recognition.onerror = (event) => {
      if (event.error === 'aborted') return; // Ignore harmless aborts

      console.error('Speech error:', event.error);
      clearSilenceTimer();
      
      if (event.error === 'network') {
        setError('Network error: Internet connection required for this language.');
        setIsListening(false);
        isListeningRef.current = false;
        // Don't abort hard here, let the UI reflect the error
      } else if (event.error !== 'no-speech') {
        setError(event.error);
        setIsListening(false);
        isListeningRef.current = false;
      }
    };
    
    recognition.onend = () => {
      console.log('🎤 Speech Ended');
      clearSilenceTimer();
      setIsListening(false);
      isListeningRef.current = false;
    };
    
    recognitionRef.current = recognition;

    // Cleanup function
    return () => {
      clearSilenceTimer();
      // Only abort if the language CHANGED (component unmounting/remounting)
      // We do NOT abort just because state updated.
      if (recognition) recognition.abort();
    };
    
  // CRITICAL FIX: Removed 'isListening' from dependencies to stop the loop
  }, [language, silenceTimeout, onTranscriptChange]); 

  const startListening = useCallback(() => {
    if (!isSupported || !recognitionRef.current) return;
    if (isListeningRef.current) return; // Prevent double start

    setTranscript('');
    setError(null);
    
    try {
      if (recognitionRef.current.lang !== language) {
        recognitionRef.current.lang = language;
      }
      recognitionRef.current.start();
    } catch (err) {
      console.error("Start error:", err);
    }
  }, [isSupported, language]); // Removed isListening dep

  const stopListening = useCallback(() => {
    clearSilenceTimer();
    if (recognitionRef.current) {
      recognitionRef.current.stop();
    }
  }, []);

  return {
    transcript,
    isListening,
    isSupported,
    error,
    startListening,
    stopListening
  };
};

export default useWebSpeechRecognition;