#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# OpenClaw Setup Script
# Installs OpenClaw, deploys the config, and adds the Telegram channel.
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  OpenClaw — Telegram Bot Setup"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# ── 1. Load environment variables ────────────────────────────────────────────
ENV_FILE="$SCRIPT_DIR/.env"
if [[ ! -f "$ENV_FILE" ]]; then
  echo "✗  .env file not found. Copy .env.example → .env and fill in your tokens."
  exit 1
fi
set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

# ── 2. Validate required secrets ─────────────────────────────────────────────
if [[ -z "${TELEGRAM_BOT_TOKEN:-}" ]]; then
  echo "✗  TELEGRAM_BOT_TOKEN is not set in .env"
  exit 1
fi

if [[ -z "${HUGGINGFACE_HUB_TOKEN:-}" ]]; then
  echo "⚠  HUGGINGFACE_HUB_TOKEN is not set — the bot can connect to Telegram but"
  echo "   cannot generate AI replies. Add your token to .env to enable responses."
  echo "   https://huggingface.co/settings/tokens/new?ownUserPermissions=inference.serverless.write&tokenType=fineGrained"
fi

# ── 3. Auto-generate gateway token if not set ────────────────────────────────
if [[ -z "${OPENCLAW_GATEWAY_TOKEN:-}" ]]; then
  OPENCLAW_GATEWAY_TOKEN=$(openssl rand -hex 32)
  echo "OPENCLAW_GATEWAY_TOKEN=$OPENCLAW_GATEWAY_TOKEN" >> "$ENV_FILE"
  echo "→  Generated new gateway auth token (saved to .env)"
fi
export OPENCLAW_GATEWAY_TOKEN

# ── 4. Install OpenClaw (idempotent) ─────────────────────────────────────────
if ! command -v openclaw &>/dev/null; then
  echo "→  Installing OpenClaw..."
  npm install -g openclaw@latest
else
  echo "✓  OpenClaw $(openclaw --version 2>&1 | head -1) already installed"
fi

# ── 5. Deploy config ─────────────────────────────────────────────────────────
OPENCLAW_DIR="$HOME/.openclaw"
mkdir -p "$OPENCLAW_DIR"

echo "→  Deploying openclaw.json to $OPENCLAW_DIR/openclaw.json"
cp "$SCRIPT_DIR/openclaw.json" "$OPENCLAW_DIR/openclaw.json"

# ── 6. Inject gateway auth token (persisted after deploy, not in repo) ───────
echo "→  Setting gateway auth token..."
openclaw config set gateway.auth.token "$OPENCLAW_GATEWAY_TOKEN" 2>&1

# ── 7. Validate config ────────────────────────────────────────────────────────
echo "→  Validating config..."
openclaw config validate && echo "✓  Config is valid" || {
  echo "✗  Config validation failed — check openclaw.json"
  exit 1
}

# ── 8. Register the Telegram channel ─────────────────────────────────────────
echo "→  Adding Telegram channel..."
openclaw channels add \
  --channel telegram \
  --token "$TELEGRAM_BOT_TOKEN" \
  --name "Telegram Bot"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ✓  Setup complete!"
echo ""
echo "  Next steps:"
echo "    1. Run:  ./start.sh"
echo "    2. Send your bot a DM on Telegram — it will reply immediately (dmPolicy=open)"
echo ""
echo "  To add the bot to a group:"
echo "    • Add @YourBot to the group"
echo "    • Mention it: @YourBot hello"
echo "    • Check group IDs:  openclaw logs --follow"
echo ""
if [[ -z "${HUGGINGFACE_HUB_TOKEN:-}" ]]; then
  echo "  ⚠  IMPORTANT: Add HUGGINGFACE_HUB_TOKEN to .env for AI responses to work!"
  echo "     https://huggingface.co/settings/tokens"
fi
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
