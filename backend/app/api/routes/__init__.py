from app.api.routes.auth import router as auth_router
from app.api.routes.health import router as health_router
from app.api.routes.products import router as products_router
from app.api.routes.customers import router as customers_router
from app.api.routes.portal import router as portal_router
from app.api.routes.negotiations import router as negotiations_router
from app.api.routes.deal_health import router as deal_health_router
from app.api.routes.reports import router as reports_router

__all__ = [
    "auth_router",
    "health_router",
    "products_router",
    "customers_router",
    "portal_router",
    "negotiations_router",
    "deal_health_router",
    "reports_router",
]
