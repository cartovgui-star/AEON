import React, { useState, useRef, useEffect } from 'react';

const API_URL = process.env.REACT_APP_BACKEND_URL;

// Voice options with descriptions
const VOICE_OPTIONS = {
  guy: { name: 'Guy', desc: 'Confident American (default)' },
  davis: { name: 'Davis', desc: 'Deep American' },
  tony: { name: 'Tony', desc: 'Casual American' },
  jason: { name: 'Jason', desc: 'Professional American' },
  aria: { name: 'Aria', desc: 'American female' },
  jenny: { name: 'Jenny', desc: 'Casual female' },
  british: { name: 'Ryan', desc: 'British male' },
  australian: { name: 'William', desc: 'Australian male' }
};

export default function VoiceChat({ onClose }) {
  const [isListening, setIsListening] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [messages, setMessages] = useState([]);
  const [selectedVoice, setSelectedVoice] = useState('guy');
  const [showVoiceSelect, setShowVoiceSelect] = useState(false);
  const [error, setError] = useState(null);
  
  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);
  const audioRef = useRef(null);
  const messagesEndRef = useRef(null);

  // Scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Start recording
  const startListening = async () => {
    try {
      setError(null);
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      
      const mediaRecorder = new MediaRecorder(stream, {
        mimeType: 'audio/webm;codecs=opus'
      });
      
      mediaRecorderRef.current = mediaRecorder;
      audioChunksRef.current = [];
      
      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };
      
      mediaRecorder.onstop = async () => {
        const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
        stream.getTracks().forEach(track => track.stop());
        await processAudio(audioBlob);
      };
      
      mediaRecorder.start();
      setIsListening(true);
      
    } catch (err) {
      console.error('Microphone error:', err);
      setError('Could not access microphone. Please allow microphone access.');
    }
  };

  // Stop recording
  const stopListening = () => {
    if (mediaRecorderRef.current && isListening) {
      mediaRecorderRef.current.stop();
      setIsListening(false);
    }
  };

  // Process audio and get response
  const processAudio = async (audioBlob) => {
    setIsProcessing(true);
    
    try {
      const formData = new FormData();
      formData.append('audio', audioBlob, 'recording.webm');
      
      const response = await fetch(`${API_URL}/api/voice/chat`, {
        method: 'POST',
        body: formData
      });
      
      const data = await response.json();
      
      if (data.error) {
        setError(data.error);
        setIsProcessing(false);
        return;
      }
      
      // Add messages
      setMessages(prev => [
        ...prev,
        { role: 'user', text: data.user_text },
        { role: 'aeon', text: data.aeon_text }
      ]);
      
      // Play audio response
      if (data.audio) {
        await playAudio(data.audio);
      }
      
    } catch (err) {
      console.error('Voice chat error:', err);
      setError('Failed to process voice. Please try again.');
    }
    
    setIsProcessing(false);
  };

  // Play audio from base64
  const playAudio = async (base64Audio) => {
    return new Promise((resolve) => {
      setIsSpeaking(true);
      
      const audio = new Audio(`data:audio/mp3;base64,${base64Audio}`);
      audioRef.current = audio;
      
      audio.onended = () => {
        setIsSpeaking(false);
        resolve();
      };
      
      audio.onerror = () => {
        setIsSpeaking(false);
        resolve();
      };
      
      audio.play().catch(() => {
        setIsSpeaking(false);
        resolve();
      });
    });
  };

  // Stop speaking
  const stopSpeaking = () => {
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.currentTime = 0;
      setIsSpeaking(false);
    }
  };

  // Change voice
  const changeVoice = async (voice) => {
    setSelectedVoice(voice);
    setShowVoiceSelect(false);
    
    try {
      await fetch(`${API_URL}/api/voice/set?voice=${voice}`, {
        method: 'POST'
      });
    } catch (err) {
      console.error('Failed to set voice:', err);
    }
  };

  // Clear conversation
  const clearConversation = async () => {
    setMessages([]);
    try {
      await fetch(`${API_URL}/api/voice/clear`, { method: 'POST' });
    } catch (err) {
      console.error('Failed to clear history:', err);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className="bg-zinc-900 rounded-2xl w-full max-w-lg border border-zinc-800 overflow-hidden" data-testid="voice-chat-modal">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-zinc-800">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-gradient-to-br from-orange-500 to-amber-600 flex items-center justify-center">
              <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
              </svg>
            </div>
            <div>
              <h3 className="font-semibold text-white">Talk to Aeon</h3>
              <p className="text-xs text-zinc-400">Voice: {VOICE_OPTIONS[selectedVoice]?.name}</p>
            </div>
          </div>
          <button 
            onClick={onClose}
            className="text-zinc-400 hover:text-white transition-colors"
            data-testid="close-voice-chat"
          >
            <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Messages */}
        <div className="h-80 overflow-y-auto p-4 space-y-3">
          {messages.length === 0 && (
            <div className="text-center text-zinc-500 py-8">
              <svg className="w-12 h-12 mx-auto mb-3 opacity-50" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
              </svg>
              <p>Press the mic button and start talking</p>
              <p className="text-sm mt-1">Aeon is listening...</p>
            </div>
          )}
          
          {messages.map((msg, i) => (
            <div 
              key={i} 
              className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              <div 
                className={`max-w-[80%] rounded-2xl px-4 py-2 ${
                  msg.role === 'user' 
                    ? 'bg-orange-600 text-white' 
                    : 'bg-zinc-800 text-zinc-100'
                }`}
              >
                <p className="text-sm">{msg.text}</p>
              </div>
            </div>
          ))}
          
          {error && (
            <div className="bg-red-900/30 border border-red-800 rounded-lg p-3 text-red-400 text-sm">
              {error}
            </div>
          )}
          
          <div ref={messagesEndRef} />
        </div>

        {/* Controls */}
        <div className="p-4 border-t border-zinc-800">
          {/* Status */}
          <div className="text-center mb-4">
            {isListening && (
              <span className="text-orange-400 flex items-center justify-center gap-2">
                <span className="w-2 h-2 bg-red-500 rounded-full animate-pulse"></span>
                Listening...
              </span>
            )}
            {isProcessing && (
              <span className="text-amber-400 flex items-center justify-center gap-2">
                <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                Processing...
              </span>
            )}
            {isSpeaking && (
              <span className="text-green-400 flex items-center justify-center gap-2">
                <span className="flex gap-0.5">
                  <span className="w-1 h-3 bg-green-400 rounded animate-pulse" style={{animationDelay: '0ms'}}></span>
                  <span className="w-1 h-4 bg-green-400 rounded animate-pulse" style={{animationDelay: '150ms'}}></span>
                  <span className="w-1 h-2 bg-green-400 rounded animate-pulse" style={{animationDelay: '300ms'}}></span>
                  <span className="w-1 h-5 bg-green-400 rounded animate-pulse" style={{animationDelay: '450ms'}}></span>
                </span>
                Aeon speaking...
              </span>
            )}
          </div>

          {/* Buttons */}
          <div className="flex items-center justify-center gap-4">
            {/* Voice selector */}
            <div className="relative">
              <button
                onClick={() => setShowVoiceSelect(!showVoiceSelect)}
                className="p-3 rounded-full bg-zinc-800 hover:bg-zinc-700 transition-colors text-zinc-400"
                title="Change voice"
                data-testid="voice-select-btn"
              >
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                </svg>
              </button>
              
              {showVoiceSelect && (
                <div className="absolute bottom-full left-0 mb-2 bg-zinc-800 rounded-lg border border-zinc-700 py-2 w-48 shadow-xl">
                  {Object.entries(VOICE_OPTIONS).map(([key, { name, desc }]) => (
                    <button
                      key={key}
                      onClick={() => changeVoice(key)}
                      className={`w-full px-4 py-2 text-left text-sm hover:bg-zinc-700 transition-colors ${
                        selectedVoice === key ? 'text-orange-400' : 'text-zinc-300'
                      }`}
                    >
                      <div className="font-medium">{name}</div>
                      <div className="text-xs text-zinc-500">{desc}</div>
                    </button>
                  ))}
                </div>
              )}
            </div>

            {/* Main mic button */}
            <button
              onClick={isListening ? stopListening : startListening}
              disabled={isProcessing || isSpeaking}
              className={`p-6 rounded-full transition-all transform ${
                isListening 
                  ? 'bg-red-600 hover:bg-red-700 scale-110 animate-pulse' 
                  : isProcessing || isSpeaking
                    ? 'bg-zinc-700 cursor-not-allowed'
                    : 'bg-gradient-to-br from-orange-500 to-amber-600 hover:from-orange-600 hover:to-amber-700 hover:scale-105'
              }`}
              data-testid="mic-button"
            >
              {isListening ? (
                <svg className="w-8 h-8 text-white" fill="currentColor" viewBox="0 0 24 24">
                  <rect x="6" y="6" width="12" height="12" rx="2" />
                </svg>
              ) : (
                <svg className="w-8 h-8 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
                </svg>
              )}
            </button>

            {/* Stop speaking / Clear */}
            <button
              onClick={isSpeaking ? stopSpeaking : clearConversation}
              className="p-3 rounded-full bg-zinc-800 hover:bg-zinc-700 transition-colors text-zinc-400"
              title={isSpeaking ? "Stop speaking" : "Clear conversation"}
              data-testid="secondary-btn"
            >
              {isSpeaking ? (
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 10a1 1 0 011-1h4a1 1 0 011 1v4a1 1 0 01-1 1h-4a1 1 0 01-1-1v-4z" />
                </svg>
              ) : (
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                </svg>
              )}
            </button>
          </div>

          <p className="text-center text-xs text-zinc-500 mt-4">
            {isListening ? 'Tap to stop recording' : 'Tap the mic and speak'}
          </p>
        </div>
      </div>
    </div>
  );
}
