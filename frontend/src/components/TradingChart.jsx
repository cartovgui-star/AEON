import React, { useEffect, useRef, useState, useCallback } from 'react';
import * as LightweightCharts from 'lightweight-charts';
import { 
  TrendingUp, TrendingDown, Activity, RefreshCw,
  ZoomIn, ZoomOut, Maximize2, ChevronDown
} from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL;

// Timeframe options
const TIMEFRAMES = [
  { value: '5m', label: '5m' },
  { value: '15m', label: '15m' },
  { value: '1h', label: '1H' },
  { value: '4h', label: '4H' },
  { value: '1d', label: '1D' },
];

// Symbol options
const SYMBOLS = [
  'BTC', 'ETH', 'SOL', 'BNB', 'XRP', 'DOGE', 'ADA', 
  'AVAX', 'LINK', 'DOT', 'ATOM', 'UNI', 'LTC', 'ARB', 'OP'
];

const TradingChart = ({ 
  symbol: initialSymbol = 'BTC', 
  trades = [], 
  positions = [],
  height = 500,
  showControls = true,
  onSymbolChange = null
}) => {
  const chartContainerRef = useRef(null);
  const chartRef = useRef(null);
  const candleSeriesRef = useRef(null);
  const volumeSeriesRef = useRef(null);
  
  const [symbol, setSymbol] = useState(initialSymbol);
  const [timeframe, setTimeframe] = useState('4h');
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [currentPrice, setCurrentPrice] = useState(null);
  const [priceChange, setPriceChange] = useState(0);
  const [showSymbolDropdown, setShowSymbolDropdown] = useState(false);
  const [showTimeframeDropdown, setShowTimeframeDropdown] = useState(false);

  // Initialize chart
  useEffect(() => {
    if (!chartContainerRef.current) return;

    const chart = LightweightCharts.createChart(chartContainerRef.current, {
      width: chartContainerRef.current.clientWidth,
      height: height,
      layout: {
        background: { type: 'solid', color: 'transparent' },
        textColor: '#9ca3af',
      },
      grid: {
        vertLines: { color: 'rgba(42, 46, 57, 0.5)' },
        horzLines: { color: 'rgba(42, 46, 57, 0.5)' },
      },
      crosshair: {
        mode: LightweightCharts.CrosshairMode.Normal,
        vertLine: {
          color: 'rgba(224, 227, 235, 0.3)',
          labelBackgroundColor: '#2962FF',
        },
        horzLine: {
          color: 'rgba(224, 227, 235, 0.3)',
          labelBackgroundColor: '#2962FF',
        },
      },
      rightPriceScale: {
        borderColor: 'rgba(42, 46, 57, 0.8)',
        scaleMargins: { top: 0.1, bottom: 0.2 },
      },
      timeScale: {
        borderColor: 'rgba(42, 46, 57, 0.8)',
        timeVisible: true,
        secondsVisible: false,
      },
      handleScroll: { vertTouchDrag: true },
      handleScale: { axisPressedMouseMove: true },
    });

    // Add candlestick series - v5 API
    const candleSeries = chart.addSeries(LightweightCharts.CandlestickSeries, {
      upColor: '#22c55e',
      downColor: '#ef4444',
      borderUpColor: '#22c55e',
      borderDownColor: '#ef4444',
      wickUpColor: '#22c55e',
      wickDownColor: '#ef4444',
    });

    // Add volume series - v5 API
    const volumeSeries = chart.addSeries(LightweightCharts.HistogramSeries, {
      color: '#26a69a',
      priceFormat: { type: 'volume' },
      priceScaleId: '',
    });
    
    // Set scale margins for volume
    volumeSeries.priceScale().applyOptions({
      scaleMargins: { top: 0.85, bottom: 0 },
    });

    chartRef.current = chart;
    candleSeriesRef.current = candleSeries;
    volumeSeriesRef.current = volumeSeries;

    // Handle resize
    const handleResize = () => {
      if (chartContainerRef.current) {
        chart.applyOptions({ width: chartContainerRef.current.clientWidth });
      }
    };

    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      chart.remove();
    };
  }, [height]);

  // Fetch and update data
  const fetchChartData = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      // Fetch OHLCV data from MEXC
      const response = await fetch(`${API_URL}/api/mexc/ohlcv/${symbol}?timeframe=${timeframe}&limit=200`);
      
      if (!response.ok) {
        throw new Error('Failed to fetch chart data');
      }

      const data = await response.json();
      
      if (!data.candles || data.candles.length === 0) {
        throw new Error('No chart data available');
      }

      // Format candle data for lightweight-charts
      const candleData = data.candles.map(candle => ({
        time: Math.floor(candle.timestamp / 1000),
        open: candle.open,
        high: candle.high,
        low: candle.low,
        close: candle.close,
      }));

      // Format volume data
      const volumeData = data.candles.map(candle => ({
        time: Math.floor(candle.timestamp / 1000),
        value: candle.volume,
        color: candle.close >= candle.open ? 'rgba(34, 197, 94, 0.4)' : 'rgba(239, 68, 68, 0.4)',
      }));

      // Update chart series
      if (candleSeriesRef.current && volumeSeriesRef.current) {
        candleSeriesRef.current.setData(candleData);
        volumeSeriesRef.current.setData(volumeData);

        // Set current price and change
        const lastCandle = candleData[candleData.length - 1];
        const firstCandle = candleData[0];
        if (lastCandle && firstCandle) {
          setCurrentPrice(lastCandle.close);
          const change = ((lastCandle.close - firstCandle.open) / firstCandle.open) * 100;
          setPriceChange(change);
        }

        // Add trade markers
        addTradeMarkers(candleData);
        
        // Add position levels
        addPositionLevels();

        // Fit content
        chartRef.current?.timeScale().fitContent();
      }

    } catch (err) {
      console.error('Chart data error:', err);
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  }, [symbol, timeframe]);

  // Add trade entry/exit markers
  const addTradeMarkers = useCallback((candleData) => {
    if (!candleSeriesRef.current || !trades || trades.length === 0) return;

    const markers = [];
    
    trades.forEach(trade => {
      // Entry marker
      if (trade.entry_time) {
        const entryTime = Math.floor(new Date(trade.entry_time).getTime() / 1000);
        const isLong = trade.direction === 'LONG';
        
        markers.push({
          time: entryTime,
          position: isLong ? 'belowBar' : 'aboveBar',
          color: isLong ? '#22c55e' : '#ef4444',
          shape: isLong ? 'arrowUp' : 'arrowDown',
          text: `${isLong ? 'BUY' : 'SELL'} @ $${trade.entry_price?.toLocaleString()}`,
        });
      }

      // Exit marker
      if (trade.exit_time && trade.exit_price) {
        const exitTime = Math.floor(new Date(trade.exit_time).getTime() / 1000);
        const isWin = (trade.pnl_pct || 0) >= 0;
        
        markers.push({
          time: exitTime,
          position: 'inBar',
          color: isWin ? '#22c55e' : '#ef4444',
          shape: 'circle',
          text: `EXIT ${isWin ? '+' : ''}${trade.pnl_pct?.toFixed(2)}%`,
        });
      }
    });

    // Sort markers by time
    markers.sort((a, b) => a.time - b.time);
    
    if (markers.length > 0) {
      candleSeriesRef.current.setMarkers(markers);
    }
  }, [trades]);

  // Add position entry/SL/TP lines
  const addPositionLevels = useCallback(() => {
    if (!candleSeriesRef.current || !positions || positions.length === 0) return;

    // Remove existing price lines
    const series = candleSeriesRef.current;
    
    positions.forEach(pos => {
      const isLong = pos.direction === 'LONG';
      
      // Entry price line
      if (pos.entry_price) {
        series.createPriceLine({
          price: pos.entry_price,
          color: '#3b82f6',
          lineWidth: 2,
          lineStyle: LineStyle.Solid,
          axisLabelVisible: true,
          title: `Entry ${pos.symbol?.replace('/USDT', '')}`,
        });
      }

      // Stop loss line
      if (pos.stop_price) {
        series.createPriceLine({
          price: pos.stop_price,
          color: '#ef4444',
          lineWidth: 1,
          lineStyle: LineStyle.Dashed,
          axisLabelVisible: true,
          title: 'SL',
        });
      }

      // Take profit line
      if (pos.target_price) {
        series.createPriceLine({
          price: pos.target_price,
          color: '#22c55e',
          lineWidth: 1,
          lineStyle: LineStyle.Dashed,
          axisLabelVisible: true,
          title: 'TP',
        });
      }

      // Liquidation price line (if available)
      if (pos.liquidation_price) {
        series.createPriceLine({
          price: pos.liquidation_price,
          color: '#f59e0b',
          lineWidth: 1,
          lineStyle: LineStyle.Dotted,
          axisLabelVisible: true,
          title: 'LIQ',
        });
      }
    });
  }, [positions]);

  // Load data when symbol/timeframe changes
  useEffect(() => {
    fetchChartData();
  }, [fetchChartData]);

  // Handle symbol change
  const handleSymbolChange = (newSymbol) => {
    setSymbol(newSymbol);
    setShowSymbolDropdown(false);
    if (onSymbolChange) onSymbolChange(newSymbol);
  };

  // Handle timeframe change
  const handleTimeframeChange = (newTimeframe) => {
    setTimeframe(newTimeframe);
    setShowTimeframeDropdown(false);
  };

  // Zoom controls
  const handleZoomIn = () => {
    chartRef.current?.timeScale().scrollToPosition(-5, false);
  };

  const handleZoomOut = () => {
    chartRef.current?.timeScale().scrollToPosition(5, false);
  };

  const handleFitContent = () => {
    chartRef.current?.timeScale().fitContent();
  };

  const isPositive = priceChange >= 0;

  return (
    <div className="relative bg-zinc-900/50 rounded-2xl border border-zinc-800/50 overflow-hidden" data-testid="trading-chart">
      {/* Chart Header */}
      {showControls && (
        <div className="flex items-center justify-between p-4 border-b border-zinc-800/50">
          {/* Left side - Symbol & Price */}
          <div className="flex items-center gap-4">
            {/* Symbol selector */}
            <div className="relative">
              <button
                onClick={() => setShowSymbolDropdown(!showSymbolDropdown)}
                className="flex items-center gap-2 px-3 py-2 bg-zinc-800/50 hover:bg-zinc-700/50 rounded-lg transition-colors"
                data-testid="symbol-selector"
              >
                <span className="text-white font-bold text-lg">{symbol}/USDT</span>
                <ChevronDown className="w-4 h-4 text-zinc-400" />
              </button>
              
              {showSymbolDropdown && (
                <div className="absolute top-full left-0 mt-1 w-40 bg-zinc-800 border border-zinc-700 rounded-lg shadow-xl z-50 max-h-64 overflow-y-auto">
                  {SYMBOLS.map(s => (
                    <button
                      key={s}
                      onClick={() => handleSymbolChange(s)}
                      className={`w-full px-3 py-2 text-left hover:bg-zinc-700/50 transition-colors ${
                        s === symbol ? 'text-blue-400 bg-zinc-700/30' : 'text-zinc-300'
                      }`}
                    >
                      {s}/USDT
                    </button>
                  ))}
                </div>
              )}
            </div>

            {/* Price display */}
            <div className="flex flex-col">
              <span className={`text-2xl font-bold ${isPositive ? 'text-green-400' : 'text-red-400'}`}>
                ${currentPrice?.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: currentPrice > 100 ? 2 : 6 }) || '---'}
              </span>
              <div className={`flex items-center gap-1 text-sm ${isPositive ? 'text-green-400' : 'text-red-400'}`}>
                {isPositive ? (
                  <TrendingUp className="w-4 h-4" />
                ) : (
                  <TrendingDown className="w-4 h-4" />
                )}
                <span>{isPositive ? '+' : ''}{priceChange.toFixed(2)}%</span>
              </div>
            </div>
          </div>

          {/* Right side - Controls */}
          <div className="flex items-center gap-2">
            {/* Timeframe selector */}
            <div className="relative">
              <div className="flex items-center bg-zinc-800/50 rounded-lg p-1">
                {TIMEFRAMES.map(tf => (
                  <button
                    key={tf.value}
                    onClick={() => handleTimeframeChange(tf.value)}
                    className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                      timeframe === tf.value 
                        ? 'bg-blue-500/20 text-blue-400' 
                        : 'text-zinc-400 hover:text-white'
                    }`}
                    data-testid={`tf-${tf.value}`}
                  >
                    {tf.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Chart controls */}
            <div className="flex items-center gap-1 bg-zinc-800/50 rounded-lg p-1">
              <button
                onClick={handleZoomIn}
                className="p-2 text-zinc-400 hover:text-white hover:bg-zinc-700/50 rounded-md transition-colors"
                title="Zoom In"
              >
                <ZoomIn className="w-4 h-4" />
              </button>
              <button
                onClick={handleZoomOut}
                className="p-2 text-zinc-400 hover:text-white hover:bg-zinc-700/50 rounded-md transition-colors"
                title="Zoom Out"
              >
                <ZoomOut className="w-4 h-4" />
              </button>
              <button
                onClick={handleFitContent}
                className="p-2 text-zinc-400 hover:text-white hover:bg-zinc-700/50 rounded-md transition-colors"
                title="Fit to Screen"
              >
                <Maximize2 className="w-4 h-4" />
              </button>
            </div>

            {/* Refresh button */}
            <button
              onClick={fetchChartData}
              disabled={isLoading}
              className="p-2 text-zinc-400 hover:text-white bg-zinc-800/50 hover:bg-zinc-700/50 rounded-lg transition-colors"
              title="Refresh"
            >
              <RefreshCw className={`w-5 h-5 ${isLoading ? 'animate-spin' : ''}`} />
            </button>
          </div>
        </div>
      )}

      {/* Chart Container */}
      <div className="relative">
        {/* Loading overlay */}
        {isLoading && (
          <div className="absolute inset-0 bg-zinc-900/80 flex items-center justify-center z-10">
            <div className="flex items-center gap-3">
              <Activity className="w-6 h-6 text-blue-400 animate-pulse" />
              <span className="text-zinc-400">Loading chart data...</span>
            </div>
          </div>
        )}

        {/* Error overlay */}
        {error && (
          <div className="absolute inset-0 bg-zinc-900/80 flex items-center justify-center z-10">
            <div className="text-center">
              <p className="text-red-400 mb-2">{error}</p>
              <button
                onClick={fetchChartData}
                className="px-4 py-2 bg-blue-500/20 text-blue-400 rounded-lg hover:bg-blue-500/30 transition-colors"
              >
                Retry
              </button>
            </div>
          </div>
        )}

        {/* Chart */}
        <div ref={chartContainerRef} className="w-full" style={{ height: `${height}px` }} />
      </div>

      {/* Position/Trade Legend */}
      {(positions?.length > 0 || trades?.length > 0) && (
        <div className="flex items-center gap-4 p-3 border-t border-zinc-800/50 text-xs">
          <div className="flex items-center gap-2">
            <div className="w-3 h-0.5 bg-blue-500"></div>
            <span className="text-zinc-400">Entry</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-0.5 bg-green-500 border-dashed"></div>
            <span className="text-zinc-400">Take Profit</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-0.5 bg-red-500 border-dashed"></div>
            <span className="text-zinc-400">Stop Loss</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-0.5 bg-amber-500 border-dotted"></div>
            <span className="text-zinc-400">Liquidation</span>
          </div>
        </div>
      )}
    </div>
  );
};

export default TradingChart;
