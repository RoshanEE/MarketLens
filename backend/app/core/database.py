"""
Database setup: async SQLAlchemy engine for direct Postgres queries
and the Supabase client for auth/storage operations.
"""

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from supabase import create_client, Client
from app.core.config import get_settings

settings = get_settings()

# Async SQLAlchemy engine for Postgres
engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    """FastAPI dependency that provides a DB session per request."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


def get_supabase_client() -> Client:
    """Admin Supabase client (service role) for server-side operations."""
    return create_client(settings.supabase_url, settings.supabase_service_role_key)
