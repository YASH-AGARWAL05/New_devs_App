from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
import logging

from ..config import settings

logger = logging.getLogger(__name__)


class DatabasePool:
    def __init__(self):
        self.engine = None
        self.session_factory = None

    async def initialize(self):
        """Initialize the async connection pool for the configured database."""
        if self.session_factory:
            return

        try:
            database_url = settings.database_url
            if database_url.startswith("postgres://"):
                database_url = database_url.replace("postgres://", "postgresql+asyncpg://", 1)
            elif database_url.startswith("postgresql://"):
                database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)

            self.engine = create_async_engine(
                database_url,
                pool_size=20,
                max_overflow=30,
                pool_pre_ping=True,
                pool_recycle=3600,
                echo=False,
            )
            self.session_factory = async_sessionmaker(
                bind=self.engine,
                class_=AsyncSession,
                expire_on_commit=False,
            )
            logger.info("Database connection pool initialized")
        except Exception as error:
            logger.error("Database pool initialization failed: %s", error)
            self.engine = None
            self.session_factory = None

    async def close(self):
        """Close the connection pool."""
        if self.engine:
            await self.engine.dispose()

    def get_session(self) -> AsyncSession:
        """Return a session from the initialized pool."""
        if not self.session_factory:
            raise RuntimeError("Database pool not initialized")
        return self.session_factory()


db_pool = DatabasePool()


async def get_db_session() -> AsyncSession:
    """Yield a session from the shared database pool."""
    async with db_pool.get_session() as session:
        yield session
