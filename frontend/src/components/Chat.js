// src/components/Chat.js
import React, { useState, useRef, useEffect, useCallback } from 'react';
import ChatMessage from './ChatMessage';
import ChatInput from './ChatInput';
import useWebSpeechSynthesis from '../hooks/useWebSpeechSynthesis';
import VoiceService from '../services/VoiceService';
import './Chat.css';

const Chat = () => {
  const [messages, setMessages] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [currentLanguage, setCurrentLanguage] = useState('en-US'); 
  
  const messagesEndRef = useRef(null);
  const { speak, stop: stopSpeech } = useWebSpeechSynthesis();

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // --- 1. HYBRID AUDIO HANDLER (Updated for Arabic) ---
  const handlePlayAudio = useCallback(async (text) => {
    try {
      // Check for Urdu OR Arabic
      if (currentLanguage.includes('ur') || currentLanguage.includes('ar')) {
        console.log(`🌍 Using Backend TTS for ${currentLanguage}...`);
        
        const result = await VoiceService.getBackendAudio(text, currentLanguage);
        
        if (result.success) {
          const audio = new Audio(result.audioUrl);
          audio.play();
        } else {
          console.error("Backend TTS failed:", result.error);
        }
      } else {
        // English uses Browser TTS
        await speak(text, { lang: currentLanguage });
      }
    } catch (err) {
      console.error('Audio Playback Error:', err);
    }
  }, [currentLanguage, speak]);

  // --- 2. MAIN HANDLER WITH TRANSLATION LOGIC ---
  const handleSendMessage = useCallback(async (input, inputType = 'text') => {
    if (isLoading) return;
    setIsLoading(true);
    setError(null);
    stopSpeech();

    // 1. Show User Message IMMEDIATELY (in their language)
    setMessages(prev => [...prev, {
      id: Date.now(),
      text: input,
      isUser: true,
      timestamp: new Date(),
      inputType
    }]);

    try {
      let promptToSend = input;

      // --- STEP A: Translate Input to English (if needed) ---
      if (!currentLanguage.startsWith('en')) {
        console.log(`Translating input (${currentLanguage}) to English...`);
        const transResult = await VoiceService.translateText(input, 'en');
        if (transResult.success) {
          promptToSend = transResult.text;
          console.log("Sending translated prompt:", promptToSend);
        }
      }

      // --- STEP B: Send to Sahrish's Backend ---
      const result = await VoiceService.sendChatMessage(promptToSend);

      if (!result.success) {
        throw new Error(result.error || "Backend connection failed");
      }

      let botResponse = result.response;

      // --- STEP C: Translate Output back to User Language (if needed) ---
      if (!currentLanguage.startsWith('en')) {
        // Map language codes for translator (ur-PK -> ur, ar-SA -> ar)
        const targetLangCode = currentLanguage.split('-')[0];
        console.log(`Translating response to ${targetLangCode}...`);
        
        const transBackResult = await VoiceService.translateText(botResponse, targetLangCode);
        if (transBackResult.success) {
          botResponse = transBackResult.text;
        }
      }

      // 2. Show Bot Message (in user's language)
      setMessages(prev => [...prev, {
        id: Date.now() + 1,
        text: botResponse,
        isUser: false,
        timestamp: new Date()
      }]);

      // 3. Auto-Play Audio (using Hybrid logic)
      if (botResponse) {
        setTimeout(() => {
          handlePlayAudio(botResponse);
        }, 100);
      }

    } catch (err) {
      console.error("Chat Flow Error:", err);
      setError("Error: " + err.message);
    } finally {
      setIsLoading(false);
    }
  }, [isLoading, currentLanguage, handlePlayAudio, stopSpeech]);

  const clearChat = () => {
    setMessages([]);
    stopSpeech();
    setError(null);
  };

  return (
    <div className="chat-container">
      <div className="chat-header">
        <div className="chat-title">
          <h1>WebVox Bot</h1>
          <div className="status-indicator connected">
            <span className="status-dot"></span>
            <span className="status-text">Multilingual AI Active</span>
          </div>
        </div>
        <div className="header-actions">
          <button className="clear-button" onClick={clearChat}>🗑️</button>
        </div>
      </div>

      <div className="messages-container">
        {messages.length === 0 ? (
          <div className="welcome-message">
             <div className="welcome-content">
              <h2>Welcome / خوش آمدید / أهلاً بك</h2>
              <p>Select your language below and start speaking.</p>
            </div>
          </div>
        ) : (
          messages.map((m) => (
            <ChatMessage key={m.id} message={m.text} isUser={m.isUser} />
          ))
        )}
        <div ref={messagesEndRef} />
      </div>

      {error && (
        <div className="error-message">
          <span className="error-icon">⚠️</span>
          <span className="error-text">{error}</span>
          <button className="error-close" onClick={() => setError(null)}>✕</button>
        </div>
      )}

      <ChatInput 
        onSendMessage={handleSendMessage}
        isLoading={isLoading}
        language={currentLanguage}
        onLanguageChange={setCurrentLanguage}
      />
    </div>
  );
};

export default Chat;