// src/components/ChatInput.js - TEXTBOX PREVIEW ONLY, MANUAL STOP
import React, { useState, useRef, useEffect } from 'react';
import VoiceInput from './VoiceInput';
import './ChatInput.css';

const ChatInput = ({ onSendMessage, isLoading }) => {
  const [message, setMessage] = useState('');
  const [isListening, setIsListening] = useState(false);
  const textareaRef = useRef(null);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (message.trim() && !isLoading && !isListening) {
      onSendMessage(message.trim(), 'text');
      setMessage('');
    }
  };

  const handleVoiceInput = (transcribedText, listening, isComplete = false) => {
    setIsListening(listening);
    
    if (isComplete && transcribedText.trim()) {
      // Voice input completed - send message
      onSendMessage(transcribedText.trim(), 'voice');
      setMessage('');
    } else if (listening || transcribedText) {
      // Show live preview in textbox
      setMessage(transcribedText || '');
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  const handleTextChange = (e) => {
    // Only allow manual text editing when not listening
    if (!isListening) {
      setMessage(e.target.value);
    }
  };

  // Auto-resize textarea
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
          <textarea
            ref={textareaRef}
            value={message}
            onChange={handleTextChange}
            onKeyPress={handleKeyPress}
            placeholder={isListening ? "Listening... (click 🛑 to stop)" : "Type a message or use voice input..."}
            disabled={isLoading}
            className={`message-input ${isListening ? 'listening-mode' : ''}`}
            rows={1}
            style={{
              color: isListening ? '#059669' : 'inherit',
              fontStyle: isListening ? 'italic' : 'normal',
              backgroundColor: isListening ? '#ecfdf5' : 'inherit'
            }}
          />
          
          <div className="input-actions">
            <VoiceInput 
              onVoiceInput={handleVoiceInput}
              disabled={isLoading}
            />
            
            <button
              type="submit"
              disabled={!message.trim() || isLoading || isListening}
              className="send-button"
              title="Send message"
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