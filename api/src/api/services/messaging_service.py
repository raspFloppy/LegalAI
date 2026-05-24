from api.services.platform.base import MessagingPlatform
from api.services.platform.telegram import TelegramAdapter
from api.config import settings


class MessagingService:
    """Routes outbound notifications to the correct messaging platform.

    A single instance is shared across request handlers.  The registry maps
    platform names to initialised ``MessagingPlatform`` adapters.

    Args:
        telegram_token: Bot token used to initialise the Telegram adapter.
    """

    def __init__(
        self,
        telegram_token: str = settings.telegram_bot_token,
    ) -> None:
        self._platforms: dict[str, MessagingPlatform] = {
            "telegram": TelegramAdapter(bot_token=telegram_token),
        }

    def get_adapter(self, platform: str) -> MessagingPlatform:
        """Return the adapter for the named platform.

        Args:
            platform: Lowercase platform key (e.g. ``"telegram"``).

        Returns:
            The ``MessagingPlatform`` adapter for that platform.

        Raises:
            ValueError: When ``platform`` is not registered.
        """
        adapter = self._platforms.get(platform)
        if adapter is None:
            raise ValueError(f"Unsupported platform: {platform!r}")
        return adapter

    async def notify_case_accepted(
        self,
        platform: str,
        chat_id: str,
        note: str | None = None,
    ) -> None:
        """Notify a client that their case was accepted.

        Args:
            platform: Originating messaging platform.
            chat_id: Client's chat identifier.
            note: Optional personalised note from the lawyer.
        """
        adapter = self.get_adapter(platform)
        text = (
            "✅ <b>Your case has been accepted.</b>\n\n"
            "A member of our legal team will be in contact with you shortly."
        )
        if note:
            text += f"\n\n<i>{note}</i>"
        await adapter.send_message(chat_id, text)

    async def notify_case_rejected(
        self,
        platform: str,
        chat_id: str,
        reason: str,
    ) -> None:
        """Notify a client that their case was rejected.

        Args:
            platform: Originating messaging platform.
            chat_id: Client's chat identifier.
            reason: Rejection reason supplied by the lawyer.
        """
        adapter = self.get_adapter(platform)
        text = (
            "❌ <b>Your case has been reviewed.</b>\n\n"
            "Unfortunately we are unable to take on your case at this time.\n\n"
            f"<b>Reason:</b> {reason}"
        )
        await adapter.send_message(chat_id, text)

    async def notify_more_info_requested(
        self,
        platform: str,
        chat_id: str,
        message: str,
    ) -> None:
        """Forward the lawyer's information request to the client.

        Args:
            platform: Originating messaging platform.
            chat_id: Client's chat identifier.
            message: The lawyer's question or clarification request.
        """
        adapter = self.get_adapter(platform)
        text = (
            "📋 <b>Our team needs more information about your case:</b>\n\n"
            f"{message}\n\n"
            "Please reply to this message with the requested details."
        )
        await adapter.send_message(chat_id, text)
