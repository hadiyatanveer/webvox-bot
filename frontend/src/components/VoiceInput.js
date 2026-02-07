// src/components/VoiceInput.js
import React, { useCallback, useEffect, useRef } from 'react';
import useWebSpeechRecognition from '../hooks/useWebSpeechRecognition';
import './VoiceInput.css';

const VoiceInput = ({ onVoiceInput, disabled, language = 'en-US' }) => {
  // We use a ref to track if we were just listening, 
  // so we can detect the specific moment it stops.
  const wasListeningRef = useRef(false);

  const handleTranscriptChange = useCallback((text, isFinal) => {
    onVoiceInput(text, false);
  }, [onVoiceInput]);

  const {
    transcript,
    isListening,
    isSupported,
    error,
    startListening,
    stopListening
  } = useWebSpeechRecognition({
    onTranscriptChange: handleTranscriptChange,
    language: language,
    silenceTimeout: 2000 // Stop after 2 seconds of silence
  });

  // AUTO-SEND LOGIC:
  // Detect when isListening switches from TRUE -> FALSE
  useEffect(() => {
    if (wasListeningRef.current && !isListening) {
      // Logic: We were listening, now we stopped (due to silence or click)
      // If we have text, send it!
      if (transcript.trim()) {
        console.log("📦 Auto-sending message:", transcript);
        onVoiceInput(transcript.trim(), false, true); // isComplete = true
      }
    }
    // Update ref for next render
    wasListeningRef.current = isListening;
  }, [isListening, transcript, onVoiceInput]);

  const handleVoiceToggle = () => {
    if (isListening) {
      // Manual stop (user clicked button)
      stopListening();
      // The useEffect above will handle the sending when isListening becomes false
    } else {
      startListening();
    }
  };

  if (!isSupported) return null;

  return (
    <div className="voice-input">
      <button
        className={`voice-button ${isListening ? 'listening' : ''}`}
        onClick={handleVoiceToggle}
        disabled={disabled}
        title={isListening ? 'Listening... (Stop speaking to send)' : `Speak (${language})`} 
        type="button"
      >
        {isListening ? '🛑' : '🎤'}
      </button>

      {/* Visual Feedback for Auto-Stop */}
      {isListening && (
        <div className="transcript-preview">
           Listening... (Auto-send in 2s)
        </div>
      )}

      {error && <div className="voice-error-small">{error}</div>}
    </div>
  );
};

export default VoiceInput;