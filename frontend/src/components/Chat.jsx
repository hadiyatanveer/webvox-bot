// src/components/Chat.js
import React, { useState, useRef, useEffect, useCallback } from 'react';
import ChatMessage from './ChatMessage';
import ChatInput from './ChatInput';
import VoiceService from '../services/VoiceService';
import AIBot from './AIBot';
import './Chat.css';

// --- Inline SVG Icons ---
const WarningIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24"
    fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
    <line x1="12" y1="9" x2="12" y2="13" />
    <line x1="12" y1="17" x2="12.01" y2="17" />
  </svg>
);

/**
 * Chat – main chatbot widget component.
 *
 * Customisable via the `theme` prop:
 *   primaryColor       – hex/rgb primary accent (default: teal)
 *   primaryHoverColor  – hover shade of primary
 *   backgroundColor    – widget background
 *   surfaceColor       – header / input surface
 *   textColor          – main text colour
 *   botName            – display name shown in header (default: "WebVox Bot")
 *
 * Example usage in the embedding page:
 *   <Chat theme={{ primaryColor: '#6c47ff', botName: 'My Assistant' }} />
 */

const RefreshIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
    <path d="M23 4v6h-6" /><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10" />
  </svg>
);

const ThemeIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="5" /><path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42" />
  </svg>
);

const DEFAULT_THEME = {};
const HELLOS = ["Hello", "السلام علیکم", "مرحباً"];

