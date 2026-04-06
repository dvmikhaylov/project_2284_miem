
from .catalog import router as catalog_router
from .dashboard import router as dashboard_router
from .documents import router as documents_router

__all__ = ["catalog_router", "dashboard_router", "documents_router"]
