import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, model_validator

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
        document_original_name: Original filename of the primary document (legacy).
        documents_json: Raw JSON array of all attached documents.
        documents: Derived list of original filenames for all documents.
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
    document_original_name: Optional[str] = None
    documents_json: Optional[str] = None
    documents: list[str] = []
    lawyer_note: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @model_validator(mode="after")
    def derive_documents(self) -> "CaseResponse":
        """Populate ``documents`` from ``documents_json`` or the legacy field."""
        if self.documents_json:
            docs = json.loads(self.documents_json)
            self.documents = [
                d.get("name") or Path(d.get("path", "")).name
                for d in docs
                if d.get("name") or d.get("path")
            ]
        elif self.document_original_name and not self.documents:
            self.documents = [self.document_original_name]
        return self


class PatchCaseRequest(BaseModel):
    """Request body for editing case fields from the dashboard.

    All fields are optional; only provided fields are updated.

    Attributes:
        title: New case title.
        description: New case description.
        priority: New urgency level.
    """

    title: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[CasePriority] = None


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
