import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Search, X, ArrowRight } from 'lucide-react';

/**
 * Command palette — opens on Cmd+K / Ctrl+K.
 * Props:
 *   navItems  — array of { id, label, icon: IconComponent }
 *   onNavigate — (pageId) => void
 *   onClose   — () => void (called after navigation or Escape)
 */
export default function CommandPalette({ navItems = [], onNavigate, onClose }) {
  const [query, setQuery] = useState('');
  const inputRef = useRef(null);
  const [selected, setSelected] = useState(0);

  // Focus input on mount
  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  // Filter items by query
  const results = query.trim()
    ? navItems.filter(item =>
        item.label.toLowerCase().includes(query.toLowerCase()) ||
        item.id.toLowerCase().includes(query.toLowerCase())
      )
    : navItems;

  // Clamp selected index when results change
  useEffect(() => {
    setSelected(s => Math.min(s, Math.max(0, results.length - 1)));
  }, [results.length]);

  const go = useCallback((id) => {
    onNavigate(id);
    onClose();
  }, [onNavigate, onClose]);

  const handleKey = (e) => {
    if (e.key === 'Escape') { onClose(); return; }
    if (e.key === 'ArrowDown') { e.preventDefault(); setSelected(s => Math.min(s + 1, results.length - 1)); return; }
    if (e.key === 'ArrowUp')   { e.preventDefault(); setSelected(s => Math.max(s - 1, 0)); return; }
    if (e.key === 'Enter' && results[selected]) { go(results[selected].id); return; }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center pt-[15vh] px-4"
      onClick={onClose}
    >
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />

      {/* Panel */}
      <div
        className="relative w-full max-w-lg bg-zinc-900 border border-zinc-700/60 rounded-2xl shadow-2xl overflow-hidden"
        onClick={e => e.stopPropagation()}
      >
        {/* Search input */}
        <div className="flex items-center gap-3 px-4 py-3 border-b border-zinc-800">
          <Search className="w-4 h-4 text-zinc-500 flex-shrink-0" />
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={e => { setQuery(e.target.value); setSelected(0); }}
            onKeyDown={handleKey}
            placeholder="Search pages..."
            className="flex-1 bg-transparent text-white placeholder-zinc-600 text-sm focus:outline-none"
          />
          <kbd className="hidden sm:flex items-center gap-1 text-xs text-zinc-600 bg-zinc-800 px-1.5 py-0.5 rounded">
            ESC
          </kbd>
          <button onClick={onClose} className="text-zinc-600 hover:text-zinc-400">
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Results */}
        <div className="max-h-72 overflow-y-auto py-2">
          {results.length === 0 ? (
            <p className="text-center text-zinc-600 text-sm py-8">No pages found</p>
          ) : (
            results.map((item, idx) => {
              const Icon = item.icon;
              const isSelected = idx === selected;
              return (
                <button
                  key={item.id}
                  onClick={() => go(item.id)}
                  onMouseEnter={() => setSelected(idx)}
                  className={`w-full flex items-center gap-3 px-4 py-2.5 text-left transition-colors ${
                    isSelected
                      ? 'bg-orange-500/15 text-orange-400'
                      : 'text-zinc-300 hover:bg-zinc-800/50'
                  }`}
                >
                  <Icon className={`w-4 h-4 flex-shrink-0 ${isSelected ? 'text-orange-400' : 'text-zinc-500'}`} />
                  <span className="text-sm font-medium flex-1">{item.label}</span>
                  {isSelected && <ArrowRight className="w-3.5 h-3.5 text-orange-400 flex-shrink-0" />}
                </button>
              );
            })
          )}
        </div>

        {/* Footer hint */}
        <div className="px-4 py-2 border-t border-zinc-800 flex items-center gap-4 text-xs text-zinc-600">
          <span><kbd className="bg-zinc-800 px-1 rounded">↑↓</kbd> navigate</span>
          <span><kbd className="bg-zinc-800 px-1 rounded">↵</kbd> go</span>
          <span><kbd className="bg-zinc-800 px-1 rounded">esc</kbd> close</span>
        </div>
      </div>
    </div>
  );
}
