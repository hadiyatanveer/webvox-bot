// src/components/ChatInput.js
import React, { useState, useRef, useEffect, useCallback } from 'react';
import VoiceInput from './VoiceInput';
import './ChatInput.css';

// --- Inline SVG Icons ---
const SendIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24"
    fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <line x1="22" y1="2" x2="11" y2="13" />
    <polygon points="22 2 15 22 11 13 2 9 22 2" />
  </svg>
);

const SpinnerIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24"
    fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
    className="icon-spin">
    <path d="M21 12a9 9 0 1 1-6.219-8.56" />
  </svg>
);

const ChatInput = ({ onSendMessage, isLoading, language, onLanguageChange, onInputActivity }) => {
  const [message, setMessage] = useState('');
  const [isListening, setIsListening] = useState(false);
  const textareaRef = useRef(null);

  const handleSubmit = useCallback(async (e) => {
    e?.preventDefault();
    const trimmedMessage = message.trim();
    if (trimmedMessage && !isLoading && !isListening) {
      setMessage(''); // Clear immediately
      await onSendMessage(trimmedMessage, 'text');
    }
  }, [message, isLoading, isListening, onSendMessage]);

  const handleKeyDown = useCallback((e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  }, [handleSubmit]);

  const handleVoiceInput = useCallback(async (text, listening, isComplete = false) => {
    setIsListening(listening);
    if (isComplete && text.trim()) {
      await onSendMessage(text.trim(), 'voice');
      setMessage('');
    } else if (listening || text) {
      onInputActivity?.();
      setMessage(text || '');
    }
  }, [onSendMessage, onInputActivity]);

  const handleTextChange = (e) => {
    if (!isListening) {
      setMessage(e.target.value);
      if (e.target.value.trim().length > 0) {
        onInputActivity?.();
      }
    }
  };

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      const scrollHeight = textareaRef.current.scrollHeight;
      textareaRef.current.style.height = scrollHeight + 'px';

      // Toggle scrollbar if it hits max-height
      if (scrollHeight > 100) {
        textareaRef.current.style.overflowY = 'auto';
        textareaRef.current.style.scrollbarWidth = 'thin';
      } else {
        textareaRef.current.style.overflowY = 'hidden';
      }
    }
  }, [message]);



  const placeholders = {
    'en-US': 'Type a message…',
    'ur-IN': 'اپنا پیغام یہاں ٹائپ کریں',
    'ar-SA': 'اكتب رسالتك هنا...'
  };

  return (
    <div className="chat-input-toolbar">
      <div className="input-row-primary">
        <div className={`input-pill ${isListening ? 'listening' : ''}`}>
          <textarea
            ref={textareaRef}
            value={message}
            onChange={handleTextChange}
            onKeyDown={handleKeyDown}
            placeholder={isListening ? 'Listening…' : (placeholders[language] || placeholders['en-US'])}
            disabled={isLoading}
            rows={1}
            dir={language === 'ar-SA' || language === 'ur-IN' ? 'rtl' : 'ltr'}
          />
          <div className="pill-actions">
            <VoiceInput
              onVoiceInput={handleVoiceInput}
              disabled={isLoading}
              language={language}
            />
            <button
              onClick={handleSubmit}
              disabled={!message.trim() || isLoading || isListening}
              className="send-arrow-btn"
              title="Send"
            >
              {isLoading ? <SpinnerIcon /> : <SendIcon />}
            </button>
          </div>
        </div>
      </div>

      {!isListening && (
        <div className="input-row-utility">
          <select
            className="lang-minimal-select"
            value={language}
            onChange={(e) => onLanguageChange(e.target.value)}
            disabled={isLoading}
          >
            <option value="en-US">🇺🇸 EN</option>
            <option value="ur-IN">🇵🇰 UR</option>
            <option value="ar-SA">🇸🇦 AR</option>
          </select>
        </div>
      )}
    </div>
  );
};

export default ChatInput;