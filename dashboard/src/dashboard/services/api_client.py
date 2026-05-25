from typing import Any, Optional

import httpx

from dashboard.config import settings


class APIClient:
    """HTTP client for the LegalAI REST API.

    All methods include the JWT token in the ``token`` query parameter as
    expected by the API.  A single instance should be created per request
    or per NiceGUI page to avoid sharing connection state.

    Args:
        token: JWT access token for an authenticated legal professional.
            Pass ``None`` for unauthenticated requests (login).
    """

    def __init__(self, token: Optional[str] = None) -> None:
        self._token = token
        self._base = settings.api_url

    async def login(self, email: str, password: str) -> dict:
        """Authenticate and return the token response dict.

        Args:
            email: Legal professional's email.
            password: Plain-text password.

        Returns:
            The decoded JSON from ``POST /auth/login``.

        Raises:
            httpx.HTTPStatusError: On non-2xx response.
        """
        async with httpx.AsyncClient(base_url=self._base) as client:
            resp = await client.post(
                "/auth/login",
                json={"email": email, "password": password},
            )
            resp.raise_for_status()
            return resp.json()

    async def get_cases(
        self,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        sort_by: str = "created_at",
        sort_dir: str = "desc",
        page: int = 1,
        page_size: int = 50,
    ) -> dict:
        """Fetch a paginated list of cases from the API.

        Args:
            status: Filter by case status (e.g. ``"PENDING"``).
            priority: Filter by priority (e.g. ``"HIGH"``).
            sort_by: Column name to sort by.
            sort_dir: ``"asc"`` or ``"desc"``.
            page: 1-based page number.
            page_size: Results per page.

        Returns:
            The decoded JSON with ``items`` and ``total`` keys.

        Raises:
            httpx.HTTPStatusError: On non-2xx response.
        """
        params: dict[str, Any] = {
            "token": self._token,
            "sort_by": sort_by,
            "sort_dir": sort_dir,
            "page": page,
            "page_size": page_size,
        }
        if status:
            params["status"] = status
        if priority:
            params["priority"] = priority

        async with httpx.AsyncClient(base_url=self._base) as client:
            resp = await client.get("/cases", params=params)
            resp.raise_for_status()
            return resp.json()

    async def accept_case(self, case_id: int, note: Optional[str] = None) -> dict:
        """Accept a case.

        Args:
            case_id: Database primary key of the case to accept.
            note: Optional note to include in the client notification.

        Returns:
            The updated case dict.
        """
        async with httpx.AsyncClient(base_url=self._base) as client:
            resp = await client.post(
                f"/cases/{case_id}/accept",
                json={"note": note},
                params={"token": self._token},
            )
            resp.raise_for_status()
            return resp.json()

    async def reject_case(self, case_id: int, reason: str) -> dict:
        """Reject a case with a stated reason.

        Args:
            case_id: Database primary key of the case to reject.
            reason: Mandatory rejection reason forwarded to the client.

        Returns:
            The updated case dict.
        """
        async with httpx.AsyncClient(base_url=self._base) as client:
            resp = await client.post(
                f"/cases/{case_id}/reject",
                json={"reason": reason},
                params={"token": self._token},
            )
            resp.raise_for_status()
            return resp.json()

    async def request_more_info(self, case_id: int, message: str) -> dict:
        """Send an information request to the client.

        Args:
            case_id: Database primary key of the case.
            message: The question or clarification request text.

        Returns:
            The updated case dict.
        """
        async with httpx.AsyncClient(base_url=self._base) as client:
            resp = await client.post(
                f"/cases/{case_id}/request-info",
                json={"message": message},
                params={"token": self._token},
            )
            resp.raise_for_status()
            return resp.json()

    async def patch_case(
        self,
        case_id: int,
        title: Optional[str] = None,
        description: Optional[str] = None,
        priority: Optional[str] = None,
    ) -> dict:
        """Update editable fields of a case.

        Args:
            case_id: Database primary key.
            title: New title, or ``None`` to leave unchanged.
            description: New description, or ``None`` to leave unchanged.
            priority: New priority string (``"HIGH"``/``"MEDIUM"``/``"LOW"``),
                or ``None`` to leave unchanged.

        Returns:
            The updated case dict.
        """
        payload = {
            k: v
            for k, v in {"title": title, "description": description, "priority": priority}.items()
            if v is not None
        }
        async with httpx.AsyncClient(base_url=self._base) as client:
            resp = await client.patch(
                f"/cases/{case_id}",
                json=payload,
                params={"token": self._token},
            )
            resp.raise_for_status()
            return resp.json()

    async def delete_case(self, case_id: int) -> None:
        """Permanently delete a case.

        Args:
            case_id: Database primary key of the case to delete.
        """
        async with httpx.AsyncClient(base_url=self._base) as client:
            resp = await client.delete(
                f"/cases/{case_id}",
                params={"token": self._token},
            )
            resp.raise_for_status()

    def document_download_url(self, case_id: int, doc_index: int = 0) -> str:
        """Build the URL for downloading a specific case document.

        Args:
            case_id: Database primary key of the case.
            doc_index: Zero-based index of the document (default ``0``).

        Returns:
            The full download URL including the auth token query parameter.
        """
        return f"{self._base}/cases/{case_id}/document?doc_index={doc_index}&token={self._token}"
