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
]
