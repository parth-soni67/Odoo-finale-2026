from app.api.routes.auth import router as auth_router
from app.api.routes.health import router as health_router
from app.api.routes.quotes import router as quotes_router
from app.api.routes.catalog import router as catalog_router

__all__ = ["auth_router", "health_router", "quotes_router", "catalog_router"]
