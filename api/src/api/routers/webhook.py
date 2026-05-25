import json
import logging
import re
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request, status
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from api import strings
from api.config import settings
from api.database.connection import get_session
from api.database.models import Case, Conversation, ConversationState
from api.services.ai_service import AIService, CaseAnalysisResult
from api.services.file_service import FileService
from api.services.messaging_service import MessagingService
from api.services.platform.base import InlineButton, MessageType, NormalisedMessage
from api.services.platform.telegram import TelegramAdapter

logger = logging.getLogger(__name__)

router = APIRouter()

_ai = AIService()
_files = FileService()
_messaging = MessagingService()
_telegram = TelegramAdapter(bot_token=settings.telegram_bot_token)

_NAME_RE = re.compile(r"^[a-zA-ZÀ-ÖØ-öø-ÿ'\-]+(?: [a-zA-ZÀ-ÖØ-öø-ÿ'\-]+)+$")


def _is_valid_full_name(text: str) -> bool:
    """Return ``True`` when ``text`` looks like a proper first-and-last name.

    Args:
        text: Raw input from the user.

    Returns:
        ``True`` if the input contains at least two words made entirely of
        letters, hyphens, or apostrophes (accented characters included).
    """
    return bool(_NAME_RE.match(text.strip()))


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
    webhook_url = (
        f"{url.rstrip('/')}/webhook/telegram"
        if url
        else f"{settings.api_base_url}/webhook/telegram"
    )
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
            await _handle_message(message, session)
    except Exception as exc:
        logger.exception("Error processing message from %s: %s", message.platform, exc)
        try:
            adapter = _messaging.get_adapter(message.platform)
            await adapter.send_message(message.chat_id, strings.DISPATCH_ERROR)
        except Exception:
            logger.exception("Failed to send error message to %s", message.chat_id)


async def _active_conversation(
    platform: str,
    chat_id: str,
    session: AsyncSession,
    *states: ConversationState,
) -> Conversation | None:
    """Return the most recent conversation for a chat in one of the given states.

    Args:
        platform: Messaging platform identifier.
        chat_id: Platform chat identifier.
        session: Active database session.
        *states: One or more ``ConversationState`` values to match.

    Returns:
        The first matching ``Conversation`` or ``None``.
    """
    result = await session.exec(
        select(Conversation)
        .where(
            Conversation.platform == platform,
            Conversation.chat_id == chat_id,
            Conversation.state.in_(list(states)),
        )
        .order_by(Conversation.created_at.desc())
    )
    return result.first()


async def _handle_message(
    message: NormalisedMessage,
    session: AsyncSession,
) -> None:
    """Route a non-callback message based on the active conversation state.

    Conversation lifecycle::

        /start  →  AWAITING_NAME  →  GATHERING_INFO  →  SUBMITTED

    Returning users with a SUBMITTED conversation are asked whether they want
    to add information to the existing case or open a new one.

    Args:
        message: Normalised inbound message.
        session: Active database session.
    """
    adapter = _messaging.get_adapter(message.platform)
    is_start = (message.text or "").strip().lower() in {"/start", "start"}

    if is_start:
        await _start_onboarding(message, session, adapter)
        return

    conv = await _active_conversation(
        message.platform,
        message.chat_id,
        session,
        ConversationState.AWAITING_NAME,
        ConversationState.GATHERING_INFO,
        ConversationState.AWAITING_UPDATE_CONFIRMATION,
    )

    if conv is None:
        submitted = await _active_conversation(
            message.platform,
            message.chat_id,
            session,
            ConversationState.SUBMITTED,
        )
        if submitted and submitted.case_id:
            await _ask_update_or_new(message, submitted, session, adapter)
            return
        await _start_onboarding(message, session, adapter)
        return

    if conv.state == ConversationState.AWAITING_NAME:
        await _handle_name_input(message, conv, session, adapter)
    elif conv.state == ConversationState.AWAITING_UPDATE_CONFIRMATION:
        await adapter.send_message(message.chat_id, strings.USE_BUTTONS)
    else:
        await _handle_case_input(message, conv, session, adapter)


