// src/components/VoiceInput.js
import React, { useState } from 'react';
import useVoiceRecorder from '../hooks/useVoiceRecorder';
import VoiceService from '../services/VoiceService';
import './VoiceInput.css';

// --- Inline SVG Icons ---
const MicIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24"
    fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M12 1a3 3 0 00-3 3v8a3 3 0 006 0V4a3 3 0 00-3-3z" />
    <path d="M19 10v2a7 7 0 01-14 0v-2" />
    <line x1="12" y1="19" x2="12" y2="23" />
    <line x1="8" y1="23" x2="16" y2="23" />
  </svg>
);

const StopIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24"
    fill="currentColor" stroke="none">
    <rect x="4" y="4" width="16" height="16" rx="2" />
  </svg>
);

const SpinnerIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24"
    fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
    className="icon-spin">
    <path d="M21 12a9 9 0 1 1-6.219-8.56" />
  </svg>
);

const VoiceInput = ({ onVoiceInput, disabled, language = 'en-US' }) => {
  const { isRecording, error, startRecording, stopRecording } = useVoiceRecorder();
  const [isProcessing, setIsProcessing] = useState(false);

  const handleVoiceToggle = async () => {
    if (isRecording) {
      const audioBlob = await stopRecording();
      setIsProcessing(true);

      try {
        const result = await VoiceService.transcribeAudio(audioBlob, language);
        if (result.success && result.text) {
          onVoiceInput(result.text, false, true);
        } else {
          console.error('STT Error:', result.error);
        }
      } catch (err) {
        console.error('Transcription failed:', err);
      } finally {
        setIsProcessing(false);
      }
    } else {
      await startRecording();
    }
  };

  const getTitle = () => {
    if (isProcessing) return 'Processing audio…';
    if (isRecording) return 'Click to stop and send';
    return `Speak (${language})`;
  };

  return (
    <div className="voice-input">
      <button
        className={`voice-button ${isRecording ? 'listening' : ''} ${isProcessing ? 'processing' : ''}`}
        onClick={handleVoiceToggle}
        disabled={disabled || isProcessing}
        title={getTitle()}
        aria-label={getTitle()}
        type="button"
      >
        {isProcessing ? <SpinnerIcon /> : isRecording ? <StopIcon /> : <MicIcon />}
      </button>



      {error && <div className="voice-error">{error}</div>}
    </div>
  );
};

export default VoiceInput;