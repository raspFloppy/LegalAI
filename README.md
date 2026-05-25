# LegalAI

LegalAI is a legal case intake and triage platform that connects clients with legal professionals through a conversational messaging interface. Clients submit their legal queries — by text, voice, or attached documents — and an AI evaluates each case, generates a structured summary, assigns a priority level, and delivers an empathetic, non-advisory response to the client. The resulting cases are surfaced on a dedicated dashboard where legal professionals can review, sort, and act on them.

## What it does

### Client-facing bot

Clients interact through a Telegram bot. They can describe their legal situation in a text message, send a voice note, or attach a PDF or image. The system handles all three input types transparently:

- **Text messages** are analysed directly.
- **Voice messages** are transcribed and then analysed.
- **Documents and images** are processed with multimodal AI to extract relevant content before analysis.

When the AI determines that key information is missing, it asks the client up to two clarifying questions delivered as inline keyboard buttons — the client taps an answer and the conversation continues without typing. Once enough context has been gathered, the client receives a structured acknowledgement: a brief AI-generated summary of their situation, a priority indicator, and a case reference number. The client is told that a legal professional will be in touch; no legal advice is given at any point.

### Legal professional dashboard

Legal professionals log in to a web dashboard where all submitted cases are displayed in a sortable, filterable table. Each row shows:

- Case ID and submission date
- Client username
- AI-generated case description
- Priority level (High / Medium / Low) with colour coding
- Current status
- A download link when the client attached a document

For each pending case a lawyer can take one of three actions:

- **Accept** — the case is assigned to the firm and the client is notified via the bot.
- **Reject** — the lawyer provides a reason, which is forwarded to the client.
- **Request more information** — the lawyer composes a message that is sent to the client through the bot, prompting them to reply with the missing details.

The dashboard polls for new cases automatically and reflects status changes in real time.

## Architecture overview

```
Client (Telegram)
       │  HTTPS webhook
       ▼
┌─────────────────────┐
│     API Service     │  FastAPI · Python 3.12
│  ─────────────────  │
│  Webhook handler    │  Normalises updates from any platform
│  AI pipeline        │  Gemini 3.5 flash (text · audio · vision)
│  Case store         │  SQLite → PostgreSQL-ready
│  Notification hub   │  Routes replies back to the correct platform
│  REST API           │  JWT-authenticated endpoints for the dashboard
└─────────────────────┘
         │  HTTP (internal)
         ▼
┌─────────────────────┐
│  Dashboard Service  │  NiceGUI · Python 3.12
│  ─────────────────  │
│  Login page         │
│  Cases table        │
│  Action dialogs     │
└─────────────────────┘
```

The platform layer is designed for multi-channel support. Adding a WhatsApp (or any other) adapter requires implementing a single abstract interface without changing any business logic.

## Technology stack

| Layer | Technology |
|---|---|
| API framework | FastAPI + Uvicorn |
| Dashboard | NiceGUI |
| Database ORM | SQLModel (SQLAlchemy async + Pydantic) |
| Database | SQLite (development) / PostgreSQL (production) |
| AI | Google Gemini 1.5 Pro |
| Messaging | Telegram Bot API |
| Authentication | JWT (HS256) via python-jose |
| Package manager | uv (workspace monorepo) |
| Containers | Docker / Docker Compose |
| Hosting | fly.io |

## Repository layout

```
legalai/
├── api/                  FastAPI backend
│   └── src/api/
│       ├── database/     SQLModel models and async engine
│       ├── routers/      HTTP route handlers
│       ├── schemas/      Pydantic request/response types
│       └── services/     AI, file storage, messaging, platform adapters
└── dashboard/            NiceGUI frontend
    └── src/dashboard/
        ├── pages/        Login and cases pages
        └── services/     API client
```

See:
- [docs/SETUP.md](docs/SETUP.md) for installation and deployment instructions
- [docs/BOT.md](docs/BOT.md) for the bot's technical architecture
- [docs/DASHBOARD.md](docs/DASHBOARD.md) for the dashboard's design.
