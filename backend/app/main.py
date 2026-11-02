from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging, get_logger
from app.db.session import close_db, init_db
from app.api.routes import health, repositories, indexing, chat, security

logger = get_logger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    configure_logging()
    logger.info("starting_application", app_name=settings.app_name, env=settings.app_env)
    await init_db()
    logger.info("database_initialized")

    yield

    # Shutdown
    logger.info("shutting_down_application")
    await close_db()


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.is_development else None,
    redoc_url="/redoc" if settings.is_development else None,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Exception handlers
register_exception_handlers(app)

# API routes
app.include_router(health.router, prefix=settings.api_prefix, tags=["health"])
app.include_router(repositories.router, prefix=f"{settings.api_prefix}/repositories", tags=["repositories"])
app.include_router(indexing.router, prefix=settings.api_prefix, tags=["indexing"])
app.include_router(chat.router, prefix=f"{settings.api_prefix}/repositories", tags=["chat"])
app.include_router(security.router, prefix=f"{settings.api_prefix}/repositories", tags=["security"])


@app.get("/")
async def root():
    return {
        "name": settings.app_name,
        "version": "0.1.0",
        "docs": "/docs",
        "health": f"{settings.api_prefix}/health",
    }