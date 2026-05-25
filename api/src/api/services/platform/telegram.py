import asyncio
import logging
import mimetypes
from typing import Optional

import httpx

from api.services.platform.base import (
    InlineButton,
    MessagingPlatform,
    MessageType,
    NormalisedMessage,
)

logger = logging.getLogger(__name__)

_TIMEOUT = httpx.Timeout(connect=10.0, read=60.0, write=30.0, pool=5.0)
_MAX_RETRIES = 2
_RETRY_DELAY = 2.0


class TelegramAdapter(MessagingPlatform):
    """Telegram Bot API adapter.

    Translates Telegram webhook updates into ``NormalisedMessage`` objects and
    provides methods to send messages / inline keyboards back via the Bot API.

    Args:
        bot_token: The token issued by BotFather.
    """

    _BASE_URL = "https://api.telegram.org/bot{token}"
    _FILE_URL = "https://api.telegram.org/file/bot{token}/{path}"

    def __init__(self, bot_token: str) -> None:
        self._token = bot_token
        self._api_base = self._BASE_URL.format(token=bot_token)

    async def _post(self, method: str, payload: dict) -> dict:
        """POST to a Telegram Bot API method with automatic retry on connect timeout.

        Args:
            method: Telegram Bot API method name (e.g. ``"sendMessage"``).
            payload: JSON body to send.

        Returns:
            Parsed JSON response body.

        Raises:
            httpx.ConnectTimeout: When all retry attempts are exhausted.
        """
        url = f"{self._api_base}/{method}"
        last_exc: Exception = RuntimeError("unreachable")
        for attempt in range(_MAX_RETRIES + 1):
            try:
                async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                    resp = await client.post(url, json=payload)
                    return resp.json()
            except httpx.ConnectTimeout as exc:
                last_exc = exc
                if attempt < _MAX_RETRIES:
                    logger.warning(
                        "ConnectTimeout on Telegram %s (attempt %d/%d), retrying in %.0fs…",
                        method, attempt + 1, _MAX_RETRIES + 1, _RETRY_DELAY,
                    )
                    await asyncio.sleep(_RETRY_DELAY)
        raise last_exc

    async def parse_update(self, payload: dict) -> Optional[NormalisedMessage]:
        """Parse a Telegram webhook update.

        Handles ``message`` updates carrying text, voice, documents, and
        photos, as well as ``callback_query`` updates from inline keyboards.

        Args:
            payload: Decoded JSON body of the Telegram webhook POST.

        Returns:
            A ``NormalisedMessage`` or ``None`` if the update is not
            actionable (e.g. edited messages, channel posts).
        """
        if "callback_query" in payload:
            return await self._parse_callback_query(payload["callback_query"])

        message = payload.get("message")
        if not message:
            return None

        sender = message.get("from", {})
        chat = message.get("chat", {})

        user_id = str(sender.get("id", "unknown"))
        chat_id = str(chat.get("id", "unknown"))
        username = (
            sender.get("username")
            or sender.get("first_name")
            or user_id
        )

        base = dict(
            platform="telegram",
            chat_id=chat_id,
            user_id=user_id,
            username=username,
            message_id=message.get("message_id"),
        )

        if "text" in message:
            return NormalisedMessage(
                **base,
                message_type=MessageType.TEXT,
                text=message["text"],
            )

        if "voice" in message:
            file_bytes, mime_type = await self.download_file(
                message["voice"]["file_id"]
            )
            return NormalisedMessage(
                **base,
                message_type=MessageType.VOICE,
                file_bytes=file_bytes,
                file_mime_type=mime_type or "audio/ogg",
            )

        if "document" in message:
            doc = message["document"]
            file_bytes, mime_type = await self.download_file(doc["file_id"])
            return NormalisedMessage(
                **base,
                message_type=MessageType.DOCUMENT,
                file_bytes=file_bytes,
                file_mime_type=mime_type or doc.get("mime_type", "application/octet-stream"),
                file_name=doc.get("file_name"),
            )

        if "photo" in message:
            largest = max(message["photo"], key=lambda p: p.get("file_size", 0))
            file_bytes, mime_type = await self.download_file(largest["file_id"])
            return NormalisedMessage(
                **base,
                message_type=MessageType.IMAGE,
                file_bytes=file_bytes,
                file_mime_type=mime_type or "image/jpeg",
            )

        return None

    async def _parse_callback_query(self, cq: dict) -> NormalisedMessage:
        """Convert a Telegram callback_query object into a NormalisedMessage.

        Args:
            cq: The ``callback_query`` sub-object from the Telegram update.

        Returns:
            A ``NormalisedMessage`` with ``message_type=CALLBACK``.
        """
        sender = cq.get("from", {})
        chat = cq.get("message", {}).get("chat", {})
        user_id = str(sender.get("id", "unknown"))
        username = (
            sender.get("username")
            or sender.get("first_name")
            or user_id
        )
        return NormalisedMessage(
            platform="telegram",
            chat_id=str(chat.get("id", user_id)),
            user_id=user_id,
            username=username,
            message_type=MessageType.CALLBACK,
            callback_data=cq.get("data"),
            callback_query_id=cq.get("id"),
            message_id=cq.get("message", {}).get("message_id"),
        )

    async def send_message(self, chat_id: str, text: str) -> None:
        """Send a plain-text message via the Telegram Bot API.

        Args:
            chat_id: Target chat identifier.
            text: Message body.  HTML parse mode is enabled so ``<b>`` and
                ``<i>`` tags work.
        """
        await self._post("sendMessage", {"chat_id": chat_id, "text": text, "parse_mode": "HTML"})

    async def send_message_with_buttons(
        self,
        chat_id: str,
        text: str,
        buttons: list[list[InlineButton]],
    ) -> None:
        """Send a message with an inline keyboard.

        Args:
            chat_id: Target chat identifier.
            text: Message body.
            buttons: Keyboard grid as ``InlineButton`` rows.
        """
        keyboard = [
            [{"text": btn.label, "callback_data": btn.callback_data} for btn in row]
            for row in buttons
        ]
        await self._post("sendMessage", {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "reply_markup": {"inline_keyboard": keyboard},
        })

    async def answer_callback_query(
        self,
        callback_query_id: str,
        text: str = "",
    ) -> None:
        """Acknowledge a callback query.

        Args:
            callback_query_id: The ``id`` field of the incoming callback query.
            text: Optional toast text shown briefly to the user.
        """
        await self._post("answerCallbackQuery", {"callback_query_id": callback_query_id, "text": text})

    async def download_file(self, file_id: str) -> tuple[bytes, str]:
        """Download a file identified by its Telegram file_id.

        Args:
            file_id: Telegram file identifier (from the message object).

        Returns:
            A tuple of ``(raw_bytes, mime_type)``.  The MIME type is guessed
            from the file extension when the platform does not provide it.
        """
        last_exc: Exception = RuntimeError("unreachable")
        for attempt in range(_MAX_RETRIES + 1):
            try:
                async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                    meta_resp = await client.get(
                        f"{self._api_base}/getFile",
                        params={"file_id": file_id},
                    )
                    meta_resp.raise_for_status()
                    file_path = meta_resp.json()["result"]["file_path"]

                    download_url = self._FILE_URL.format(token=self._token, path=file_path)
                    file_resp = await client.get(download_url)
                    file_resp.raise_for_status()

                    mime_type, _ = mimetypes.guess_type(file_path)
                    return file_resp.content, mime_type or "application/octet-stream"
            except httpx.ConnectTimeout as exc:
                last_exc = exc
                if attempt < _MAX_RETRIES:
                    logger.warning(
                        "ConnectTimeout downloading file (attempt %d/%d), retrying…",
                        attempt + 1, _MAX_RETRIES + 1,
                    )
                    await asyncio.sleep(_RETRY_DELAY)
        raise last_exc

    async def remove_inline_keyboard(self, chat_id: str, message_id: int) -> None:
        """Edit a message to strip its inline keyboard.

        Called immediately after a callback query is answered so the buttons
        become unclickable and duplicate submissions are prevented.

        Args:
            chat_id: Chat identifier of the message to edit.
            message_id: Identifier of the message whose keyboard should be
                removed.
        """
        await self._post("editMessageReplyMarkup", {
            "chat_id": chat_id,
            "message_id": message_id,
            "reply_markup": {"inline_keyboard": []},
        })

    async def register_webhook(self, webhook_url: str, secret_token: str) -> dict:
        """Register the webhook URL with Telegram.

        Should be called once after deployment.  Subsequent calls with the
        same URL are idempotent.

        Args:
            webhook_url: The publicly reachable HTTPS URL Telegram will POST
                updates to (e.g. ``https://api.example.com/webhook/telegram``).
            secret_token: Secret included in the
                ``X-Telegram-Bot-Api-Secret-Token`` header for validation.

        Returns:
            The raw JSON response from Telegram's ``setWebhook`` endpoint.
        """
        return await self._post("setWebhook", {"url": webhook_url, "secret_token": secret_token})
