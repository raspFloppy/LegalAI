from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from api.database.models import CasePriority, CaseStatus


class CaseResponse(BaseModel):
    """Full case representation returned by the REST API.

    Attributes:
        id: Database primary key.
        platform: Originating messaging platform.
        username: Client-provided username.
        title: Short AI-generated title.
        description: Longer AI-generated description.
        priority: Urgency level assigned by the AI.
        status: Current processing status.
        document_original_name: Original filename if a document was attached.
        lawyer_note: Note added by the reviewing lawyer, if any.
        created_at: Case creation timestamp (UTC).
        updated_at: Last modification timestamp (UTC).
    """

    id: int
    platform: str
    username: str
    title: str
    description: str
    priority: CasePriority
    status: CaseStatus
    document_original_name: Optional[str]
    lawyer_note: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AcceptCaseRequest(BaseModel):
    """Request body for accepting a case.

    Attributes:
        note: Optional note sent to the client alongside the acceptance
            notification.
    """

    note: Optional[str] = None


class RejectCaseRequest(BaseModel):
    """Request body for rejecting a case.

    Attributes:
        reason: Mandatory rejection reason forwarded to the client.
    """

    reason: str


class RequestMoreInfoRequest(BaseModel):
    """Request body asking the client for additional information.

    Attributes:
        message: The question or clarification request to forward to the
            client via the messaging platform.
    """

    message: str


class CaseListResponse(BaseModel):
    """Paginated list of cases.

    Attributes:
        items: Cases for the current page.
        total: Total number of cases matching the applied filters.
    """

    items: list[CaseResponse]
    total: int
