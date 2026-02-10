# Routes package
from .derivatives import router as derivatives_router
from .freewill import router as freewill_router
from .intelligence import router as intelligence_router
from .smc import router as smc_router
from .memory import router as memory_router
from .strategies import router as strategies_router
from .alerts import router as alerts_router

__all__ = [
    "derivatives_router",
    "freewill_router", 
    "intelligence_router",
    "smc_router",
    "memory_router",
    "strategies_router",
    "alerts_router"
]
