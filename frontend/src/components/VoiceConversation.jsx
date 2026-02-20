import React, { useState, useRef, useEffect, useCallback } from 'react';

const API_URL = process.env.REACT_APP_BACKEND_URL;

// Voice options
const VOICES = {
  guy: 'Confident American',
  davis: 'Deep American',
  british: 'British',
  australian: 'Australian'
};

export default function VoiceConversation({ onClose }) {
  const [permissionGranted, setPermissionGranted] = useState(false);
  const [isActive, setIsActive] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [transcript, setTranscript] = useState('');
  const [aeonResponse, setAeonResponse] = useState('');
  const [messages, setMessages] = useState([]);
  const [selectedVoice, setSelectedVoice] = useState('guy');
  const [error, setError] = useState(null);
  const [volume, setVolume] = useState(0);
  const [textInput, setTextInput] = useState('');
  const [showTextInput, setShowTextInput] = useState(false);
  
  const recognitionRef = useRef(null);
  const audioRef = useRef(null);
  const silenceTimerRef = useRef(null);
  const isProcessingRef = useRef(false);
  const messagesEndRef = useRef(null);

  // Scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Request microphone permission
  const requestPermission = async () => {
    try {
      setError(null);
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      stream.getTracks().forEach(track => track.stop());
      setPermissionGranted(true);
      return true;
    } catch (err) {
      console.error('Microphone permission denied:', err);
      setError('Microphone access denied. Please allow microphone in browser settings.');
      return false;
    }
  };

  // Initialize speech recognition
  const initSpeechRecognition = useCallback(() => {
    if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
      setError('Speech recognition not supported. Use Chrome or Edge.');
      return null;
    }

    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    const recognition = new SpeechRecognition();
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = 'en-US';

    recognition.onresult = (event) => {
      let interimTranscript = '';
      let finalTranscript = '';

      for (let i = event.resultIndex; i < event.results.length; i++) {
        const text = event.results[i][0].transcript;
        if (event.results[i].isFinal) {
          finalTranscript += text;
        } else {
          interimTranscript += text;
        }
      }

      setTranscript(finalTranscript || interimTranscript);
      
      if (silenceTimerRef.current) {
        clearTimeout(silenceTimerRef.current);
      }

      if (finalTranscript && !isProcessingRef.current) {
        silenceTimerRef.current = setTimeout(() => {
          if (finalTranscript.trim()) {
            processUserSpeech(finalTranscript.trim());
          }
        }, 1500);
      }
    };

    recognition.onerror = (event) => {
      console.error('Speech error:', event.error);
      if (event.error === 'not-allowed') {
        setError('Microphone blocked. Click the mic icon in browser address bar to allow.');
        setPermissionGranted(false);
      }
    };

    recognition.onend = () => {
      setIsListening(false);
      if (isActive && !isProcessingRef.current && !isSpeaking && permissionGranted) {
        setTimeout(() => {
          try { recognition.start(); } catch (e) {}
        }, 100);
      }
    };

    recognition.onstart = () => {
      setIsListening(true);
      setError(null);
    };

    return recognition;
  }, [isActive, isSpeaking, permissionGranted]);

  // Process speech
  const processUserSpeech = useCallback(async (text) => {
    if (isProcessingRef.current || !text.trim()) return;
    
    isProcessingRef.current = true;
    setIsProcessing(true);
    setTranscript('');
    
    if (recognitionRef.current) {
      try { recognitionRef.current.stop(); } catch (e) {}
    }

    setMessages(prev => [...prev, { role: 'user', text }]);

    try {
      console.log('Sending to:', `${API_URL}/api/voice/respond`);
      const response = await fetch(`${API_URL}/api/voice/respond`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text, voice: selectedVoice })
      });

      console.log('Response status:', response.status);
      const data = await response.json();
      console.log('Response data:', data);

      if (data.error) {
        setError(data.error);
      } else {
        setAeonResponse(data.text);
        setMessages(prev => [...prev, { role: 'aeon', text: data.text }]);
        if (data.audio) {
          await playAudio(data.audio);
        }
      }
    } catch (err) {
      console.error('Fetch error:', err);
      setError('Connection error: ' + err.message);
    }

    isProcessingRef.current = false;
    setIsProcessing(false);
    
    if (isActive) startListening();
  }, [selectedVoice, isActive]);

  // Play audio - requires user interaction first (handled by Start button)
  const playAudio = async (base64Audio) => {
    setIsSpeaking(true);
    
    try {
      // Create audio context to unlock audio (some browsers need this)
      const AudioContext = window.AudioContext || window.webkitAudioContext;
      if (AudioContext) {
        const ctx = new AudioContext();
        await ctx.resume();
        ctx.close();
      }
      
      // Create and play audio
      const audio = new Audio(`data:audio/mp3;base64,${base64Audio}`);
      audioRef.current = audio;
      
      await new Promise((resolve, reject) => {
        audio.onended = () => resolve();
        audio.onerror = (e) => reject(e);
        
        audio.play().catch(reject);
      });
      
    } catch (err) {
      console.error('Audio playback error:', err);
    }
    
    setIsSpeaking(false);
    setAeonResponse('');
  };

  // Start listening
  const startListening = useCallback(() => {
    if (!recognitionRef.current) {
      recognitionRef.current = initSpeechRecognition();
    }
    if (recognitionRef.current && !isProcessingRef.current) {
      try { recognitionRef.current.start(); } catch (e) {}
    }
  }, [initSpeechRecognition]);

  // Interrupt
  const interrupt = () => {
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.currentTime = 0;
    }
    setIsSpeaking(false);
    setAeonResponse('');
  };

  // Start conversation
  const startConversation = async () => {
    if (!permissionGranted) {
      const granted = await requestPermission();
      if (!granted) return;
    }
    setIsActive(true);
    setError(null);
    recognitionRef.current = initSpeechRecognition();
    startListening();
  };

  // Stop conversation
  const stopConversation = () => {
    setIsActive(false);
    if (recognitionRef.current) {
      try { recognitionRef.current.stop(); } catch (e) {}
    }
    interrupt();
  };

  // Handle text submit
  const handleTextSubmit = (e) => {
    e.preventDefault();
    if (textInput.trim() && !isProcessingRef.current) {
      processUserSpeech(textInput.trim());
      setTextInput('');
    }
  };

  // Cleanup
  useEffect(() => {
    return () => {
      if (recognitionRef.current) try { recognitionRef.current.stop(); } catch (e) {}
      if (silenceTimerRef.current) clearTimeout(silenceTimerRef.current);
    };
  }, []);

  // Visualizer
  useEffect(() => {
    let id;
    const animate = () => {
      setVolume(isListening ? Math.random() * 50 + 20 : isSpeaking ? Math.random() * 80 + 40 : 10);
      id = requestAnimationFrame(animate);
    };
    animate();
    return () => cancelAnimationFrame(id);
  }, [isListening, isSpeaking]);

  return (
    <div className="fixed inset-0 bg-black z-50 flex flex-col">
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
            <p className="text-xs text-zinc-400">
              {!permissionGranted ? 'Click Start to allow mic' : 
               isActive ? (isSpeaking ? 'Speaking...' : isProcessing ? 'Thinking...' : 'Listening...') : 'Ready'}
            </p>
          </div>
        </div>
        
        <div className="flex items-center gap-2">
          <select value={selectedVoice} onChange={(e) => setSelectedVoice(e.target.value)}
            className="bg-zinc-800 text-zinc-300 text-sm rounded px-2 py-1 border border-zinc-700">
            {Object.entries(VOICES).map(([key, name]) => (
              <option key={key} value={key}>{name}</option>
            ))}
          </select>
          <button onClick={onClose} className="text-zinc-400 hover:text-white p-2">
            <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      </div>

      {/* Main */}
      <div className="flex-1 flex flex-col items-center justify-center p-8">
        <div className={`relative w-48 h-48 rounded-full flex items-center justify-center transition-all duration-300 ${
          isActive ? isSpeaking ? 'bg-green-500/20' : 'bg-orange-500/20' : 'bg-zinc-800/50'
        }`} style={{ boxShadow: isActive ? `0 0 ${volume}px ${isSpeaking ? '#22c55e' : '#f97316'}` : 'none' }}>
          {isActive && (
            <>
              <div className={`absolute inset-0 rounded-full animate-ping opacity-20 ${isSpeaking ? 'bg-green-500' : 'bg-orange-500'}`} style={{animationDuration: '2s'}}></div>
            </>
          )}
          <div className={`w-24 h-24 rounded-full flex items-center justify-center ${
            isActive ? isSpeaking ? 'bg-green-500' : 'bg-orange-500' : 'bg-zinc-700'
          }`}>
            {isProcessing ? (
              <svg className="w-10 h-10 text-white animate-spin" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path>
              </svg>
            ) : isSpeaking ? (
              <svg className="w-10 h-10 text-white" fill="currentColor" viewBox="0 0 24 24">
                <path d="M3 9v6h4l5 5V4L7 9H3zm13.5 3c0-1.77-1.02-3.29-2.5-4.03v8.05c1.48-.73 2.5-2.25 2.5-4.02z"/>
              </svg>
            ) : (
              <svg className="w-10 h-10 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
              </svg>
            )}
          </div>
        </div>

        <div className="mt-8 text-center max-w-md">
          {transcript && <p className="text-orange-400 text-lg">You: "{transcript}"</p>}
          {aeonResponse && <p className="text-green-400 text-lg mt-2">Aeon: "{aeonResponse}"</p>}
          {!transcript && !aeonResponse && isActive && !isProcessing && (
            <p className="text-zinc-500">Speak naturally... I'm listening</p>
          )}
          {error && (
            <div className="mt-4 p-4 bg-red-900/30 border border-red-800 rounded-lg">
              <p className="text-red-400">{error}</p>
            </div>
          )}
        </div>

        <button onClick={isActive ? stopConversation : startConversation}
          className={`mt-8 px-8 py-4 rounded-full text-lg font-semibold transition-all ${
            isActive ? 'bg-red-600 hover:bg-red-700' : 'bg-orange-500 hover:bg-orange-600'
          } text-white`}>
          {isActive ? 'End Conversation' : 'Start Talking'}
        </button>

        {isSpeaking && (
          <button onClick={interrupt} className="mt-4 text-sm text-zinc-400 hover:text-white">
            Tap to interrupt
          </button>
        )}

        {/* Text input fallback */}
        <div className="mt-6 w-full max-w-md">
          {!showTextInput ? (
            <button 
              onClick={() => setShowTextInput(true)}
              className="text-sm text-zinc-500 hover:text-zinc-300 transition-colors"
            >
              Prefer typing? Click here
            </button>
          ) : (
            <form onSubmit={handleTextSubmit} className="flex gap-2">
              <input
                type="text"
                value={textInput}
                onChange={(e) => setTextInput(e.target.value)}
                placeholder="Type your message..."
                disabled={isProcessing}
                className="flex-1 bg-zinc-800 border border-zinc-700 rounded-full px-4 py-2 text-white text-sm focus:outline-none focus:border-orange-500"
                data-testid="voice-text-input"
              />
              <button 
                type="submit"
                disabled={isProcessing || !textInput.trim()}
                className="px-4 py-2 bg-orange-500 hover:bg-orange-600 disabled:bg-zinc-700 disabled:text-zinc-500 text-white rounded-full text-sm font-medium transition-colors"
                data-testid="voice-text-submit"
              >
                Send
              </button>
            </form>
          )}
        </div>
      </div>

      {/* History */}
      <div className="h-40 border-t border-zinc-800 overflow-y-auto p-4">
        <div className="max-w-2xl mx-auto space-y-2">
          {messages.length === 0 && <p className="text-center text-zinc-600 text-sm">Conversation appears here</p>}
          {messages.map((msg, i) => (
            <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              <div className={`max-w-[80%] rounded-2xl px-4 py-2 text-sm ${
                msg.role === 'user' ? 'bg-orange-600/20 text-orange-200' : 'bg-green-600/20 text-green-200'
              }`}>{msg.text}</div>
            </div>
          ))}
          <div ref={messagesEndRef} />
        </div>
      </div>
    </div>
  );
}
