# Routes package
from .derivatives import router as derivatives_router
from .freewill import router as freewill_router
from .intelligence import router as intelligence_router
from .smc import router as smc_router
from .memory import router as memory_router
from .strategies import router as strategies_router
from .alerts import router as alerts_router
from .market import router as market_router
from .trading import router as trading_router
from .analysis import router as analysis_router
# New modular routes
from .calculators import router as calculators_router
from .advanced import router as advanced_router
from .orderflow import router as orderflow_router
from .options import router as options_router
from .backtest import router as backtest_router
from .coinglass import router as coinglass_router
from .dual import router as dual_router
from .data import router as data_router
from .sentiment import router as sentiment_router
from .strategy_health import router as strategy_health_router
from .voice import router as voice_router
from .user import router as user_router

__all__ = [
    "derivatives_router",
    "freewill_router",
    "intelligence_router",
    "smc_router",
    "memory_router",
    "strategies_router",
    "alerts_router",
    "market_router",
    "trading_router",
    "analysis_router",
    # New modular routes
    "calculators_router",
    "advanced_router",
    "orderflow_router",
    "options_router",
    "backtest_router",
    "coinglass_router",
    "dual_router",
    "data_router",
    "sentiment_router",
    "strategy_health_router",
    "voice_router",
    "user_router",
]
