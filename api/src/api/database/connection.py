from typing import AsyncGenerator

import bcrypt
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
            hashed_password=bcrypt.hashpw(
                settings.seed_password.encode(), bcrypt.gensalt()
            ).decode(),
            name=settings.seed_name,
        )
        session.add(user)
        await session.commit()


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async database session for use as a FastAPI dependency.

    ``expire_on_commit=False`` prevents SQLAlchemy from expiring ORM objects
    after each ``commit()``, which would trigger synchronous lazy-loads that
    cannot run inside an async context.

    Yields:
        An ``AsyncSession`` that is automatically closed after the request.
    """
    async with AsyncSession(_engine, expire_on_commit=False) as session:
        yield session
