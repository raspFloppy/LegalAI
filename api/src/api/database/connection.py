from typing import AsyncGenerator

from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from api.config import settings
from api.database.models import LegalUser

_engine = create_async_engine(
    settings.database_url,
    echo=False,
    connect_args={"check_same_thread": False},
)

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


async def create_db_and_tables() -> None:
    """Create all SQLModel tables if they do not already exist."""
    async with _engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)


async def seed_initial_data() -> None:
    """Insert the default legal-professional account when the DB is empty.

    Uses settings ``SEED_EMAIL``, ``SEED_PASSWORD``, and ``SEED_NAME`` so the
    credentials can be overridden via environment variables without touching
    source code.
    """
    async with AsyncSession(_engine) as session:
        from sqlmodel import select

        result = await session.exec(
            select(LegalUser).where(LegalUser.email == settings.seed_email)
        )
        if result.first() is not None:
            return

        user = LegalUser(
            email=settings.seed_email,
            hashed_password=_pwd_context.hash(settings.seed_password),
            name=settings.seed_name,
        )
        session.add(user)
        await session.commit()


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async database session for use as a FastAPI dependency.

    Yields:
        An ``AsyncSession`` that is automatically closed after the request.
    """
    async with AsyncSession(_engine) as session:
        yield session
