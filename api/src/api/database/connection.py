from typing import AsyncGenerator

import bcrypt
from sqlalchemy import text
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


async def add_missing_columns() -> None:
    """Add new columns to existing tables without a full schema migration.

    Safe to run on every startup: each ALTER TABLE is ignored if the column
    already exists.
    """
    new_columns = [
        "ALTER TABLE cases ADD COLUMN documents_json TEXT",
        "ALTER TABLE conversations ADD COLUMN linked_case_id INTEGER",
    ]
    async with _engine.begin() as conn:
        for stmt in new_columns:
            try:
                await conn.execute(text(stmt))
            except Exception:
                pass


async def seed_initial_data() -> None:
    """Insert default legal-professional accounts when they don't exist yet.

    Primary account uses ``SEED_EMAIL`` / ``SEED_PASSWORD`` / ``SEED_NAME``
    from settings.  The MVP tester account is hardcoded and idempotent.
    """
    from sqlmodel import select

    _SEED_USERS = [
        (settings.seed_email, settings.seed_password, settings.seed_name),
        ("occhiutolegal@legalai.com", "occhiutolegal2024", "Occhiuto Legal"),
    ]

    async with AsyncSession(_engine) as session:
        for email, password, name in _SEED_USERS:
            result = await session.exec(select(LegalUser).where(LegalUser.email == email))
            if result.first() is not None:
                continue
            user = LegalUser(
                email=email,
                hashed_password=bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode(),
                name=name,
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
