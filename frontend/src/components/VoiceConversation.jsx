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
  
  const recognitionRef = useRef(null);
  const audioRef = useRef(null);
  const silenceTimerRef = useRef(null);
  const isProcessingRef = useRef(false);
  const messagesEndRef = useRef(null);

  // Scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Initialize speech recognition
  useEffect(() => {
    if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
      const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
      recognitionRef.current = new SpeechRecognition();
      recognitionRef.current.continuous = true;
      recognitionRef.current.interimResults = true;
      recognitionRef.current.lang = 'en-US';

      recognitionRef.current.onresult = (event) => {
        let interimTranscript = '';
        let finalTranscript = '';

        for (let i = event.resultIndex; i < event.results.length; i++) {
          const transcript = event.results[i][0].transcript;
          if (event.results[i].isFinal) {
            finalTranscript += transcript;
          } else {
            interimTranscript += transcript;
          }
        }

        setTranscript(finalTranscript || interimTranscript);
        
        // Reset silence timer on any speech
        if (silenceTimerRef.current) {
          clearTimeout(silenceTimerRef.current);
        }

        // If we have final transcript, wait for silence then process
        if (finalTranscript && !isProcessingRef.current) {
          silenceTimerRef.current = setTimeout(() => {
            if (finalTranscript.trim()) {
              processUserSpeech(finalTranscript.trim());
            }
          }, 1500); // 1.5s silence = user finished speaking
        }
      };

      recognitionRef.current.onerror = (event) => {
        console.error('Speech recognition error:', event.error);
        if (event.error !== 'no-speech' && event.error !== 'aborted') {
          setError(`Speech error: ${event.error}`);
        }
      };

      recognitionRef.current.onend = () => {
        // Restart if still active and not processing
        if (isActive && !isProcessingRef.current && !isSpeaking) {
          try {
            recognitionRef.current.start();
          } catch (e) {
            // Already started
          }
        }
        setIsListening(false);
      };

      recognitionRef.current.onstart = () => {
        setIsListening(true);
      };
    } else {
      setError('Speech recognition not supported in this browser. Try Chrome.');
    }

    return () => {
      if (recognitionRef.current) {
        recognitionRef.current.stop();
      }
      if (silenceTimerRef.current) {
        clearTimeout(silenceTimerRef.current);
      }
    };
  }, [isActive, isSpeaking]);

  // Process user speech
  const processUserSpeech = useCallback(async (text) => {
    if (isProcessingRef.current || !text.trim()) return;
    
    isProcessingRef.current = true;
    setIsProcessing(true);
    setTranscript('');
    
    // Stop listening while processing
    if (recognitionRef.current) {
      recognitionRef.current.stop();
    }

    // Add user message
    setMessages(prev => [...prev, { role: 'user', text }]);

    try {
      // Get Aeon's response
      const response = await fetch(`${API_URL}/api/voice/respond`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text, voice: selectedVoice })
      });

      const data = await response.json();

      if (data.error) {
        setError(data.error);
        isProcessingRef.current = false;
        setIsProcessing(false);
        startListening();
        return;
      }

      // Add Aeon's response
      setAeonResponse(data.text);
      setMessages(prev => [...prev, { role: 'aeon', text: data.text }]);

      // Play audio
      if (data.audio) {
        await playAudio(data.audio);
      }

    } catch (err) {
      console.error('Error:', err);
      setError('Failed to get response. Try again.');
    }

    isProcessingRef.current = false;
    setIsProcessing(false);
    
    // Resume listening after Aeon finishes
    if (isActive) {
      startListening();
    }
  }, [selectedVoice, isActive]);

  // Play audio response
  const playAudio = (base64Audio) => {
    return new Promise((resolve) => {
      setIsSpeaking(true);
      
      const audio = new Audio(`data:audio/mp3;base64,${base64Audio}`);
      audioRef.current = audio;

      audio.onended = () => {
        setIsSpeaking(false);
        setAeonResponse('');
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

  // Start listening
  const startListening = () => {
    if (recognitionRef.current && !isProcessingRef.current) {
      try {
        recognitionRef.current.start();
      } catch (e) {
        // Already started
      }
    }
  };

  // Stop everything and interrupt Aeon
  const interrupt = () => {
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.currentTime = 0;
    }
    setIsSpeaking(false);
    setAeonResponse('');
  };

  // Toggle conversation
  const toggleConversation = () => {
    if (isActive) {
      // Stop
      setIsActive(false);
      if (recognitionRef.current) {
        recognitionRef.current.stop();
      }
      interrupt();
    } else {
      // Start
      setIsActive(true);
      setError(null);
      startListening();
    }
  };

  // Visualizer effect
  useEffect(() => {
    let animationId;
    const animate = () => {
      if (isListening) {
        setVolume(Math.random() * 50 + 20);
      } else if (isSpeaking) {
        setVolume(Math.random() * 80 + 40);
      } else {
        setVolume(10);
      }
      animationId = requestAnimationFrame(animate);
    };
    animate();
    return () => cancelAnimationFrame(animationId);
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
            <h3 className="font-semibold text-white">Aeon Voice</h3>
            <p className="text-xs text-zinc-400">
              {isActive ? (isSpeaking ? 'Speaking...' : isProcessing ? 'Thinking...' : 'Listening...') : 'Tap to start'}
            </p>
          </div>
        </div>
        
        <div className="flex items-center gap-2">
          {/* Voice selector */}
          <select 
            value={selectedVoice}
            onChange={(e) => setSelectedVoice(e.target.value)}
            className="bg-zinc-800 text-zinc-300 text-sm rounded px-2 py-1 border border-zinc-700"
          >
            {Object.entries(VOICES).map(([key, name]) => (
              <option key={key} value={key}>{name}</option>
            ))}
          </select>
          
          <button 
            onClick={onClose}
            className="text-zinc-400 hover:text-white p-2"
          >
            <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      </div>

      {/* Main area */}
      <div className="flex-1 flex flex-col items-center justify-center p-8">
        {/* Visualizer */}
        <div 
          className={`relative w-48 h-48 rounded-full flex items-center justify-center transition-all duration-300 ${
            isActive 
              ? isSpeaking 
                ? 'bg-gradient-to-br from-green-500/20 to-emerald-600/20' 
                : 'bg-gradient-to-br from-orange-500/20 to-amber-600/20'
              : 'bg-zinc-800/50'
          }`}
          style={{
            boxShadow: isActive ? `0 0 ${volume}px ${isSpeaking ? '#22c55e' : '#f97316'}` : 'none'
          }}
        >
          {/* Pulse rings */}
          {isActive && (
            <>
              <div className={`absolute inset-0 rounded-full animate-ping opacity-20 ${isSpeaking ? 'bg-green-500' : 'bg-orange-500'}`} style={{animationDuration: '2s'}}></div>
              <div className={`absolute inset-4 rounded-full animate-ping opacity-30 ${isSpeaking ? 'bg-green-500' : 'bg-orange-500'}`} style={{animationDuration: '2.5s'}}></div>
            </>
          )}
          
          {/* Center icon */}
          <div className={`w-24 h-24 rounded-full flex items-center justify-center ${
            isActive 
              ? isSpeaking 
                ? 'bg-gradient-to-br from-green-500 to-emerald-600' 
                : 'bg-gradient-to-br from-orange-500 to-amber-600'
              : 'bg-zinc-700'
          }`}>
            {isProcessing ? (
              <svg className="w-10 h-10 text-white animate-spin" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
              </svg>
            ) : isSpeaking ? (
              <svg className="w-10 h-10 text-white" fill="currentColor" viewBox="0 0 24 24">
                <path d="M3 9v6h4l5 5V4L7 9H3zm13.5 3c0-1.77-1.02-3.29-2.5-4.03v8.05c1.48-.73 2.5-2.25 2.5-4.02zM14 3.23v2.06c2.89.86 5 3.54 5 6.71s-2.11 5.85-5 6.71v2.06c4.01-.91 7-4.49 7-8.77s-2.99-7.86-7-8.77z"/>
              </svg>
            ) : (
              <svg className="w-10 h-10 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
              </svg>
            )}
          </div>
        </div>

        {/* Current transcript/response */}
        <div className="mt-8 text-center max-w-md">
          {transcript && (
            <p className="text-orange-400 text-lg animate-pulse">"{transcript}"</p>
          )}
          {aeonResponse && (
            <p className="text-green-400 text-lg mt-2">"{aeonResponse}"</p>
          )}
          {!transcript && !aeonResponse && isActive && !isProcessing && (
            <p className="text-zinc-500">Speak naturally... I'm listening</p>
          )}
          {error && (
            <p className="text-red-400 mt-2">{error}</p>
          )}
        </div>

        {/* Start/Stop button */}
        <button
          onClick={toggleConversation}
          className={`mt-8 px-8 py-4 rounded-full text-lg font-semibold transition-all ${
            isActive
              ? 'bg-red-600 hover:bg-red-700 text-white'
              : 'bg-gradient-to-r from-orange-500 to-amber-600 hover:from-orange-600 hover:to-amber-700 text-white'
          }`}
        >
          {isActive ? 'End Conversation' : 'Start Talking'}
        </button>

        {/* Interrupt button */}
        {isSpeaking && (
          <button
            onClick={interrupt}
            className="mt-4 px-4 py-2 text-sm text-zinc-400 hover:text-white"
          >
            Tap to interrupt
          </button>
        )}
      </div>

      {/* Message history */}
      <div className="h-48 border-t border-zinc-800 overflow-y-auto p-4">
        <div className="max-w-2xl mx-auto space-y-2">
          {messages.map((msg, i) => (
            <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              <div className={`max-w-[80%] rounded-2xl px-4 py-2 text-sm ${
                msg.role === 'user' 
                  ? 'bg-orange-600/20 text-orange-200' 
                  : 'bg-green-600/20 text-green-200'
              }`}>
                {msg.text}
              </div>
            </div>
          ))}
          <div ref={messagesEndRef} />
        </div>
      </div>
    </div>
  );
}
