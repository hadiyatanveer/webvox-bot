// src/components/VoiceInput.js - SIMPLE BUTTON WITH MANUAL STOP
import React from 'react';
import useWebSpeechRecognition from '../hooks/useWebSpeechRecognition';
import './VoiceInput.css';

const VoiceInput = ({ onVoiceInput, disabled }) => {
  const {
    transcript,
    isListening,
    isSupported,
    error,
    startListening,
    stopListening,
    resetTranscript
  } = useWebSpeechRecognition({
    onTranscriptChange: (transcript, isFinal) => {
      // Send real-time updates to parent for textbox preview
      onVoiceInput(transcript, isListening);
    }
  });

  const handleVoiceToggle = () => {
    if (isListening) {
      // MANUAL STOP - user pressed button to stop
      stopListening();
      // Send final transcript when manually stopped
      if (transcript.trim()) {
        onVoiceInput(transcript.trim(), false, true); // Send as final
        resetTranscript();
      }
    } else {
      // START listening
      startListening();
    }
  };

  if (!isSupported) {
    return (
      <div className="voice-input">
        <button
          className="voice-button disabled"
          disabled={true}
          title="Speech recognition not supported in this browser"
        >
          🎤❌
        </button>
      </div>
    );
  }

  return (
    <div className="voice-input">
      <button
        className={`voice-button ${isListening ? 'listening' : ''}`}
        onClick={handleVoiceToggle}
        disabled={disabled}
        title={isListening ? 'Click to stop listening' : 'Click to start voice input'}
      >
        {isListening ? '🛑' : '🎤'}
      </button>
      
      {error && (
        <div className="voice-error-small">
          {error}
        </div>
      )}
    </div>
  );
};

export default VoiceInput;