async def _start_onboarding(
    message: NormalisedMessage,
    session: AsyncSession,
    adapter,
) -> None:
    """Create a new AWAITING_NAME conversation and greet the user.

    Args:
        message: The triggering inbound message.
        session: Active database session.
        adapter: Platform adapter for sending the greeting.
    """
    conv = Conversation(
        platform=message.platform,
        chat_id=message.chat_id,
        user_id=message.user_id,
        username=message.username,
        state=ConversationState.AWAITING_NAME,
        collected_text="",
    )
    session.add(conv)
    await session.commit()
    await adapter.send_message(message.chat_id, strings.WELCOME)


async def _ask_update_or_new(
    message: NormalisedMessage,
    submitted_conv: Conversation,
    session: AsyncSession,
    adapter,
) -> None:
    """Ask a returning user whether to update the existing case or open a new one.

    Transitions the submitted conversation to AWAITING_UPDATE_CONFIRMATION so
    free-text messages are ignored until the user presses a button.

    Args:
        message: The triggering inbound message.
        submitted_conv: The most recent SUBMITTED conversation for this chat.
        session: Active database session.
        adapter: Platform adapter for sending the question.
    """
    submitted_conv.state = ConversationState.AWAITING_UPDATE_CONFIRMATION
    submitted_conv.updated_at = datetime.utcnow()
    session.add(submitted_conv)
    await session.commit()

    name = submitted_conv.display_name or submitted_conv.username
    case_id = submitted_conv.case_id
    buttons = [
        [InlineButton(
            label=strings.UPDATE_YES_BTN.format(case_id=case_id),
            callback_data=f"update:{case_id}:{submitted_conv.id}:yes",
        )],
        [InlineButton(
            label=strings.UPDATE_NO_BTN,
            callback_data=f"update:{case_id}:{submitted_conv.id}:no",
        )],
    ]
    await adapter.send_message_with_buttons(
        message.chat_id,
        strings.ASK_UPDATE_OR_NEW.format(name=name, case_id=case_id),
        buttons,
    )


async def _handle_name_input(
    message: NormalisedMessage,
    conv: Conversation,
    session: AsyncSession,
    adapter,
) -> None:
    """Validate the user's name and transition to GATHERING_INFO.

    Accepts only text messages.  If the name fails validation (fewer than
    two words, digits, or special characters) the bot asks again.

    Args:
        message: The message containing the proposed full name.
        conv: The active AWAITING_NAME conversation record.
        session: Active database session.
        adapter: Platform adapter for replies.
    """
    if message.message_type != MessageType.TEXT:
        await adapter.send_message(message.chat_id, strings.NAME_INVALID)
        return

    raw_name = (message.text or "").strip()

    if not _is_valid_full_name(raw_name):
        await adapter.send_message(message.chat_id, strings.NAME_INVALID)
        return

    display_name = " ".join(part.capitalize() for part in raw_name.split())

    conv.display_name = display_name
    conv.state = ConversationState.GATHERING_INFO
    conv.updated_at = datetime.utcnow()
    session.add(conv)
    await session.commit()

    await adapter.send_message(
        message.chat_id,
        strings.ASK_PROBLEM.format(name=display_name),
    )


