import json
import logging
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request, status
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from api.config import settings
from api.database.connection import get_session
from api.database.models import Case, Conversation, ConversationState
from api.services.ai_service import AIService, CaseAnalysisResult
from api.services.file_service import FileService
from api.services.messaging_service import MessagingService
from api.services.platform.base import MessageType, NormalisedMessage
from api.services.platform.telegram import TelegramAdapter

logger = logging.getLogger(__name__)

router = APIRouter()

_ai = AIService()
_files = FileService()
_messaging = MessagingService()
_telegram = TelegramAdapter(bot_token=settings.telegram_bot_token)


@router.post("/telegram")
async def telegram_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    session: Annotated[AsyncSession, Depends(get_session)],
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
) -> dict:
    """Receive and process Telegram Bot API updates.

    Validates the secret token header, parses the update into a
    ``NormalisedMessage``, and dispatches to the appropriate handler in a
    background task so Telegram's 5-second timeout is always met.

    Args:
        request: The raw FastAPI request (body read as JSON).
        background_tasks: FastAPI background task queue.
        session: Injected database session.
        x_telegram_bot_api_secret_token: Secret token set when registering
            the webhook, used to verify the request originated from Telegram.

    Returns:
        ``{"ok": True}`` immediately so Telegram does not retry.

    Raises:
        HTTPException: 403 when the secret token does not match.
    """
    if (
        settings.telegram_webhook_secret
        and x_telegram_bot_api_secret_token != settings.telegram_webhook_secret
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid secret")

    payload = await request.json()
    message = await _telegram.parse_update(payload)

    if message is None:
        return {"ok": True}

    background_tasks.add_task(_dispatch, message, session)
    return {"ok": True}


@router.post("/setup/telegram")
async def setup_telegram_webhook(
    token: str,
    url: str | None = None,
) -> dict:
    """Register the Telegram webhook URL.

    Args:
        token: Admin JWT to authorise the setup call.
        url: Override the webhook URL.  When omitted, ``API_BASE_URL`` from
            settings is used.  Pass the ngrok/fly.io base URL here to avoid
            restarting the server just to update the address.

    Returns:
        Telegram's raw ``setWebhook`` response plus the registered URL.
    """
    webhook_url = f"{url.rstrip('/')}/webhook/telegram" if url else f"{settings.api_base_url}/webhook/telegram"
    result = await _telegram.register_webhook(
        webhook_url=webhook_url,
        secret_token=settings.telegram_webhook_secret,
    )
    result["registered_url"] = webhook_url
    return result


async def _dispatch(message: NormalisedMessage, session: AsyncSession) -> None:
    """Route an incoming normalised message to the correct handler.

    Args:
        message: The normalised inbound message.
        session: Active database session.
    """
    try:
        if message.message_type == MessageType.CALLBACK:
            await _handle_callback(message, session)
        else:
            await _handle_new_message(message, session)
    except Exception as exc:
        logger.exception("Error processing message from %s: %s", message.platform, exc)
        adapter = _messaging.get_adapter(message.platform)
        await adapter.send_message(
            message.chat_id,
            "⚠️ We encountered an error processing your message. Please try again.",
        )


async def _handle_new_message(
    message: NormalisedMessage,
    session: AsyncSession,
) -> None:
    """Process a text, voice, document, or image message.

    Checks for an active conversation for the sender.  If one exists the
    message is treated as a follow-up reply; otherwise a new conversation is
    started and the AI analysis is performed.

    Args:
        message: Normalised inbound message.
        session: Active database session.
    """
    adapter = _messaging.get_adapter(message.platform)

    result = await session.exec(
        select(Conversation).where(
            Conversation.platform == message.platform,
            Conversation.chat_id == message.chat_id,
            Conversation.state == ConversationState.GATHERING_INFO,
        )
    )
    active_conv = result.first()

    if active_conv and active_conv.state == ConversationState.GATHERING_INFO:
        active_conv.collected_text += f"\n\nAdditional info: {message.text or ''}"
        active_conv.updated_at = datetime.utcnow()
        session.add(active_conv)
        await session.commit()

        answers = json.loads(active_conv.answers_json or "{}")
        analysis = await _ai.analyse_case(
            text=active_conv.collected_text,
            file_bytes=None,
            previous_answers={int(k): v for k, v in answers.items()},
        )
        await _finalise_case(active_conv, analysis, session, adapter)
        return

    file_bytes: bytes | None = None
    file_mime: str | None = None
    file_name: str | None = None

    if message.message_type == MessageType.VOICE and message.file_bytes:
        transcription = await _ai.transcribe_voice(
            message.file_bytes,
            mime_type=message.file_mime_type or "audio/ogg",
        )
        text = transcription
        file_bytes = message.file_bytes
        file_mime = message.file_mime_type
    elif message.message_type in (MessageType.DOCUMENT, MessageType.IMAGE):
        text = message.text or "Document/image submitted for review"
        file_bytes = message.file_bytes
        file_mime = message.file_mime_type
        file_name = message.file_name
    else:
        text = message.text or ""

    await adapter.send_message(
        message.chat_id,
        "🔍 <b>Analysing your case...</b>\n\nPlease wait a moment.",
    )

    analysis = await _ai.analyse_case(
        text=text,
        file_bytes=file_bytes if message.message_type in (MessageType.DOCUMENT, MessageType.IMAGE) else None,
        file_mime_type=file_mime if message.message_type in (MessageType.DOCUMENT, MessageType.IMAGE) else None,
    )

    conv = Conversation(
        platform=message.platform,
        chat_id=message.chat_id,
        user_id=message.user_id,
        username=message.username,
        collected_text=text,
        questions_json=json.dumps(
            [q.model_dump() for q in analysis.questions]
        ),
        answers_json="{}",
        file_mime_type=file_mime,
        file_original_name=file_name,
    )

    if file_bytes:
        tmp_case = Case(
            platform=message.platform,
            chat_id=message.chat_id,
            user_id=message.user_id,
            username=message.username,
            title=analysis.title,
            description=analysis.description,
            priority=analysis.priority,
            raw_message=text,
        )
        session.add(tmp_case)
        await session.flush()
        stored_path = await _files.save(
            file_bytes, file_name, tmp_case.id, mime_type=file_mime or "application/octet-stream"
        )
        conv.file_path = str(stored_path)
        await session.delete(tmp_case)

    session.add(conv)
    await session.commit()
    await session.refresh(conv)

    if analysis.questions:
        await _ask_next_question(conv, analysis.questions, 0, adapter)
    else:
        await _finalise_case(conv, analysis, session, adapter)


async def _handle_callback(
    message: NormalisedMessage,
    session: AsyncSession,
) -> None:
    """Process an inline-keyboard callback from a clarifying question.

    Parses the ``conv:{id}:q{idx}:{answer}`` callback data, records the
    answer, and either asks the next question or finalises the case.

    Args:
        message: Normalised callback message.
        session: Active database session.
    """
    adapter = _messaging.get_adapter(message.platform)

    if message.callback_query_id:
        await adapter.answer_callback_query(message.callback_query_id)

    data = message.callback_data or ""
    parts = data.split(":")
    if len(parts) != 4 or parts[0] != "conv":
        return

    conv_id = int(parts[1])
    q_idx = int(parts[2][1:])
    answer = parts[3]

    conv = await session.get(Conversation, conv_id)
    if conv is None or conv.state != ConversationState.GATHERING_INFO:
        return

    if conv.current_question_index > q_idx:
        return

    if message.message_id:
        await adapter.remove_inline_keyboard(message.chat_id, message.message_id)

    answers = json.loads(conv.answers_json or "{}")
    answers[str(q_idx)] = answer
    conv.answers_json = json.dumps(answers)
    conv.current_question_index = q_idx + 1
    conv.updated_at = datetime.utcnow()
    session.add(conv)
    await session.commit()
    await session.refresh(conv)

    questions = [
        type("Q", (), {"question": q["question"], "options": q["options"]})()
        for q in json.loads(conv.questions_json or "[]")
    ]

    next_idx = q_idx + 1
    if next_idx < len(questions):
        await _ask_next_question(conv, questions, next_idx, adapter)
    else:
        analysis = await _ai.analyse_case(
            text=conv.collected_text,
            previous_answers={int(k): v for k, v in answers.items()},
        )
        await _finalise_case(conv, analysis, session, adapter)


async def _ask_next_question(
    conv: Conversation,
    questions: list,
    idx: int,
    adapter,
) -> None:
    """Send the question at ``idx`` as an inline-keyboard message.

    Callback data format: ``conv:{conv.id}:q{idx}:{option_text}``

    Args:
        conv: The active ``Conversation`` record.
        questions: Full list of clarifying questions from the analysis.
        idx: Index of the question to send now.
        adapter: The platform adapter to send the message through.
    """
    from api.services.platform.base import InlineButton

    q = questions[idx]
    buttons = [
        [InlineButton(
            label=opt,
            callback_data=f"conv:{conv.id}:q{idx}:{opt}",
        )]
        for opt in q.options
    ]

    total = len(questions)
    header = f"❓ <b>Question {idx + 1} of {total}</b>\n\n"
    await adapter.send_message_with_buttons(conv.chat_id, header + q.question, buttons)


async def _finalise_case(
    conv: Conversation,
    analysis: CaseAnalysisResult,
    session: AsyncSession,
    adapter,
) -> None:
    """Create the Case record and send the AI feedback to the client.

    Args:
        conv: The completed ``Conversation`` record.
        analysis: Final AI analysis result.
        session: Active database session.
        adapter: The platform adapter for sending the confirmation message.
    """
    file_path = conv.file_path
    if file_path:
        stored = _files.resolve_path(file_path)
        doc_path = str(stored)
    else:
        doc_path = None

    case = Case(
        platform=conv.platform,
        chat_id=conv.chat_id,
        user_id=conv.user_id,
        username=conv.username,
        title=analysis.title,
        description=analysis.description,
        priority=analysis.priority,
        raw_message=conv.collected_text,
        document_path=doc_path,
        document_original_name=conv.file_original_name,
    )
    session.add(case)

    conv.state = ConversationState.SUBMITTED
    conv.updated_at = datetime.utcnow()
    session.add(conv)

    await session.commit()
    await session.refresh(case)

    case_id = case.id
    conv.case_id = case_id
    session.add(conv)
    await session.commit()

    priority_emoji = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢"}.get(
        analysis.priority.value, "⚪"
    )

    confirmation = (
        f"{analysis.user_feedback}\n\n"
        f"{priority_emoji} <b>Case priority:</b> {analysis.priority.value}\n"
        f"📁 <b>Case ID:</b> #{case_id}\n\n"
        "A legal professional will review your case and contact you shortly."
    )
    await adapter.send_message(conv.chat_id, confirmation)
