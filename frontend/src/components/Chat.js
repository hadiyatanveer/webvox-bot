// src/components/Chat.js - WITH FRONTEND TTS
import React, { useState, useRef, useEffect } from 'react';
import './Chat.css';
import ChatMessage from './ChatMessage';
import ChatInput from './ChatInput';
import useWebSpeechSynthesis from '../hooks/useWebSpeechSynthesis';
import { sendMessageToBot } from "../services/BotResponse";

const Chat = () => {
  const [messages, setMessages] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  
  const messagesEndRef = useRef(null);
  
  // Use frontend TTS instead of backend
  const {
    speak,
    stop: stopSpeech,
    isPlaying,
    isSupported: ttsSupported,
    error: ttsError
  } = useWebSpeechSynthesis();

  // Auto-scroll to bottom when new messages are added
  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const handleSendMessage = async (input, inputType = 'text') => {
    if (isLoading) return;

    setIsLoading(true);
    setError(null);

    try {
      // Add user message to chat
      setMessages(prev => [...prev, {
        id: Date.now(),
        text: input,
        isUser: true,
        timestamp: new Date(),
        inputType: inputType
      }]);

      const response = await sendMessageToBot(input);

      setTimeout(() => {
        setMessages(prev => [...prev, {
          id: Date.now() + 1,
          text: response, 
          isUser: false,
          timestamp: new Date(),
          originalInputType: inputType
        }]);
        setIsLoading(false);
      }, 500); // Small delay to simulate processing

    } catch (err) {
      console.error('Error processing message:', err);
      setError(err.message || 'Failed to process message');
      setIsLoading(false);
    }
  };

  const handlePlayAudio = async (text) => {
    if (isPlaying) {
      // Stop current audio
      stopSpeech();
      return;
    }

    try {
      setError(null);
      
      // Use frontend TTS
      await speak(text, {
        speed: 1.0,
        pitch: 1.0,
        volume: 1.0
      });
      
    } catch (err) {
      console.error('Error playing audio:', err);
      setError(err.message || 'Failed to play audio');
    }
  };

  const clearChat = () => {
    setMessages([]);
    setError(null);
    if (isPlaying) {
      stopSpeech();
    }
  };

  return (
    <div className="chat-container">
      {/* Header */}
      <div className="chat-header">
        <div className="chat-title">
          <h1>WebVox Bot</h1>
          <div className="status-indicator connected">
            <span className="status-dot"></span>
            <span className="status-text">
              Ready (All Frontend Processing!)
            </span>
          </div>
        </div>
        
        <div className="header-actions">
          <button 
            className="clear-button"
            onClick={clearChat}
            disabled={messages.length === 0}
            title="Clear chat"
          >
            🗑️
          </button>
        </div>
      </div>

      {/* Messages */}
      <div className="messages-container">
        {messages.length === 0 ? (
          <div className="welcome-message">
            <div className="welcome-content">
              <h2>Welcome to WebVox Bot! 🎙️</h2>
              <p><strong>Now with 100% Frontend Processing!</strong></p>
              <ul>
                <li>Type a message in the input below</li>
                <li>Click 🎤 to start voice input, 🛑 to stop</li>
                <li>Voice preview shows in the textbox as you speak</li>
                <li>Click 🔊 next to responses to hear them</li>
                <li>Both STT and TTS work entirely in your browser</li>
              </ul>
              <p className="subtitle">No backend issues, everything works offline!</p>
            </div>
          </div>
        ) : (
          messages.map((message) => (
            <ChatMessage
              key={message.id}
              message={message.text}
              isUser={message.isUser}
              onPlayAudio={handlePlayAudio}
              isPlaying={isPlaying}
              inputType={message.inputType || message.originalInputType}
            />
          ))
        )}
        
        {isLoading && (
          <div className="typing-indicator">
            <div className="typing-dots">
              <span></span>
              <span></span>
              <span></span>
            </div>
            <p>Processing...</p>
          </div>
        )}
        
        <div ref={messagesEndRef} />
      </div>

      {/* Error Display */}
      {(error || ttsError) && (
        <div className="error-message">
          <span className="error-icon">⚠️</span>
          <span className="error-text">{error || ttsError}</span>
          <button 
            className="error-close"
            onClick={() => setError(null)}
          >
            ✕
          </button>
        </div>
      )}

      {/* Input */}
      <ChatInput 
        onSendMessage={handleSendMessage}
        isLoading={isLoading}
      />
    </div>
  );
};

export default Chat;