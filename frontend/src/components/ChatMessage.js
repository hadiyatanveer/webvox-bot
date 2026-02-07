// src/components/ChatMessage.js
import React from 'react';
import './ChatMessage.css';

const ChatMessage = ({ message, isUser }) => {
  
  // Helper function to parse **bold** text
  const formatMessage = (text) => {
    if (!text) return null;

    // 1. Split the text by the ** pattern
    // The regex captures the delimiters so we can process them
    const parts = text.split(/(\*\*.*?\*\*)/g);

    return parts.map((part, index) => {
      // 2. Check if this part is bold (starts and ends with **)
      if (part.startsWith('**') && part.endsWith('**')) {
        // Remove the asterisks and wrap in <strong>
        const content = part.slice(2, -2);
        return <strong key={index}>{content}</strong>;
      }
      // 3. Return normal text otherwise
      return <span key={index}>{part}</span>;
    });
  };

  return (
    <div className={`message ${isUser ? 'user-message' : 'bot-message'}`}>
      <div className="message-content">
        <div className="message-avatar">
          {isUser ? '👤' : '🤖'}
        </div>
        <div className="message-text">
          {/* Call the formatter here instead of displaying raw message */}
          <p>{formatMessage(message)}</p>
        </div>
      </div>
    </div>
  );
};

export default ChatMessage;