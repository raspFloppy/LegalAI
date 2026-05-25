from api import strings
from api.config import settings
from api.services.platform.base import MessagingPlatform
from api.services.platform.telegram import TelegramAdapter


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
        lawyer_name: str,
        note: str | None = None,
    ) -> None:
        """Notify a client that their case was accepted.

        Args:
            platform: Originating messaging platform.
            chat_id: Client's chat identifier.
            lawyer_name: Full name of the lawyer who accepted the case.
            note: Optional personalised note from the lawyer.
        """
        adapter = self.get_adapter(platform)
        text = strings.CASE_ACCEPTED.format(lawyer_name=lawyer_name)
        if note:
            text += strings.CASE_ACCEPTED_NOTE_SUFFIX.format(note=note)
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
        text = strings.CASE_REJECTED.format(reason=reason)
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
        text = strings.MORE_INFO_REQUESTED.format(message=message)
        await adapter.send_message(chat_id, text)
