// src/components/ChatMessage.js
import React from 'react';
import './ChatMessage.css';

const ChatMessage = ({ message, isUser, onPlayAudio, isPlaying }) => {
  return (
    <div className={`message ${isUser ? 'user-message' : 'bot-message'}`}>
      <div className="message-content">
        <div className="message-avatar">
          {isUser ? '👤' : '🤖'}
        </div>
        <div className="message-text">
          <p>{message}</p>
          {!isUser && (
            <button 
              className={`play-button ${isPlaying ? 'playing' : ''}`}
              onClick={() => onPlayAudio(message)}
              disabled={isPlaying}
              title="Read aloud"
            >
              {isPlaying ? '🔊' : '🔈'}
            </button>
          )}
        </div>
      </div>
    </div>
  );
};

export default ChatMessage;