from pydantic import BaseModel


class LoginRequest(BaseModel):
    """Payload for the ``/auth/login`` endpoint.

    Attributes:
        email: Legal professional's registered email address.
        password: Plain-text password (transmitted over TLS, never stored).
    """

    email: str
    password: str


class TokenResponse(BaseModel):
    """JWT token returned after successful authentication.

    Attributes:
        access_token: Signed JWT bearer token.
        token_type: Always ``"bearer"`` per OAuth 2.0 convention.
        name: Display name of the authenticated user.
    """

    access_token: str
    token_type: str = "bearer"
    name: str


class UserResponse(BaseModel):
    """Public representation of a legal-professional account.

    Attributes:
        id: Database primary key.
        email: Registered email address.
        name: Display name.
        is_active: Whether the account is currently enabled.
    """

    id: int
    email: str
    name: str
    is_active: bool
