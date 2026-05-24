# Bot — Technical Reference

## Overview

The bot is not a standalone process. It is implemented as a set of HTTP endpoints inside the FastAPI service (`api/`). Telegram delivers updates by calling the API's webhook endpoint; the API processes each update, interacts with the AI, persists data, and replies through the Telegram Bot API.

```
Telegram Servers
      │
      │  POST /webhook/telegram
      │  (X-Telegram-Bot-Api-Secret-Token header)
      ▼
┌──────────────────────────────────────────────────────┐
│  webhook.py router                                   │
│  ┌─────────────────────────────────────────────────┐ │
│  │  TelegramAdapter.parse_update()                 │ │
│  │       ↓ NormalisedMessage                       │ │
│  │  _dispatch() [BackgroundTask]                   │ │
│  │    ├── _handle_new_message()                    │ │
│  │    └── _handle_callback()                       │ │
│  └─────────────────────────────────────────────────┘ │
│  AIService   FileService   MessagingService          │
└──────────────────────────────────────────────────────┘
      │
      │  POST https://api.telegram.org/bot{token}/sendMessage
      ▼
Telegram Servers → Client device
```

---

## Platform abstraction layer

### `services/platform/base.py`

All platform-specific logic is hidden behind two abstractions:

**`NormalisedMessage`** — a Pydantic model that represents any inbound message regardless of origin. Fields include `platform`, `chat_id`, `user_id`, `username`, `message_type`, plus type-specific payloads (`text`, `file_bytes`, `callback_data`, etc.).

**`MessagingPlatform`** — an abstract base class with four methods every adapter must implement:

| Method | Purpose |
|---|---|
| `parse_update(payload)` | Convert a raw webhook JSON payload into a `NormalisedMessage`. Return `None` for irrelevant updates. |
| `send_message(chat_id, text)` | Send a plain HTML text message. |
| `send_message_with_buttons(chat_id, text, buttons)` | Send a message with an inline keyboard (`list[list[InlineButton]]`). |
| `answer_callback_query(callback_query_id, text)` | Acknowledge a button press to dismiss Telegram's loading spinner. |
| `download_file(file_id)` | Download a file from the platform CDN and return `(bytes, mime_type)`. |

Adding WhatsApp (or any other platform) means implementing `MessagingPlatform` and registering the new adapter in `MessagingService.__init__`. No other code changes are required.

### `services/platform/telegram.py` — `TelegramAdapter`

Handles three categories of Telegram update:

| Update type | Handling |
|---|---|
| `message.text` | Extracts text, creates `TEXT` message |
| `message.voice` | Downloads OGG/OPUS file, creates `VOICE` message |
| `message.document` | Downloads file, preserves original filename, creates `DOCUMENT` message |
| `message.photo` | Downloads the largest photo variant, creates `IMAGE` message |
| `callback_query` | Extracts callback data and query ID, creates `CALLBACK` message |

All outbound calls use `httpx.AsyncClient` against `https://api.telegram.org/bot{token}/`.

---

## Webhook endpoint

### `POST /webhook/telegram`

**Security.** Telegram includes a `X-Telegram-Bot-Api-Secret-Token` header on every request when a secret is configured at webhook registration time. The endpoint compares this value against `settings.telegram_webhook_secret` and returns `403` on mismatch.

**Responsiveness.** The endpoint returns `{"ok": true}` immediately after parsing the update. All actual processing is handed off to FastAPI's `BackgroundTasks` queue. This guarantees a response within milliseconds and prevents Telegram from retrying the delivery due to a timeout.

```
POST /webhook/telegram
   │
   ├── Validate secret token header
   ├── Parse body → NormalisedMessage via TelegramAdapter
   ├── Return 200 {"ok": true}          ← happens immediately
   └── background: _dispatch(message)
```

---

## Conversation state machine

Each client interaction follows a state machine tracked in the `Conversation` database table.

```
                  First message arrives
                          │
                          ▼
                  ┌───────────────┐
                  │ GATHERING_INFO│  ← Conversation row created
                  └───────┬───────┘
                          │
            ┌─────────────┴───────────────┐
     AI has questions?              No questions
            │                             │
            ▼                             ▼
   Send inline keyboard          Finalise case immediately
   for question 1 of N                    │
            │                             │
   User taps button                       │
   (callback_query)                       │
            │                             │
   Record answer                          │
            │                             │
   More questions?──Yes──► Send next question
            │
           No
            │
            ▼
     Re-analyse with answers
            │
            ▼
        ┌──────────┐
        │ SUBMITTED│  ← Case row created, confirmation sent to client
        └──────────┘
```

**`Conversation` table fields:**

