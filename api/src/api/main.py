import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from api.config import settings
from api.database.connection import create_db_and_tables, seed_initial_data
from api.routers import auth, cases, webhook


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle startup and shutdown events.

    On startup: creates all database tables, seeds the default legal-
    professional account, and ensures the upload directory exists.

    Args:
        app: The FastAPI application instance.

    Yields:
        Control to the running application.
    """
    await create_db_and_tables()
    await seed_initial_data()
    os.makedirs(settings.upload_dir, exist_ok=True)
    yield


app = FastAPI(
    title="LegalAI API",
    description=(
        "Backend for the LegalAI case management system. "
        "Handles Telegram webhooks, AI case analysis, and the dashboard REST API."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/uploads", StaticFiles(directory=settings.upload_dir), name="uploads")

app.include_router(auth.router, prefix="/auth", tags=["Authentication"])
app.include_router(cases.router, prefix="/cases", tags=["Cases"])
app.include_router(webhook.router, prefix="/webhook", tags=["Webhooks"])


@app.get("/health", tags=["Health"])
async def health_check() -> dict:
    """Return a simple liveness probe response.

    Returns:
        A dict with ``{"status": "healthy"}``.
    """
    return {"status": "healthy"}
