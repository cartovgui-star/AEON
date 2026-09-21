import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Eye, Heart, Activity, RefreshCw, Radio } from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL;

const TYPE_CONFIG = {
  SENSE: {
    label: 'SENSE',
    color: 'text-blue-400',
    bg: 'bg-blue-500/10 border-blue-500/20',
    dot: 'bg-blue-400',
    Icon: Eye,
  },
  HEAL: {
    label: 'HEAL',
    color: 'text-orange-400',
    bg: 'bg-orange-500/10 border-orange-500/20',
    dot: 'bg-orange-400',
    Icon: Heart,
  },
  ADAPT: {
    label: 'ADAPT',
    color: 'text-green-400',
    bg: 'bg-green-500/10 border-green-500/20',
    dot: 'bg-green-400',
    Icon: Activity,
  },
};

function FeedEntry({ entry }) {
  const cfg = TYPE_CONFIG[entry.type] || TYPE_CONFIG.SENSE;
  const { Icon } = cfg;

  const fmtTime = (ts) => {
    if (!ts) return '—';
    try {
      return new Date(ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    } catch (_) {
      return ts;
    }
  };

  return (
    <div className={`flex items-start gap-2 px-3 py-2 rounded-lg border ${cfg.bg} mb-1.5`}>
      <div className="flex-shrink-0 flex items-center gap-1.5 mt-0.5">
        <div className={`w-1.5 h-1.5 rounded-full ${cfg.dot}`} />
        <Icon className={`w-3 h-3 ${cfg.color}`} />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-0.5">
          <span className={`text-[10px] font-bold uppercase tracking-widest font-mono ${cfg.color}`}>
            {entry.type}
          </span>
          <span className="text-[10px] text-zinc-600 font-mono">{fmtTime(entry.timestamp)}</span>
        </div>
        <p className="text-xs text-zinc-300 break-words leading-relaxed">{entry.summary}</p>
      </div>
    </div>
  );
}

export default function NexusAwarenessFeed() {
  const [feed, setFeed] = useState([]);
  const [loading, setLoading] = useState(true);
  const [lastUpdated, setLastUpdated] = useState(null);
  const scrollRef = useRef(null);
  const headers = {};

  const fetchFeed = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/nexus/awareness-feed?limit=20`, { headers });
      if (res.ok) {
        const data = await res.json();
        setFeed(data);
        setLastUpdated(new Date());
      }
    } catch (_) {}
    setLoading(false);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    fetchFeed();
    const interval = setInterval(fetchFeed, 10000);
    return () => clearInterval(interval);
  }, [fetchFeed]);

  // Auto-scroll to top (latest) on new data
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = 0;
    }
  }, [feed]);

  return (
    <div className="bg-zinc-900/50 border border-zinc-800/50 rounded-xl overflow-hidden">
      {/* Header */}
      <div className="flex items-center gap-2 px-4 py-2.5 border-b border-zinc-800/50 bg-zinc-900/80">
        <Radio className="w-3.5 h-3.5 text-orange-400 animate-pulse" />
        <span className="text-xs font-bold uppercase tracking-wider text-orange-400">
          NEXUS Live Feed
        </span>
        <div className="flex items-center gap-3 ml-auto">
          {lastUpdated && (
            <span className="text-[10px] text-zinc-600 font-mono">
              {lastUpdated.toLocaleTimeString()}
            </span>
          )}
          <button
            onClick={fetchFeed}
            className="p-1 rounded hover:bg-zinc-700/50 text-zinc-500 hover:text-white transition-colors"
          >
            <RefreshCw className={`w-3 h-3 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Legend */}
      <div className="flex items-center gap-4 px-4 py-2 bg-zinc-950/50 border-b border-zinc-800/30">
        {Object.entries(TYPE_CONFIG).map(([type, cfg]) => (
          <div key={type} className="flex items-center gap-1.5">
            <div className={`w-1.5 h-1.5 rounded-full ${cfg.dot}`} />
            <span className={`text-[10px] font-mono font-semibold ${cfg.color}`}>{type}</span>
          </div>
        ))}
        <span className="text-[10px] text-zinc-600 ml-auto">Refreshes every 10s</span>
      </div>

      {/* Feed */}
      <div
        ref={scrollRef}
        className="p-3 overflow-y-auto font-mono"
        style={{ height: '320px', background: '#0a0a0a' }}
      >
        {loading && feed.length === 0 ? (
          <div className="flex items-center justify-center h-full text-zinc-600 text-xs gap-2">
            <RefreshCw className="w-3 h-3 animate-spin" />
            Loading awareness feed...
          </div>
        ) : feed.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-zinc-600 text-xs gap-2">
            <Radio className="w-6 h-6 opacity-30" />
            <p>No awareness events yet</p>
            <p className="text-zinc-700">NEXUS will populate this as it runs</p>
          </div>
        ) : (
          feed.map((entry, i) => (
            <FeedEntry key={`${entry.type}-${entry.timestamp}-${i}`} entry={entry} />
          ))
        )}
      </div>
    </div>
  );
}