| Field | Purpose |
|---|---|
| `collected_text` | Accumulates all user input (initial message + any follow-up text) |
| `questions_json` | JSON array of `{question, options[]}` from the first AI analysis |
| `answers_json` | JSON object mapping question index → chosen answer option |
| `current_question_index` | Which question is currently being presented |
| `file_path` / `file_mime_type` | Stored attachment details, carried over to the Case on finalisation |
| `state` | `GATHERING_INFO` or `SUBMITTED` |
| `case_id` | FK populated once the Case record is created |

---

## Message processing pipeline

### New message (`_handle_new_message`)

```
Receive NormalisedMessage
         │
         ▼
Is there an active GATHERING_INFO conversation for this chat_id?
         │
    YES ─┴─ NO
    │              │
    │         Pre-process input:
    │           VOICE  → AIService.transcribe_voice()  → text
    │           DOCUMENT/IMAGE → kept as file_bytes for multimodal analysis
    │           TEXT   → used directly
    │              │
    │         Send "Analysing your case…" acknowledgement
    │              │
    │         AIService.analyse_case(text, file_bytes?)
    │              │
    │         Create Conversation row
    │              │
    │         Has questions? ──YES──► ask_next_question()
    │              │
    │              NO
    │              │
    └──────────────▼
              _finalise_case()
```

### Callback (`_handle_callback`)

Callback data uses the format `conv:{conversation_id}:q{question_index}:{answer_text}`.

```
Parse callback data  →  conv_id, q_idx, answer
         │
         ▼
Load Conversation from DB, verify state == GATHERING_INFO
         │
         ▼
Append answer to answers_json, increment current_question_index
         │
         ▼
More questions remaining?
         │
    YES──┴──NO
    │           │
    │     Re-run AIService.analyse_case() with all collected answers
    │           │
ask_next_question()    _finalise_case()
```

---

## AI service (`services/ai_service.py`)

### `analyse_case(text, file_bytes?, file_mime_type?, previous_answers?)`

Sends a structured prompt to Gemini with `response_mime_type = "application/json"` to guarantee parseable output. The model is instructed to return:

```json
{
  "title": "5-7 word case title",
  "description": "2-3 sentence professional description",
  "priority": "HIGH | MEDIUM | LOW",
  "user_feedback": "Empathetic non-advisory reply to the client",
  "questions": [
    { "question": "...", "options": ["...", "..."] }
  ]
}
```

**Priority rules (embedded in the system prompt):**

| Priority | Criteria |
|---|---|
| HIGH | Criminal matters, domestic violence, urgent child custody, housing eviction, immigration detention, urgent injunctions |
| MEDIUM | Civil disputes, employment law, contracts, debt collection, general family law |
| LOW | General legal questions, document review, estate planning, business formation |

When `file_bytes` are provided they are passed as inline base64 data alongside the text prompt, enabling multimodal analysis of PDFs and images without an intermediate file-upload step.

When `previous_answers` are provided they are appended to the prompt as additional context so the model can produce a more accurate description and priority on the second pass.

### `transcribe_voice(audio_bytes, mime_type)`

Uses a separate `GenerativeModel` instance (without `response_mime_type` constraint) to request a plain-text transcription of the audio. The resulting text is then passed to `analyse_case` as if the client had typed the message.

---

## File service (`services/file_service.py`)

Files are stored at `{upload_dir}/{case_id}/{uuid}{ext}`. The extension is inferred from the original filename if provided, or from the MIME type. Because files may arrive before the Case row exists, a temporary Case is created during the conversation flow solely to obtain an integer ID for directory naming; this temporary row is deleted before the real Case is committed.

The stored absolute path is written to `Case.document_path`. The original filename is preserved in `Case.document_original_name` and returned to the dashboard for the download link label.

---

## Notification service (`services/messaging_service.py`)

`MessagingService` holds a registry of platform adapters keyed by platform name string. The three notification helpers — `notify_case_accepted`, `notify_case_rejected`, `notify_more_info_requested` — resolve the correct adapter from the `Case.platform` field and call `send_message` with pre-formatted HTML text. This keeps the case action routers platform-agnostic: they only call `_messaging.notify_*()` and never reference Telegram directly.

---

## Inline keyboard format

When the AI returns questions, each one is sent as a separate message with a vertical inline keyboard (one button per row). The callback data embedded in each button is:

```
conv:{conversation_id}:q{question_index}:{option_text}
```

Example for conversation 7, question 0, option "Yes":

```
conv:7:q0:Yes
```

The handler splits on `:` (maximum 4 parts) to recover all three values. Option text is used verbatim as the answer so the stored `answers_json` contains human-readable strings.

---

## Database models relevant to the bot

### `Conversation`

Created when the first message arrives. Holds all transient state for the question-answer loop. Remains in the database after submission (state = `SUBMITTED`) for audit purposes.

### `Case`

Created by `_finalise_case()` once all questions have been answered (or immediately if no questions are needed). Contains the denormalised data the dashboard displays: title, description, priority, status, platform identifiers for reply routing, and the stored file path.