async def _handle_case_input(
    message: NormalisedMessage,
    conv: Conversation,
    session: AsyncSession,
    adapter,
) -> None:
    """Process the user's legal problem description.

    Handles text, voice (transcribed via Gemini), documents, and images.
    Sends an AI analysis and either asks clarifying questions or finalises
    the case immediately.

    Args:
        message: The message containing the legal problem.
        conv: The active GATHERING_INFO conversation record.
        session: Active database session.
        adapter: Platform adapter for replies.
    """
    if conv.collected_text:
        conv.collected_text += strings.ADDITIONAL_INFO_SUFFIX.format(
            text=message.text or ""
        )
        conv.updated_at = datetime.utcnow()
        session.add(conv)
        await session.commit()

        answers = json.loads(conv.answers_json or "{}")
        analysis = await _ai.analyse_case(
            text=conv.collected_text,
            previous_answers={int(k): v for k, v in answers.items()},
        )
        await _finalise_case(conv, analysis, session, adapter)
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
        text = message.text or strings.DOCUMENT_SUBMITTED_TEXT
        file_bytes = message.file_bytes
        file_mime = message.file_mime_type
        file_name = message.file_name
    else:
        text = message.text or ""

    try:
        await adapter.send_message(message.chat_id, strings.ANALYSING)
    except Exception:
        logger.warning("Could not send analysis notification to %s", message.chat_id)

    analysis = await _ai.analyse_case(
        text=text,
        file_bytes=file_bytes if message.message_type in (MessageType.DOCUMENT, MessageType.IMAGE) else None,
        file_mime_type=file_mime if message.message_type in (MessageType.DOCUMENT, MessageType.IMAGE) else None,
    )

    conv.collected_text = text
    conv.questions_json = json.dumps([q.model_dump() for q in analysis.questions])
    conv.file_mime_type = file_mime
    conv.file_original_name = file_name
    conv.updated_at = datetime.utcnow()

    if file_bytes:
        save_under_id = conv.linked_case_id
        if save_under_id is None:
            tmp = Case(
                platform=conv.platform,
                chat_id=conv.chat_id,
                user_id=conv.user_id,
                username=conv.display_name or conv.username,
                title=analysis.title,
                description=analysis.description,
                priority=analysis.priority,
                raw_message=text,
            )
            session.add(tmp)
            await session.flush()
            save_under_id = tmp.id

        stored = await _files.save(
            file_bytes, file_name, save_under_id, mime_type=file_mime or "application/octet-stream"
        )
        conv.file_path = str(stored)

        if conv.linked_case_id is None:
            await session.delete(tmp)

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
    """Process inline-keyboard callbacks.

    Handles two callback formats:
    - ``conv:{id}:q{idx}:{answer}``  — clarifying question answer
    - ``update:{case_id}:{conv_id}:{yes|no}``  — update-or-new choice

    Args:
        message: Normalised callback message.
        session: Active database session.
    """
    adapter = _messaging.get_adapter(message.platform)

    if message.callback_query_id:
        await adapter.answer_callback_query(message.callback_query_id)

    data = message.callback_data or ""
    parts = data.split(":")

    if parts[0] == "update" and len(parts) == 4:
        if message.message_id:
            await adapter.remove_inline_keyboard(message.chat_id, message.message_id)
        await _handle_update_choice(
            message, session,
            case_id=int(parts[1]),
            conv_id=int(parts[2]),
            choice=parts[3],
        )
        return

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