const Chat = ({ theme: initialTheme = DEFAULT_THEME }) => {
  const [messages, setMessages] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [currentLanguage, setCurrentLanguage] = useState('en-US');
  const [themeMode, setThemeMode] = useState('light'); // 'light' or 'dark'
  const [widgetMode, setWidgetMode] = useState('full'); // 'full' or 'widget'
  const [dynamicTheme, setDynamicTheme] = useState({});
  const [isTransitioning, setIsTransitioning] = useState(false);
  const [helloIndex, setHelloIndex] = useState(0);
  const [chatBotName, setChatBotName] = useState('WebVox Bot');

  useEffect(() => {
    const timer = setInterval(() => {
      setHelloIndex((prev) => (prev + 1) % HELLOS.length);
    }, 2500);
    return () => clearInterval(timer);
  }, []);

  const messagesEndRef = useRef(null);
  const currentAudioRef = useRef(null);

  // Initialize theme and mode from URL and props
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const modeParam = params.get('mode') || initialTheme.mode || 'full';
    const primaryParam = params.get('primaryColor');
    const bgParam = params.get('bgColor');
    const textParam = params.get('textColor');
    const iconParam = params.get('iconUrl');
    const nameParam = params.get('botName');
    const statusColorParam = params.get('statusColor');
    const agentColorParam = params.get('agentColor');
    const micColorParam = params.get('micColor');

    setWidgetMode(modeParam);
    if (nameParam || initialTheme.botName) {
      setChatBotName(nameParam || initialTheme.botName);
    }

    setDynamicTheme({
      primary: primaryParam || initialTheme.primaryColor,
      bg: bgParam || initialTheme.backgroundColor,
      text: textParam || initialTheme.textColor,
      surface: initialTheme.surfaceColor,
      iconUrl: iconParam,
      statusColor: statusColorParam,
      agentColor: agentColorParam || initialTheme.agentColor,
      micColor: micColorParam || initialTheme.micColor
    });
  }, [
    initialTheme.primaryColor,
    initialTheme.backgroundColor,
    initialTheme.textColor,
    initialTheme.surfaceColor,
    initialTheme.botName,
    initialTheme.agentColor,
    initialTheme.micColor,
    initialTheme.mode
  ]);

  // Handle theme mode (light/dark) logic
  const toggleTheme = () => setThemeMode(prev => prev === 'light' ? 'dark' : 'light');

  // Build CSS variable overrides
  const themeStyle = {
    '--dynamic-primary': dynamicTheme.primary || 'var(--color-primary)',
    '--dynamic-bg': dynamicTheme.bg || 'var(--color-background)',
    '--dynamic-text': dynamicTheme.text || 'var(--color-text)',
    '--dynamic-surface': dynamicTheme.surface || 'var(--color-surface)',
    '--dynamic-border': dynamicTheme.border || 'var(--color-border)',
    '--dynamic-status-color': dynamicTheme.statusColor || '#10B981',
    '--dynamic-agent-color': dynamicTheme.agentColor || 'var(--color-secondary)',
    '--dynamic-mic-color': dynamicTheme.micColor || dynamicTheme.agentColor || 'var(--color-success)',
  };

  const botName = chatBotName;

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const stopAudio = useCallback(() => {
    if (currentAudioRef.current) {
      currentAudioRef.current.pause();
      currentAudioRef.current.currentTime = 0;
      currentAudioRef.current = null;
    }
  }, []);

  // --- 1. AZURE NEURAL AUDIO HANDLER ---
  const handlePlayAudio = useCallback(async (text) => {
    try {
      const result = await VoiceService.getBackendAudio(text, currentLanguage);
      if (result.success) {
        stopAudio();
        const audio = new Audio(result.audioUrl);
        currentAudioRef.current = audio;
        audio.play();
      } else {
        console.error('Backend Azure TTS failed:', result.error);
      }
    } catch (err) {
      console.error('Audio Playback Error:', err);
    }
  }, [currentLanguage, stopAudio]);

  // --- 2. MAIN HANDLER WITH TRANSLATION LOGIC ---
  const handleSendMessage = useCallback(async (input, inputType = 'text') => {
    if (isLoading) return;
    setIsLoading(true);
    setError(null);
    stopAudio();

    setMessages(prev => [...prev, {
      id: Date.now(),
      text: input,
      isUser: true,
      timestamp: new Date(),
      inputType,
    }]);

    try {
      let promptToSend = input;

      if (!currentLanguage.startsWith('en')) {
        const transResult = await VoiceService.translateText(input, 'en');
        if (transResult.success) promptToSend = transResult.text;
      }

      const result = await VoiceService.sendChatMessage(promptToSend);
      if (!result.success) throw new Error(result.error || 'Backend connection failed');

      let botResponse = result.response;

      if (!currentLanguage.startsWith('en')) {
        const targetLangCode = currentLanguage.split('-')[0];
        const transBackResult = await VoiceService.translateText(botResponse, targetLangCode);
        if (transBackResult.success) botResponse = transBackResult.text;
      }

      setMessages(prev => [...prev, {
        id: Date.now() + 1,
        text: botResponse,
        isUser: false,
        timestamp: new Date(),
      }]);

      if (botResponse) {
        setTimeout(() => handlePlayAudio(botResponse), 100);
      }
    } catch (err) {
      console.error('Chat Flow Error:', err);
      setError('Error: ' + err.message);
    } finally {
      setIsLoading(false);
    }
  }, [isLoading, currentLanguage, handlePlayAudio, stopAudio]);

  const clearChat = () => {
    setMessages([]);
    stopAudio();
    setError(null);
    setIsTransitioning(false);
  };

  const handleStartChat = () => {
    setIsTransitioning(true);
    setTimeout(() => {
      handleSendMessage("Hello! I want to know more about your services.");
    }, 500); // Wait for fade-out animation
  };

  const handleInputActivity = useCallback(() => {
    if (messages.length === 0 && !isTransitioning) {
      setIsTransitioning(true);
    }
    stopAudio();
  }, [messages.length, isTransitioning, stopAudio]);



  return (
    <div
      className={`chat-container mode-${widgetMode}`}
      style={themeStyle}
      data-color-scheme={themeMode}
      dir={currentLanguage === 'ar-SA' || currentLanguage === 'ur-IN' ? 'rtl' : 'ltr'}
    >
      <div className="chat-header">
        <div className="header-left">
          <div className="bot-info">
            <span className="bot-name">{botName}</span>
            <div className="status-container">
              <span className="online-dot" />
              <span className="status-text">We're online</span>
            </div>
          </div>
        </div>

        <div className="header-actions">
          <button className="icon-btn" onClick={clearChat} title="Reset chat">
            <RefreshIcon />
          </button>
          <button className="icon-btn" onClick={toggleTheme} title="Toggle theme">
            <ThemeIcon />
          </button>
        </div>
      </div>

      <div className={`messages-container ${messages.length === 0 ? 'empty' : ''}`}>
        {messages.length === 0 ? (
          <div className={`landing-page ${isTransitioning ? 'fade-out' : ''}`}>
            <div className="landing-content">
              <h1 className="landing-title">
                <span key={helloIndex} className="multilingual-hello">
                  {HELLOS[helloIndex]}
                </span>
              </h1>

              <div className="landing-robot-container">
                <AIBot />
              </div>

              <h2 className="landing-subtitle">How can I help you?</h2>

              <button
                className="landing-cta-btn"
                onClick={handleStartChat}
              >
                I want to know!
              </button>
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
          <span className="error-icon"><WarningIcon /></span>
          <span className="error-text">{error}</span>
        </div>
      )}

      <ChatInput
        onSendMessage={handleSendMessage}
        isLoading={isLoading}
        language={currentLanguage}
        onLanguageChange={setCurrentLanguage}
        onInputActivity={handleInputActivity}
      />
    </div>
  );
};

export default Chat;