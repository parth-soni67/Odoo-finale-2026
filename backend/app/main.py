from fastapi import FastAPI, Request, status
import os
from fastapi.responses import JSONResponse, FileResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.routes.health import router as health_router
from app.api.routes.auth import router as auth_router
from app.api.routes.quotes import router as quotes_router
from app.api.routes.catalog import router as catalog_router
from app.api.routes.orders import router as orders_router
from app.api.routes.products import router as products_router
from app.api.routes.customers import router as customers_router
from app.api.routes.portal import router as portal_router
from app.api.routes.negotiations import router as negotiations_router
from app.api.routes.deal_health import router as deal_health_router
from app.api.routes.reports import router as reports_router

from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.core.database import Base, engine
    import app.models  # noqa: F401
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="DealFlow360 — Intelligent, Self-Governing Sales Operations Platform API",
    openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
    docs_url=f"{settings.API_V1_PREFIX}/docs",
    redoc_url=f"{settings.API_V1_PREFIX}/redoc",
    lifespan=lifespan,
)

# CORS configuration
if settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.BACKEND_CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


# Standardized Error Handling
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    if isinstance(exc.detail, dict) and "code" in exc.detail:
        error_body = exc.detail
    else:
        error_body = {
            "code": f"HTTP_{exc.status_code}",
            "message": str(exc.detail)
        }
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": error_body},
        headers=getattr(exc, "headers", None)
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Input validation failed",
                "details": exc.errors()
            }
        }
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected internal server error occurred"
            }
        }
    )


# Routers
app.include_router(health_router, prefix=settings.API_V1_PREFIX)
app.include_router(auth_router, prefix=settings.API_V1_PREFIX)
app.include_router(products_router, prefix=settings.API_V1_PREFIX)
app.include_router(customers_router, prefix=settings.API_V1_PREFIX)
app.include_router(quotes_router, prefix=settings.API_V1_PREFIX)
app.include_router(orders_router, prefix=settings.API_V1_PREFIX)
app.include_router(catalog_router, prefix=settings.API_V1_PREFIX)
app.include_router(portal_router, prefix=settings.API_V1_PREFIX)
app.include_router(negotiations_router, prefix=settings.API_V1_PREFIX)
app.include_router(deal_health_router, prefix=settings.API_V1_PREFIX)
app.include_router(reports_router, prefix=settings.API_V1_PREFIX)


@app.get("/demo")
def demo_ui():
    demo_file = os.path.join(os.path.dirname(__file__), "static", "demo.html")
    return FileResponse(demo_file, media_type="text/html")


frontend_dist = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist"))
if os.path.isdir(frontend_dist):
    from fastapi.staticfiles import StaticFiles
    assets_dir = os.path.join(frontend_dist, "assets")
    if os.path.isdir(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="spa_assets")

    @app.get("/register")
    @app.get("/signup")
    @app.get("/login")
    @app.get("/portal")
    @app.get("/my-quotes")
    @app.get("/orders")
    @app.get("/billing")
    @app.get("/company")
    @app.get("/account")
    @app.get("/quotations")
    @app.get("/products")
    @app.get("/customers")
    @app.get("/approvals")
    @app.get("/deal-health")
    @app.get("/admin")
    @app.get("/operations")
    @app.get("/finance")
    @app.get("/negotiations")
    @app.get("/reports")
    def serve_spa():
        index_file = os.path.join(frontend_dist, "index.html")
        if os.path.isfile(index_file):
            return FileResponse(index_file, media_type="text/html")
        return FileResponse(os.path.join(os.path.dirname(__file__), "static", "demo.html"), media_type="text/html")


@app.get("/")
def root():
    return {
        "name": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "docs": f"{settings.API_V1_PREFIX}/docs",
        "health": f"{settings.API_V1_PREFIX}/health",
        "demo": "/demo"
    }
