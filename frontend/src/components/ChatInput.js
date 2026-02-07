// src/components/ChatInput.js
import React, { useState, useRef, useEffect, useCallback } from 'react';
import VoiceInput from './VoiceInput';
import './ChatInput.css';

const ChatInput = ({ onSendMessage, isLoading, language, onLanguageChange }) => {
  const [message, setMessage] = useState('');
  const [isListening, setIsListening] = useState(false);
  const textareaRef = useRef(null);

  const handleSubmit = useCallback(async (e) => {
    e.preventDefault();
    if (message.trim() && !isLoading && !isListening) {
      await onSendMessage(message.trim(), 'text');
      setMessage('');
    }
  }, [message, isLoading, isListening, onSendMessage]);

  const handleVoiceInput = useCallback(async (text, listening, isComplete = false) => {
    setIsListening(listening);
    if (isComplete && text.trim()) {
      await onSendMessage(text.trim(), 'voice');
      setMessage('');
    } else if (listening || text) {
      setMessage(text || '');
    }
  }, [onSendMessage]);

  const handleTextChange = (e) => {
     if (!isListening) setMessage(e.target.value);
  };

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = textareaRef.current.scrollHeight + 'px';
    }
  }, [message]);

  return (
    <div className="chat-input-container">
      <form onSubmit={handleSubmit} className="chat-input-form">
        <div className="input-wrapper">
          
          <select 
            className="language-select"
            value={language}
            onChange={(e) => onLanguageChange(e.target.value)}
            disabled={isListening || isLoading}
          >
            <option value="en-US">🇺🇸 EN</option>
            <option value="ur-IN">🇵🇰 UR</option>
            <option value="ar-SA">🇸🇦 AR</option>
          </select>

          <textarea
            ref={textareaRef}
            value={message}
            onChange={handleTextChange}
            placeholder={isListening ? "Listening..." : "Type or speak..."}
            disabled={isLoading}
            className={`message-input ${isListening ? 'listening-mode' : ''}`}
            rows={1}
            dir={language === 'ar-SA' || language === 'ur' ? 'rtl' : 'ltr'}
          />
          
          <div className="input-actions">
            <VoiceInput 
              onVoiceInput={handleVoiceInput}
              disabled={isLoading}
              language={language}
            />
            <button
              type="submit"
              disabled={!message.trim() || isLoading || isListening}
              className="send-button"
            >
              {isLoading ? '⏳' : '📤'}
            </button>
          </div>
        </div>
      </form>
    </div>
  );
};

export default ChatInput;