async def _handle_update_choice(
    message: NormalisedMessage,
    session: AsyncSession,
    case_id: int,
    conv_id: int,
    choice: str,
) -> None:
    """Process the user's choice to update an existing case or open a new one.

    Args:
        message: Normalised callback message.
        session: Active database session.
        case_id: ID of the existing case the user was asked about.
        conv_id: ID of the AWAITING_UPDATE_CONFIRMATION conversation.
        choice: ``"yes"`` to update, ``"no"`` to start fresh onboarding.
    """
    adapter = _messaging.get_adapter(message.platform)

    submitted_conv = await session.get(Conversation, conv_id)
    if submitted_conv is None:
        return

    submitted_conv.state = ConversationState.SUBMITTED
    submitted_conv.updated_at = datetime.utcnow()
    session.add(submitted_conv)

    if choice == "yes":
        new_conv = Conversation(
            platform=message.platform,
            chat_id=message.chat_id,
            user_id=message.user_id,
            username=message.username,
            state=ConversationState.GATHERING_INFO,
            display_name=submitted_conv.display_name,
            collected_text="",
            linked_case_id=case_id,
        )
        session.add(new_conv)
        await session.commit()
        await adapter.send_message(
            message.chat_id,
            strings.UPDATE_START.format(case_id=case_id),
        )
    else:
        new_conv = Conversation(
            platform=message.platform,
            chat_id=message.chat_id,
            user_id=message.user_id,
            username=message.username,
            state=ConversationState.AWAITING_NAME,
            collected_text="",
        )
        session.add(new_conv)
        await session.commit()
        await adapter.send_message(message.chat_id, strings.WELCOME)


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
        questions: Full list of clarifying questions from the AI analysis.
        idx: Index of the question to send now.
        adapter: Platform adapter for sending the message.
    """
    q = questions[idx]
    buttons = [
        [InlineButton(label=opt, callback_data=f"conv:{conv.id}:q{idx}:{opt}")]
        for opt in q.options
    ]
    total = len(questions)
    header = strings.QUESTION_HEADER.format(idx=idx + 1, total=total)
    await adapter.send_message_with_buttons(conv.chat_id, header + q.question, buttons)


async def _finalise_case(
    conv: Conversation,
    analysis: CaseAnalysisResult,
    session: AsyncSession,
    adapter,
) -> None:
    """Create or update a Case record and notify the client.

    When ``conv.linked_case_id`` is set the existing case is updated with the
    new analysis and any new document is appended to ``documents_json``.
    Otherwise a new Case is created.

    Args:
        conv: The completed ``Conversation`` record.
        analysis: Final AI analysis result.
        session: Active database session.
        adapter: Platform adapter for sending the confirmation message.
    """
    doc_path = str(_files.resolve_path(conv.file_path)) if conv.file_path else None

    if conv.linked_case_id:
        existing = await session.get(Case, conv.linked_case_id)
        if existing is not None:
            await _update_case(existing, conv, analysis, doc_path, session, adapter)
            return
        logger.warning("Linked case %d not found; creating new case instead", conv.linked_case_id)

    new_doc = {"path": doc_path, "name": conv.file_original_name} if doc_path else None

    case = Case(
        platform=conv.platform,
        chat_id=conv.chat_id,
        user_id=conv.user_id,
        username=conv.display_name or conv.username,
        title=analysis.title,
        description=analysis.description,
        priority=analysis.priority,
        raw_message=conv.collected_text,
        document_path=doc_path,
        document_original_name=conv.file_original_name,
        documents_json=json.dumps([new_doc]) if new_doc else None,
    )
    session.add(case)

    conv.state = ConversationState.SUBMITTED
    conv.updated_at = datetime.utcnow()
    session.add(conv)

    await session.commit()
    await session.refresh(case)

    case_id = case.id
    chat_id = conv.chat_id

    conv.case_id = case_id
    session.add(conv)
    await session.commit()

    priority_emoji = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢"}.get(
        analysis.priority.value, "⚪"
    )
    confirmation = strings.CASE_CONFIRMATION.format(
        user_feedback=analysis.user_feedback,
        priority_emoji=priority_emoji,
        priority=analysis.priority.value,
        case_id=case_id,
    )
    await adapter.send_message(chat_id, confirmation)


async def _update_case(
    case: Case,
    conv: Conversation,
    analysis: CaseAnalysisResult,
    doc_path: str | None,
    session: AsyncSession,
    adapter,
) -> None:
    """Update an existing case with new information and an optional new document.

    Merges the existing documents list with any new file, updates the AI
    analysis fields, and appends the new raw message to the case history.

    Args:
        case: The existing ``Case`` to update.
        conv: The completed update ``Conversation``.
        analysis: Fresh AI analysis including the new information.
        doc_path: Absolute path to the new file, or ``None``.
        session: Active database session.
        adapter: Platform adapter for sending the confirmation message.
    """
    existing_docs: list[dict] = []
    if case.documents_json:
        existing_docs = json.loads(case.documents_json)
    elif case.document_path:
        existing_docs = [{"path": case.document_path, "name": case.document_original_name}]

    if doc_path:
        existing_docs.append({"path": doc_path, "name": conv.file_original_name})
        case.document_path = doc_path
        case.document_original_name = conv.file_original_name

    case.description = analysis.description
    case.priority = analysis.priority
    case.raw_message = case.raw_message + f"\n\n--- Aggiornamento ---\n{conv.collected_text}"
    case.documents_json = json.dumps(existing_docs) if existing_docs else None
    case.updated_at = datetime.utcnow()
    session.add(case)

    conv.state = ConversationState.SUBMITTED
    conv.case_id = case.id
    conv.updated_at = datetime.utcnow()
    session.add(conv)

    await session.commit()

    await adapter.send_message(
        conv.chat_id,
        strings.UPDATE_CONFIRMED.format(case_id=case.id),
    )
