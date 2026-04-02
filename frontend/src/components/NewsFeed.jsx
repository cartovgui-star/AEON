import React, { useState, useEffect, useCallback } from 'react';
import { Newspaper, RefreshCw, TrendingUp, TrendingDown, Minus, Globe, Loader2, AlertTriangle } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';

const API_URL = process.env.REACT_APP_BACKEND_URL;

function SentimentBadge({ score }) {
  if (score > 0.1)  return <span className="flex items-center gap-1 text-xs text-green-400 bg-green-500/10 px-2 py-0.5 rounded"><TrendingUp className="w-3 h-3" />Bull</span>;
  if (score < -0.1) return <span className="flex items-center gap-1 text-xs text-red-400 bg-red-500/10 px-2 py-0.5 rounded"><TrendingDown className="w-3 h-3" />Bear</span>;
  return <span className="flex items-center gap-1 text-xs text-zinc-400 bg-zinc-700/50 px-2 py-0.5 rounded"><Minus className="w-3 h-3" />Neutral</span>;
}

function NewsItem({ item, idx }) {
  const score = item.sentiment_score ?? item.score ?? 0;
  const source = item.source || item.publisher || '';
  const url    = item.url || item.link || null;
  const ts     = item.published_at || item.timestamp || null;
  const timeStr = ts ? new Date(ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '';
  const coins   = Array.isArray(item.coins) ? item.coins : [];

  return (
    <div className="p-3 bg-zinc-800/40 border border-zinc-700/40 rounded-xl hover:border-zinc-600/60 transition-colors">
      <div className="flex items-start justify-between gap-3 mb-2">
        <div className="flex-1">
          {url ? (
            <a href={url} target="_blank" rel="noopener noreferrer"
              className="text-sm text-zinc-100 hover:text-orange-400 transition-colors leading-snug line-clamp-2">
              {item.title || item.headline || 'Untitled'}
            </a>
          ) : (
            <p className="text-sm text-zinc-100 leading-snug line-clamp-2">
              {item.title || item.headline || 'Untitled'}
            </p>
          )}
        </div>
        <SentimentBadge score={score} />
      </div>

      <div className="flex items-center gap-3 flex-wrap">
        {source && <span className="text-xs text-zinc-500 flex items-center gap-1"><Globe className="w-3 h-3" />{source}</span>}
        {timeStr && <span className="text-xs text-zinc-600">{timeStr}</span>}
        {coins.map(c => (
          <span key={c} className="text-xs bg-orange-500/10 text-orange-400 border border-orange-500/20 px-1.5 py-0.5 rounded">
            {c}
          </span>
        ))}
      </div>

      {item.summary && (
        <p className="text-xs text-zinc-500 mt-2 leading-relaxed line-clamp-2">{item.summary}</p>
      )}
    </div>
  );
}

function SentimentOverview({ data }) {
  if (!data) return null;
  const bull = data.bullish_pct ?? 0;
  const bear = data.bearish_pct ?? 0;
  const neut = data.neutral_pct ?? Math.max(0, 100 - bull - bear);
  const overall = data.overall_sentiment || data.sentiment || 'N/A';
  const overallColor = overall === 'BULLISH' ? 'text-green-400' : overall === 'BEARISH' ? 'text-red-400' : 'text-yellow-400';

  return (
    <Card className="bg-zinc-900/60 border-zinc-800/50">
      <CardContent className="p-4">
        <div className="flex items-center justify-between mb-3">
          <span className="text-xs text-zinc-500 font-medium uppercase tracking-wider">News Sentiment</span>
          <span className={`text-sm font-bold ${overallColor}`}>{overall}</span>
        </div>
        {/* Bar */}
        <div className="h-2 rounded-full overflow-hidden flex mb-2">
          <div className="bg-green-500 transition-all" style={{ width: `${bull}%` }} />
          <div className="bg-zinc-600 transition-all"  style={{ width: `${neut}%` }} />
          <div className="bg-red-500 transition-all"   style={{ width: `${bear}%` }} />
        </div>
        <div className="flex justify-between text-xs text-zinc-500">
          <span className="text-green-400">{bull.toFixed(0)}% Bullish</span>
          <span>{neut.toFixed(0)}% Neutral</span>
          <span className="text-red-400">{bear.toFixed(0)}% Bearish</span>
        </div>
        {data.total_analyzed != null && (
          <p className="text-xs text-zinc-600 mt-2">{data.total_analyzed} articles analyzed</p>
        )}
      </CardContent>
    </Card>
  );
}

export default function NewsFeed() {
  const [news, setNews]           = useState([]);
  const [sentiment, setSentiment] = useState(null);
  const [loading, setLoading]     = useState(true);
  const [error, setError]         = useState(null);
  const [coin, setCoin]           = useState('');
  const [inputCoin, setInputCoin] = useState('');

  const fetchData = useCallback(async (filterCoin = coin) => {
    setLoading(true);
    setError(null);
    try {
      const coinParam = filterCoin ? `&coin=${filterCoin.toUpperCase()}` : '';
      const [newsRes, sentRes] = await Promise.allSettled([
        fetch(`${API_URL}/api/news/latest?limit=30${coinParam}`).then(r => r.json()),
        fetch(`${API_URL}/api/news/sentiment`).then(r => r.json()),
      ]);

      if (newsRes.status === 'fulfilled') {
        const d = newsRes.value;
        setNews(Array.isArray(d) ? d : (d.news || d.articles || d.items || []));
      } else {
        setError('Failed to load news');
      }
      if (sentRes.status === 'fulfilled') setSentiment(sentRes.value);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [coin]);

  useEffect(() => {
    fetchData();
    const t = setInterval(() => fetchData(), 120000); // refresh every 2 min
    return () => clearInterval(t);
  }, [fetchData]);

  const handleFilter = (e) => {
    e.preventDefault();
    const c = inputCoin.trim().replace('/USDT', '').toUpperCase();
    setCoin(c);
    fetchData(c);
  };

  return (
    <div className="space-y-5 max-w-4xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <Newspaper className="w-6 h-6 text-orange-400" />
            News Feed
          </h1>
          <p className="text-sm text-zinc-500 mt-1">Live crypto news with sentiment analysis</p>
        </div>
        <button onClick={() => fetchData()}
          className="p-2 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-400 hover:text-white transition-colors">
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {/* Sentiment overview */}
      <SentimentOverview data={sentiment} />

      {/* Coin filter */}
      <form onSubmit={handleFilter} className="flex items-center gap-2">
        <input
          type="text"
          value={inputCoin}
          onChange={e => setInputCoin(e.target.value)}
          placeholder="Filter by coin (e.g. BTC)"
          className="flex-1 bg-zinc-800/50 border border-zinc-700/50 rounded-lg px-3 py-2 text-sm text-zinc-200 placeholder-zinc-600 focus:outline-none focus:border-orange-500/50"
        />
        <button type="submit"
          className="px-4 py-2 bg-orange-500/20 hover:bg-orange-500/30 text-orange-400 border border-orange-500/30 rounded-lg text-sm font-medium transition-colors">
          Filter
        </button>
        {coin && (
          <button type="button" onClick={() => { setCoin(''); setInputCoin(''); fetchData(''); }}
            className="px-3 py-2 bg-zinc-800 hover:bg-zinc-700 text-zinc-400 rounded-lg text-sm transition-colors">
            Clear
          </button>
        )}
      </form>

      {/* Error */}
      {error && (
        <div className="flex items-center gap-2 p-3 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400 text-sm">
          <AlertTriangle className="w-4 h-4 flex-shrink-0" />
          {error}
        </div>
      )}

      {/* News list */}
      {loading ? (
        <div className="flex items-center justify-center py-16">
          <Loader2 className="w-7 h-7 text-orange-400 animate-spin" />
        </div>
      ) : news.length === 0 ? (
        <div className="text-center py-16 text-zinc-500">
          <Newspaper className="w-12 h-12 mx-auto mb-3 opacity-30" />
          <p className="text-sm">No news articles found</p>
          {coin && <p className="text-xs mt-1">Try clearing the coin filter</p>}
        </div>
      ) : (
        <div className="space-y-2">
          {news.map((item, idx) => <NewsItem key={item.id || idx} item={item} idx={idx} />)}
        </div>
      )}
    </div>
  );
}
