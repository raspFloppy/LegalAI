from datetime import datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from jose import jwt
from passlib.context import CryptContext
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from api.config import settings
from api.database.connection import get_session
from api.database.models import LegalUser
from api.schemas.auth import LoginRequest, TokenResponse, UserResponse

router = APIRouter()

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def create_access_token(subject: str) -> str:
    """Create a signed JWT access token.

    Args:
        subject: The value to embed as the JWT ``sub`` claim (typically the
            user's email address).

    Returns:
        A signed JWT string.
    """
    expire = datetime.utcnow() + timedelta(
        minutes=settings.access_token_expire_minutes
    )
    return jwt.encode(
        {"sub": subject, "exp": expire},
        settings.secret_key,
        algorithm=settings.algorithm,
    )


async def get_current_user(
    token: str,
    session: AsyncSession,
) -> LegalUser:
    """Validate a JWT and return the corresponding legal-professional record.

    Args:
        token: Raw JWT string extracted from the ``Authorization`` header.
        session: Active database session.

    Returns:
        The authenticated ``LegalUser`` record.

    Raises:
        HTTPException: 401 if the token is invalid, expired, or the user is
            not found.
    """
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            token, settings.secret_key, algorithms=[settings.algorithm]
        )
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exc
    except Exception:
        raise credentials_exc

    result = await session.exec(
        select(LegalUser).where(LegalUser.email == email)
    )
    user = result.first()
    if user is None or not user.is_active:
        raise credentials_exc
    return user


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> TokenResponse:
    """Authenticate a legal professional and return a JWT.

    Args:
        body: Login credentials (email + password).
        session: Injected database session.

    Returns:
        A ``TokenResponse`` containing the JWT and the user's display name.

    Raises:
        HTTPException: 401 when credentials are invalid.
    """
    result = await session.exec(
        select(LegalUser).where(LegalUser.email == body.email)
    )
    user = result.first()

    if user is None or not _pwd_context.verify(body.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    token = create_access_token(user.email)
    return TokenResponse(access_token=token, name=user.name)


@router.get("/me", response_model=UserResponse)
async def get_me(
    token: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> UserResponse:
    """Return the profile of the currently authenticated user.

    Args:
        token: JWT passed as a query parameter (for dashboard convenience).
        session: Injected database session.

    Returns:
        The ``UserResponse`` for the authenticated user.
    """
    user = await get_current_user(token, session)
    return UserResponse(id=user.id, email=user.email, name=user.name, is_active=user.is_active)
