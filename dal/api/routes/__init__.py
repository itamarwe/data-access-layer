from .catalog import router as catalog_router
from .curation import router as curation_router
from .system import router as system_router

__all__ = ("catalog_router", "curation_router", "system_router")
