# Setup Guide

## Prerequisites

| Tool | Version | Purpose |
|---|---|---|
| Python | ≥ 3.12 | Runtime |
| [uv](https://docs.astral.sh/uv/) | latest | Package manager and workspace |
| Docker + Docker Compose | latest | Containerised local development |
| [flyctl](https://fly.io/docs/hands-on/install-flyctl/) | latest | fly.io deployment CLI |
| Telegram account | — | Create the bot via BotFather |
| Google AI Studio account | — | Issue the Gemini API key |

---

## Environment variables

Copy the example file and fill in every value before running any service.

```bash
cp .env.example .env
```

| Variable | Description |
|---|---|
| `SECRET_KEY` | Random string used to sign JWTs. Generate with `openssl rand -hex 32`. |
| `TELEGRAM_BOT_TOKEN` | Token issued by [@BotFather](https://t.me/BotFather) when you create the bot. |
| `TELEGRAM_WEBHOOK_SECRET` | Any random string. Telegram will include it in every webhook request header so the API can verify the source. |
| `GEMINI_API_KEY` | API key from [Google AI Studio](https://aistudio.google.com/app/apikey). |
| `GEMINI_MODEL` | Model name. Default `gemini-1.5-pro`. Change to `gemini-2.0-flash` for faster, cheaper responses. |
| `API_BASE_URL` | The public base URL of the API service. Used to self-register the Telegram webhook. Must be reachable by Telegram's servers (HTTPS). |
| `SEED_EMAIL` | Email for the auto-created legal-professional account. |
| `SEED_PASSWORD` | Password for that account. Change before deploying. |
| `NICEGUI_SECRET_KEY` | Secret used to sign NiceGUI session cookies. Generate with `openssl rand -hex 32`. |
| `API_URL` | URL the dashboard uses to reach the API. Use `http://localhost:8000` locally or the fly.io URL in production. |

---

## Local development

### 1. Install dependencies

```bash
# API
cd api
uv sync
cd ..

# Dashboard
cd dashboard
uv sync
cd ..
```

### 2. Run the API

```bash
cd api
uv run uvicorn api.main:app --reload --port 8000
```

The API will:
- Create `legalai.db` (SQLite) in the current directory on first start.
- Seed a default legal-professional account using `SEED_EMAIL` / `SEED_PASSWORD`.
- Serve the interactive API docs at [http://localhost:8000/docs](http://localhost:8000/docs).

### 3. Run the dashboard

In a second terminal:

```bash
cd dashboard
uv run python -m dashboard.main
```

Open [http://localhost:8080](http://localhost:8080) and log in with the seed credentials.

### 4. Expose the API for Telegram (local testing)

Telegram requires a publicly reachable HTTPS URL to deliver webhook events. Use a tunnelling tool to expose your local server:

```bash
# Using ngrok
ngrok http 8000
```

Copy the `https://` URL ngrok prints and set it in `.env`:

```
API_BASE_URL=https://abc123.ngrok-free.app
```

Then register the webhook (see the [Telegram webhook](#telegram-webhook) section below).

---

## Docker Compose

Running both services together with Docker Compose is the simplest way to validate the full stack locally.

```bash
# Build and start both services
docker compose up --build

# Run in the background
docker compose up --build -d

# Stop
docker compose down
```

Services:
- API → [http://localhost:8000](http://localhost:8000)
- Dashboard → [http://localhost:8080](http://localhost:8080)

The `uploads/` directory is bind-mounted into the API container so files survive container restarts.

---

## Telegram webhook

After the API is publicly reachable (either via ngrok locally or fly.io in production), register the webhook once:

```bash
# 1. Get a JWT by logging in
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"lawyer@legalai.com","password":"legalai2024"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# 2. Register the webhook
curl -X POST "http://localhost:8000/webhook/setup/telegram?token=$TOKEN"
```

A successful response looks like:

```json
{"ok": true, "result": true, "description": "Webhook was set"}
```

Telegram will now POST all bot updates to `{API_BASE_URL}/webhook/telegram`.

---

## fly.io deployment

### First-time setup

```bash
# Authenticate
fly auth login

# Create the API app (run from the api/ directory)
cd api
fly launch --name legalai-api --no-deploy

# Create a persistent volume for uploads (1 GB)
fly volumes create legalai_data --region iad --size 1

# Set secrets
fly secrets set \
  SECRET_KEY="$(openssl rand -hex 32)" \
  TELEGRAM_BOT_TOKEN="your-bot-token" \
  TELEGRAM_WEBHOOK_SECRET="$(openssl rand -hex 16)" \
  GEMINI_API_KEY="your-gemini-key" \
  SEED_PASSWORD="choose-a-strong-password" \
  NICEGUI_SECRET_KEY="$(openssl rand -hex 32)"

# Deploy the API
fly deploy
cd ..
```

Once the API is live, note its URL (e.g. `https://legalai-api.fly.dev`) and set `API_BASE_URL` in the dashboard secrets.

```bash
# Create the dashboard app (run from the dashboard/ directory)
cd dashboard
fly launch --name legalai-dashboard --no-deploy

fly secrets set \
  API_URL="https://legalai-api.fly.dev" \
  NICEGUI_SECRET_KEY="$(openssl rand -hex 32)"

fly deploy
cd ..
```

### Register the Telegram webhook on fly.io

```bash
TOKEN=$(curl -s -X POST https://legalai-api.fly.dev/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"lawyer@legalai.com","password":"your-seed-password"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

curl -X POST "https://legalai-api.fly.dev/webhook/setup/telegram?token=$TOKEN"
```

### Subsequent deploys

```bash
cd api       && fly deploy && cd ..
cd dashboard && fly deploy && cd ..
```

### Scaling and regions

The `fly.toml` files are pre-configured with `auto_stop_machines = true` to keep costs low. To pin a region or increase memory, edit the `[[vm]]` section.

---

## Production checklist

- [ ] All secrets set via `fly secrets set` (nothing in `.env` in production)
- [ ] `SEED_PASSWORD` changed from the default
- [ ] `SECRET_KEY` and `NICEGUI_SECRET_KEY` are randomly generated 32-byte hex strings
- [ ] `TELEGRAM_WEBHOOK_SECRET` is set and matches in both `fly secrets set` and the webhook registration call
- [ ] Telegram webhook registration completed and returns `{"ok": true}`
- [ ] Dashboard login tested with the production URL
- [ ] Persistent volume attached to the API (`fly volumes list`)
