"""
MarketLens FastAPI application entry point.
Sets up CORS, mounts all routers, and handles lifespan events (DB init).
"""

import asyncio
import structlog
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.database import engine, Base
from app.api.routes import health, auth, research
from app.services.timeout_watcher import watch_for_stuck_runs

log = structlog.get_logger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables on startup (idempotent — skipped if already exist)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    log.info("startup.db_ready")

    watcher = asyncio.create_task(watch_for_stuck_runs())

    yield

    watcher.cancel()
    await engine.dispose()
    log.info("shutdown.db_closed")


app = FastAPI(
    title="MarketLens API",
    description="Market Research Intelligence Assistant backend",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount routers
app.include_router(health.router)
app.include_router(auth.router, prefix="/api")
app.include_router(research.router, prefix="/api/research")
