from datetime import datetime
from enum import Enum
from typing import Optional

from sqlmodel import Field, SQLModel


class CasePriority(str, Enum):
    """Priority levels assigned to a legal case by the AI."""

    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class CaseStatus(str, Enum):
    """Lifecycle status of a legal case."""

    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    MORE_INFO_REQUESTED = "MORE_INFO_REQUESTED"


class ConversationState(str, Enum):
    """State of an ongoing bot conversation before a case is created."""

    GATHERING_INFO = "GATHERING_INFO"
    SUBMITTED = "SUBMITTED"


class LegalUser(SQLModel, table=True):
    """A legal professional who can log in to the dashboard.

    Attributes:
        id: Auto-incremented primary key.
        email: Unique login email.
        hashed_password: Bcrypt-hashed password.
        name: Display name shown in the dashboard.
        is_active: Whether the account can authenticate.
    """

    __tablename__ = "legal_users"

    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(unique=True, index=True)
    hashed_password: str
    name: str
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Case(SQLModel, table=True):
    """A legal case submitted through the messaging bot.

    Attributes:
        id: Auto-incremented primary key.
        platform: Originating messaging platform (e.g. ``"telegram"``).
        chat_id: Platform-specific chat identifier for reply routing.
        user_id: Platform-specific user identifier.
        username: Human-readable username provided by the client.
        title: Short AI-generated title (used as column header).
        description: Longer AI-generated case description for the dashboard.
        priority: AI-assigned urgency level.
        status: Current processing status.
        raw_message: The original user message text or transcription.
        document_path: Filesystem path to an uploaded file, if any.
        document_original_name: Original filename as uploaded by the client.
        lawyer_note: Optional note added by the lawyer (rejection reason, etc.).
        created_at: UTC timestamp of case creation.
        updated_at: UTC timestamp of last status change.
    """

    __tablename__ = "cases"

    id: Optional[int] = Field(default=None, primary_key=True)
    platform: str
    chat_id: str
    user_id: str
    username: str
    title: str
    description: str
    priority: CasePriority
    status: CaseStatus = Field(default=CaseStatus.PENDING)
    raw_message: str
    document_path: Optional[str] = Field(default=None)
    document_original_name: Optional[str] = Field(default=None)
    lawyer_note: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class Conversation(SQLModel, table=True):
    """Tracks an in-progress bot conversation while the AI gathers information.

    Attributes:
        id: Auto-incremented primary key.
        platform: Originating messaging platform.
        chat_id: Platform-specific chat identifier.
        user_id: Platform-specific user identifier.
        username: Human-readable username.
        state: Current conversation phase.
        collected_text: Accumulated user input (initial message + answers).
        questions_json: JSON-serialised list of pending clarifying questions.
        answers_json: JSON-serialised dict mapping question index to answer.
        current_question_index: Index of the question currently being asked.
        file_path: Path to a file the user attached, if any.
        file_mime_type: MIME type of the attached file.
        file_original_name: Original filename of the attachment.
        case_id: FK to the created Case once the conversation is complete.
    """

    __tablename__ = "conversations"

    id: Optional[int] = Field(default=None, primary_key=True)
    platform: str
    chat_id: str
    user_id: str
    username: str
    state: ConversationState = Field(default=ConversationState.GATHERING_INFO)
    collected_text: str
    questions_json: Optional[str] = Field(default=None)
    answers_json: Optional[str] = Field(default="{}"),
    current_question_index: int = Field(default=0)
    file_path: Optional[str] = Field(default=None)
    file_mime_type: Optional[str] = Field(default=None)
    file_original_name: Optional[str] = Field(default=None)
    case_id: Optional[int] = Field(default=None, foreign_key="cases.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
