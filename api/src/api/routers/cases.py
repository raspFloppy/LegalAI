import json
from datetime import datetime
from pathlib import Path
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from api.config import settings
from api.database.connection import get_session
from api.database.models import Case, CasePriority, CaseStatus
from api.routers.auth import get_current_user
from api.schemas.case import (
    AcceptCaseRequest,
    CaseListResponse,
    CaseResponse,
    PatchCaseRequest,
    RejectCaseRequest,
    RequestMoreInfoRequest,
)
from api.services.messaging_service import MessagingService

router = APIRouter()

_messaging = MessagingService()


async def _require_auth(
    token: str,
    session: Annotated[AsyncSession, Depends(get_session)],
):
    """FastAPI dependency that validates the JWT and returns the current user.

    Args:
        token: JWT passed as a query parameter.
        session: Injected database session.

    Returns:
        The authenticated ``LegalUser``.
    """
    return await get_current_user(token, session)


@router.get("", response_model=CaseListResponse)
async def list_cases(
    session: Annotated[AsyncSession, Depends(get_session)],
    token: str = Query(...),
    status_filter: Optional[CaseStatus] = Query(None, alias="status"),
    priority_filter: Optional[CasePriority] = Query(None, alias="priority"),
    sort_by: str = Query("created_at"),
    sort_dir: str = Query("desc"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> CaseListResponse:
    """Return a paginated, filterable list of cases for the dashboard.

    Args:
        session: Injected database session.
        token: JWT for authentication.
        status_filter: Optional status to filter on.
        priority_filter: Optional priority to filter on.
        sort_by: Column name to sort by (``created_at``, ``priority``,
            ``status``, ``username``).
        sort_dir: ``"asc"`` or ``"desc"``.
        page: 1-based page number.
        page_size: Number of results per page (max 100).

    Returns:
        ``CaseListResponse`` with the current page of cases and the total
        count matching the applied filters.
    """
    await _require_auth(token, session)

    query = select(Case)
    if status_filter:
        query = query.where(Case.status == status_filter)
    if priority_filter:
        query = query.where(Case.priority == priority_filter)

    sort_column = {
        "created_at": Case.created_at,
        "updated_at": Case.updated_at,
        "priority": Case.priority,
        "status": Case.status,
        "username": Case.username,
    }.get(sort_by, Case.created_at)

    if sort_dir == "asc":
        query = query.order_by(sort_column.asc())
    else:
        query = query.order_by(sort_column.desc())

    all_results = await session.exec(query)
    all_cases = all_results.all()
    total = len(all_cases)

    offset = (page - 1) * page_size
    page_cases = all_cases[offset : offset + page_size]

    return CaseListResponse(
        items=[CaseResponse.model_validate(c) for c in page_cases],
        total=total,
    )


@router.get("/{case_id}", response_model=CaseResponse)
async def get_case(
    case_id: int,
    token: str = Query(...),
    session: AsyncSession = Depends(get_session),
) -> CaseResponse:
    """Return a single case by ID.

    Args:
        case_id: Database primary key.
        token: JWT for authentication.
        session: Injected database session.

    Returns:
        The ``CaseResponse`` for the requested case.

    Raises:
        HTTPException: 404 when the case does not exist.
    """
    await _require_auth(token, session)
    case = await session.get(Case, case_id)
    if case is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    return CaseResponse.model_validate(case)


@router.patch("/{case_id}", response_model=CaseResponse)
async def patch_case(
    case_id: int,
    body: PatchCaseRequest,
    token: str = Query(...),
    session: AsyncSession = Depends(get_session),
) -> CaseResponse:
    """Update editable fields of a case (title, description, priority).

    Args:
        case_id: Database primary key.
        body: Fields to update; unset fields are left unchanged.
        token: JWT for authentication.
        session: Injected database session.

    Returns:
        The updated ``CaseResponse``.

    Raises:
        HTTPException: 404 when the case does not exist.
    """
    await _require_auth(token, session)
    case = await session.get(Case, case_id)
    if case is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")

    if body.title is not None:
        case.title = body.title
    if body.description is not None:
        case.description = body.description
    if body.priority is not None:
        case.priority = body.priority

    case.updated_at = datetime.utcnow()
    session.add(case)
    await session.commit()
    await session.refresh(case)
    return CaseResponse.model_validate(case)


@router.delete("/{case_id}", status_code=204)
async def delete_case(
    case_id: int,
    token: str = Query(...),
    session: AsyncSession = Depends(get_session),
) -> None:
    """Permanently delete a case and its associated conversation records.

    Args:
        case_id: Database primary key.
        token: JWT for authentication.
        session: Injected database session.

    Raises:
        HTTPException: 404 when the case does not exist.
    """
    await _require_auth(token, session)
    case = await session.get(Case, case_id)
    if case is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    await session.delete(case)
    await session.commit()


@router.get("/{case_id}/document")
async def download_case_document(
    case_id: int,
    doc_index: int = Query(0, ge=0),
    token: str = Query(...),
    session: AsyncSession = Depends(get_session),
) -> FileResponse:
    """Stream a document attached to a case as a file download.

    Args:
        case_id: Database primary key.
        doc_index: Zero-based index into the ``documents_json`` array.  Defaults
            to ``0`` (first / only document), preserving backward compatibility.
        token: JWT for authentication.
        session: Injected database session.

    Returns:
        A ``FileResponse`` streaming the stored file.

    Raises:
        HTTPException: 404 when the case, document index, or file does not exist.
    """
    await _require_auth(token, session)
    case = await session.get(Case, case_id)
    if case is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    if case.documents_json:
        docs = json.loads(case.documents_json)
        if doc_index >= len(docs):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
        doc = docs[doc_index]
        path = Path(doc["path"])
        filename = doc.get("name") or path.name
    elif case.document_path:
        path = Path(case.document_path)
        filename = case.document_original_name or path.name
    else:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    if not path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document file missing from storage",
        )
    return FileResponse(path=path, filename=filename)


@router.post("/{case_id}/accept", response_model=CaseResponse)
async def accept_case(
    case_id: int,
    body: AcceptCaseRequest,
    token: str = Query(...),
    session: AsyncSession = Depends(get_session),
) -> CaseResponse:
    """Accept a pending case and notify the client.

    Args:
        case_id: Database primary key.
        body: Optional note to include in the acceptance notification.
        token: JWT for authentication.
        session: Injected database session.

    Returns:
        The updated ``CaseResponse``.

    Raises:
        HTTPException: 404 / 409 on missing or non-pending case.
    """
    current_user = await _require_auth(token, session)
    case = await session.get(Case, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    if case.status != CaseStatus.PENDING:
        raise HTTPException(status_code=409, detail="Case is not pending")

    case.status = CaseStatus.ACCEPTED
    case.lawyer_note = body.note
    case.updated_at = datetime.utcnow()
    session.add(case)
    await session.commit()
    await session.refresh(case)

    await _messaging.notify_case_accepted(case.platform, case.chat_id, current_user.name, body.note)

    return CaseResponse.model_validate(case)


@router.post("/{case_id}/reject", response_model=CaseResponse)
async def reject_case(
    case_id: int,
    body: RejectCaseRequest,
    token: str = Query(...),
    session: AsyncSession = Depends(get_session),
) -> CaseResponse:
    """Reject a case and notify the client with the stated reason.

    Args:
        case_id: Database primary key.
        body: Mandatory rejection reason.
        token: JWT for authentication.
        session: Injected database session.

    Returns:
        The updated ``CaseResponse``.

    Raises:
        HTTPException: 404 / 409 on missing or non-pending case.
    """
    await _require_auth(token, session)
    case = await session.get(Case, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    if case.status != CaseStatus.PENDING:
        raise HTTPException(status_code=409, detail="Case is not pending")

    case.status = CaseStatus.REJECTED
    case.lawyer_note = body.reason
    case.updated_at = datetime.utcnow()
    session.add(case)
    await session.commit()
    await session.refresh(case)

    await _messaging.notify_case_rejected(case.platform, case.chat_id, body.reason)

    return CaseResponse.model_validate(case)


@router.post("/{case_id}/request-info", response_model=CaseResponse)
async def request_more_info(
    case_id: int,
    body: RequestMoreInfoRequest,
    token: str = Query(...),
    session: AsyncSession = Depends(get_session),
) -> CaseResponse:
    """Mark a case as requiring more information and message the client.

    Args:
        case_id: Database primary key.
        body: The message / question to forward to the client.
        token: JWT for authentication.
        session: Injected database session.

    Returns:
        The updated ``CaseResponse``.

    Raises:
        HTTPException: 404 on missing case.
    """
    await _require_auth(token, session)
    case = await session.get(Case, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")

    case.status = CaseStatus.MORE_INFO_REQUESTED
    case.lawyer_note = body.message
    case.updated_at = datetime.utcnow()
    session.add(case)
    await session.commit()
    await session.refresh(case)

    await _messaging.notify_more_info_requested(case.platform, case.chat_id, body.message)

    return CaseResponse.model_validate(case)
