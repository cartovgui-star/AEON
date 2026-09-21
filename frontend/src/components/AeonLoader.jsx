import React from 'react';

/**
 * AeonLoader — branded loading screen
 * Props:
 *   message  — text under the logo (default: "Loading...")
 *   fullScreen — if true, takes full viewport height (default: false → h-64)
 *   size     — "sm" | "md" | "lg" (default: "md")
 */
export default function AeonLoader({ message = "Loading...", fullScreen = false, size = "md" }) {
  const sizeMap = {
    sm: { logo: "w-8 h-8", icon: "w-4 h-4", ring1: "w-12 h-12", ring2: "w-16 h-16", text: "text-xs" },
    md: { logo: "w-12 h-12", icon: "w-6 h-6", ring1: "w-20 h-20", ring2: "w-28 h-28", text: "text-sm" },
    lg: { logo: "w-16 h-16", icon: "w-8 h-8", ring1: "w-28 h-28", ring2: "w-36 h-36", text: "text-base" },
  };
  const s = sizeMap[size] || sizeMap.md;
  const containerH = fullScreen ? "min-h-screen" : "h-64";

  return (
    <div className={`flex flex-col items-center justify-center ${containerH} gap-6`}>
      {/* Rings + Logo */}
      <div className="relative flex items-center justify-center">
        {/* Outer ring */}
        <div
          className={`absolute ${s.ring2} rounded-full border border-orange-500/10`}
          style={{ animation: "aeon-pulse 3s ease-in-out infinite" }}
        />
        {/* Spinning ring */}
        <div
          className={`absolute ${s.ring1} rounded-full border-2 border-transparent border-t-orange-500/60 border-r-orange-500/20`}
          style={{ animation: "aeon-spin 1.2s linear infinite" }}
        />
        {/* Inner glow */}
        <div
          className={`absolute ${s.ring1} rounded-full`}
          style={{
            background: "radial-gradient(circle, rgba(249,115,22,0.08) 0%, transparent 70%)",
            animation: "aeon-pulse 2s ease-in-out infinite",
          }}
        />
        {/* Logo box */}
        <div className={`${s.logo} rounded-xl bg-gradient-to-br from-orange-500 to-amber-600 flex items-center justify-center shadow-lg`}
          style={{ boxShadow: "0 0 24px rgba(249,115,22,0.35)" }}>
          {/* Bot/A icon */}
          <svg className={s.icon} viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M12 2L2 7l10 5 10-5-10-5z" stroke="white" strokeWidth="1.5" strokeLinejoin="round"/>
            <path d="M2 17l10 5 10-5" stroke="white" strokeWidth="1.5" strokeLinejoin="round"/>
            <path d="M2 12l10 5 10-5" stroke="white" strokeWidth="1.5" strokeLinejoin="round"/>
          </svg>
        </div>
      </div>

      {/* Text */}
      <div className="flex flex-col items-center gap-1">
        <span className={`${s.text} font-semibold text-zinc-300 tracking-wide`}>{message}</span>
        {/* Dot pulse */}
        <div className="flex gap-1 mt-1">
          {[0, 1, 2].map(i => (
            <div
              key={i}
              className="w-1 h-1 rounded-full bg-orange-500/60"
              style={{ animation: `aeon-dot 1.2s ease-in-out ${i * 0.2}s infinite` }}
            />
          ))}
        </div>
      </div>

      <style>{`
        @keyframes aeon-spin {
          from { transform: rotate(0deg); }
          to   { transform: rotate(360deg); }
        }
        @keyframes aeon-pulse {
          0%, 100% { opacity: 0.4; transform: scale(1); }
          50%       { opacity: 1;   transform: scale(1.05); }
        }
        @keyframes aeon-dot {
          0%, 80%, 100% { opacity: 0.2; transform: scale(0.8); }
          40%           { opacity: 1;   transform: scale(1.2); }
        }
      `}</style>
    </div>
  );
}
