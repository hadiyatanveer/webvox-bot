// src/hooks/useWebSpeechRecognition.js - PROPER VERSION WITH MANUAL STOP
import { useState, useRef, useCallback, useEffect } from 'react';

const useWebSpeechRecognition = ({ onTranscriptChange }) => {
  const [isListening, setIsListening] = useState(false);
  const [transcript, setTranscript] = useState('');
  const [error, setError] = useState(null);
  const [isSupported, setIsSupported] = useState(false);
  
  const recognitionRef = useRef(null);
  const finalTranscriptRef = useRef('');

  // Check if Web Speech API is supported
  useEffect(() => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    setIsSupported(!!SpeechRecognition);
    
    if (SpeechRecognition) {
      const recognition = new SpeechRecognition();
      
      // Configure recognition settings
      recognition.continuous = true;
      recognition.interimResults = true;
      recognition.lang = 'en-US';
      recognition.maxAlternatives = 1;
      
      // Event handlers
      recognition.onstart = () => {
        console.log('Speech recognition started');
        setIsListening(true);
        setError(null);
      };
      
      recognition.onresult = (event) => {
        let interimTranscript = '';
        let finalTranscript = finalTranscriptRef.current;
        
        for (let i = event.resultIndex; i < event.results.length; i++) {
          const transcript = event.results[i][0].transcript;
          
          if (event.results[i].isFinal) {
            finalTranscript += transcript + ' ';
          } else {
            interimTranscript += transcript;
          }
        }
        
        finalTranscriptRef.current = finalTranscript;
        const fullTranscript = finalTranscript + interimTranscript;
        setTranscript(fullTranscript);
        
        // Send real-time transcript to parent for textbox preview
        if (onTranscriptChange) {
          onTranscriptChange(fullTranscript, !interimTranscript); // isFinal flag
        }
      };
      
      recognition.onerror = (event) => {
        console.error('Speech recognition error:', event.error);
        setError(`Speech recognition error: ${event.error}`);
        setIsListening(false);
      };
      
      recognition.onend = () => {
        console.log('Speech recognition ended');
        setIsListening(false);
      };
      
      recognitionRef.current = recognition;
    }
  }, [onTranscriptChange]);

  const startListening = useCallback(() => {
    if (!isSupported) {
      setError('Speech recognition is not supported in this browser');
      return;
    }
    
    if (recognitionRef.current && !isListening) {
      finalTranscriptRef.current = '';
      setTranscript('');
      setError(null);
      
      // Clear textbox when starting
      if (onTranscriptChange) {
        onTranscriptChange('', false);
      }
      
      try {
        recognitionRef.current.start();
      } catch (err) {
        console.error('Error starting recognition:', err);
        setError('Could not start speech recognition');
      }
    }
  }, [isListening, isSupported, onTranscriptChange]);

  const stopListening = useCallback(() => {
    if (recognitionRef.current && isListening) {
      recognitionRef.current.stop();
    }
  }, [isListening]);

  const resetTranscript = useCallback(() => {
    setTranscript('');
    finalTranscriptRef.current = '';
    if (onTranscriptChange) {
      onTranscriptChange('', false);
    }
  }, [onTranscriptChange]);

  return {
    transcript,
    isListening,
    isSupported,
    error,
    startListening,
    stopListening,
    resetTranscript
  };
};

export default useWebSpeechRecognition;