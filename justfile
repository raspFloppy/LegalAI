# Default: list available commands
default:
    @just --list

# Initialize the project: copy .env and generate secret keys
setup:
    cp -n .env.example .env || true
    @echo "--- Generating Secret Keys ---"
    sed -i "s/SECRET_KEY=.*/SECRET_KEY=$(openssl rand -hex 32)/" .env
    sed -i "s/NICEGUI_SECRET_KEY=.*/NICEGUI_SECRET_KEY=$(openssl rand -hex 32)/" .env
    sed -i "s/TELEGRAM_WEBHOOK_SECRET=.*/TELEGRAM_WEBHOOK_SECRET=$(openssl rand -hex 16)/" .env
    @echo "Done. Please fill in your TELEGRAM_BOT_TOKEN and GEMINI_API_KEY in .env"

# Install dependencies for the entire workspace
install:
    uv sync

# Run the API locally with hot-reload
api:
    cd api && uv run uvicorn api.main:app --reload --port 8000

# Run the dashboard locally
dashboard:
    cd dashboard && uv run python -m dashboard.main

# Run both services using Docker Compose
dev:
    docker compose up --build

# Stop all Docker services
stop:
    docker compose down

# Clean up local development artifacts (database and uploads)
clean:
    rm -rf api/legalai.db api/uploads dashboard/uploads
    @echo "Cleanup complete."

# Register the Telegram webhook
# URL can be ngrok (https://abc.ngrok-free.app), localhost (http://localhost:8000), or fly.io (https://app.fly.dev)
register-webhook:
    #!/usr/bin/env bash
    set -e
    read -p "Enter API base URL (ngrok / localhost / fly.io): " URL
    URL="${URL%/}"
    echo "→ Logging in at $URL ..."
    RESPONSE=$(curl -s --max-time 10 -X POST "$URL/auth/login" \
      -H "Content-Type: application/json" \
      -d '{"email":"lawyer@legalai.com","password":"legalai2024"}')
    if [ -z "$RESPONSE" ]; then
      echo "✗ No response from $URL — is the API running and reachable?"
      exit 1
    fi
    TOKEN=$(echo "$RESPONSE" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['access_token'])" 2>/dev/null)
    if [ -z "$TOKEN" ]; then
      echo "✗ Login failed. Server replied: $RESPONSE"
      exit 1
    fi
    echo "✓ Token obtained."
    echo "→ Registering webhook ..."
    curl -s --max-time 10 -X POST "$URL/webhook/setup/telegram?token=$TOKEN&url=$URL" | python3 -m json.tool

# Deploy the API to Fly.io
deploy-api:
    cd api && fly deploy

# Deploy the Dashboard to Fly.io
deploy-dashboard:
    cd dashboard && fly deploy

# Set Fly.io secrets for the API
set-secrets-api:
    @eval $$(grep -v '^#' .env | xargs) && cd api && fly secrets set \
        SECRET_KEY="$$SECRET_KEY" \
        TELEGRAM_BOT_TOKEN="$$TELEGRAM_BOT_TOKEN" \
        TELEGRAM_WEBHOOK_SECRET="$$TELEGRAM_WEBHOOK_SECRET" \
        GEMINI_API_KEY="$$GEMINI_API_KEY" \
        SEED_PASSWORD="$$SEED_PASSWORD" \
        NICEGUI_SECRET_KEY="$$NICEGUI_SECRET_KEY"

# Set Fly.io secrets for the Dashboard
set-secrets-dashboard:
    @eval $$(grep -v '^#' .env | xargs) && cd dashboard && fly secrets set \
        API_URL="https://legalai-api.fly.dev" \
        NICEGUI_SECRET_KEY="$$NICEGUI_SECRET_KEY"
