from abc import ABC, abstractmethod
from enum import Enum
from typing import Optional

from pydantic import BaseModel


class MessageType(str, Enum):
    """Type of content contained in a normalised platform message."""

    TEXT = "text"
    VOICE = "voice"
    DOCUMENT = "document"
    IMAGE = "image"
    CALLBACK = "callback"


class InlineButton(BaseModel):
    """A single button inside an inline keyboard row.

    Attributes:
        label: Text displayed on the button.
        callback_data: Opaque string sent back when the button is pressed.
    """

    label: str
    callback_data: str


class NormalisedMessage(BaseModel):
    """Platform-agnostic message representation.

    All platform adapters convert their native payloads into this schema so
    that the core business logic never depends on a specific platform's API.

    Attributes:
        platform: Lowercase platform identifier (e.g. ``"telegram"``).
        chat_id: Stable chat/conversation identifier used to route replies.
        user_id: Platform-specific user identifier.
        username: Human-readable username (may fall back to user_id).
        message_type: Content category of this message.
        text: Plain-text body for ``TEXT`` messages or transcribed voice.
        file_bytes: Raw binary content for ``VOICE``, ``DOCUMENT``, or
            ``IMAGE`` messages.
        file_mime_type: MIME type of ``file_bytes`` when present.
        file_name: Original filename when the user sent a document.
        callback_data: Opaque payload from an inline-button press.
        callback_query_id: Platform identifier needed to acknowledge the
            callback (Telegram ``answerCallbackQuery``).
        message_id: Platform message identifier (used when editing messages).
    """

    platform: str
    chat_id: str
    user_id: str
    username: str
    message_type: MessageType
    text: Optional[str] = None
    file_bytes: Optional[bytes] = None
    file_mime_type: Optional[str] = None
    file_name: Optional[str] = None
    callback_data: Optional[str] = None
    callback_query_id: Optional[str] = None
    message_id: Optional[int] = None


class MessagingPlatform(ABC):
    """Abstract interface every messaging-platform adapter must implement.

    Concrete adapters (e.g. ``TelegramAdapter``) translate between the
    platform's native webhook payload / API and the normalised types defined
    in this module, ensuring the rest of the application stays platform-
    agnostic.
    """

    @abstractmethod
    async def parse_update(self, payload: dict) -> Optional[NormalisedMessage]:
        """Convert a raw webhook payload into a ``NormalisedMessage``.

        Args:
            payload: The decoded JSON body received from the platform webhook.

        Returns:
            A ``NormalisedMessage`` when the update is actionable, or ``None``
            for updates the adapter intentionally ignores (e.g. channel posts).
        """

    @abstractmethod
    async def send_message(self, chat_id: str, text: str) -> None:
        """Send a plain-text message to a chat.

        Args:
            chat_id: Destination chat identifier.
            text: Message body (HTML formatting supported where the platform
                allows it).
        """

    @abstractmethod
    async def send_message_with_buttons(
        self,
        chat_id: str,
        text: str,
        buttons: list[list[InlineButton]],
    ) -> None:
        """Send a message with an attached inline keyboard.

        Args:
            chat_id: Destination chat identifier.
            text: Message body.
            buttons: 2-D list of ``InlineButton`` objects representing the
                keyboard grid (outer list = rows, inner list = columns).
        """

    @abstractmethod
    async def answer_callback_query(
        self,
        callback_query_id: str,
        text: str = "",
    ) -> None:
        """Acknowledge a callback query to dismiss the loading indicator.

        Args:
            callback_query_id: Platform-assigned callback query identifier.
            text: Optional toast notification shown to the user.
        """

    @abstractmethod
    async def download_file(self, file_id: str) -> tuple[bytes, str]:
        """Download a file from the platform's CDN.

        Args:
            file_id: Platform-specific file identifier.

        Returns:
            A tuple of ``(raw_bytes, mime_type)``.
        """
