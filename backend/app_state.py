"""
Shared application state and dependencies.
All route modules import from here to avoid circular imports.
"""
from typing import Dict, Any, Set
from datetime import datetime

# These will be set by server.py during initialization
db = None
chat_ids: Set[int] = set()
mexc = None
autonomous_trader = None
autonomous_trader_v2 = None
free_will_v2 = None
dual_engine = None
learning_system = None
market_intel = None
enhanced_intel = None
derivatives_intel = None
news_intel = None
futures_calc = None
mtf_analysis = None
advanced_strategies = None
order_flow = None
options_analyzer = None
backtest_engine = None
coinglass_intel = None
strategy_engine = None
price_alert_system = None
sentiment_analyzer = None
arbitrage_detector = None
strategy_health = None
user_profiler = None
confluence_analyzer = None
ws_manager = None
aeon_mind = None
self_healer = None
vwap_scalper = None  # VWAP + EMA Cross + RSI Scalper
vp_engine = None     # Hyper Accuracy Engine (VP + Liq Heatmap + Orderbook + BTC Gate)
quant_analyzer = None  # Quant Analyzer Engine - pure multi-factor technical scoring
analytics_engine = None  # Performance Analytics Engine
regime_engine = None     # Market Regime Detection Engine
yolo_engine = None   # YOLO Engine - independent aggressive trading
continuous_learner = None  # Continuous Learning Engine
paper_trading = None  # Paper Trading System
engine_manager = None  # Unified Engine Manager - 7 engines
tcn_engine = None     # TCN Neural Engine (engine 9) — deep learning, BTC/USDT 1h

# Telegram helpers
send_telegram_message = None
get_user_settings = None
update_user_settings = None
get_user_probe_state = None
update_probe_state = None
store_user_insight = None
get_user_insights = None

# Persona prompts
AEON_DEFAULT_SYSTEM = ""
ALCHEMY_MODE_SYSTEM = ""
TRADING_ANALYSIS_SYSTEM = ""
build_system_prompt = None
build_user_prompt = None

# Background task helpers
generate_trade_analysis = None
freewill_market_scan = None
freewill_proactive = None
send_daily_report = None

# Trade outcome tracker
trade_outcome_tracker = None

# Other
last_market_alert: Dict[int, datetime] = {}
last_freewill_message: Dict[int, datetime] = {}
daily_reports_sent: Dict[str, list] = {}
stock_reports_sent: Dict[str, list] = {}
