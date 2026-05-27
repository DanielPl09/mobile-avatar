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
  echo "⚠  HUGGINGFACE_HUB_TOKEN is not set — HuggingFace inference will use the"
  echo "   built-in free tier (limited requests). Add a token for full access."
  echo "   https://huggingface.co/settings/tokens"
fi

# ── 3. Install OpenClaw (idempotent) ─────────────────────────────────────────
if ! command -v openclaw &>/dev/null; then
  echo "→  Installing OpenClaw..."
  npm install -g openclaw@latest
else
  echo "✓  OpenClaw $(openclaw --version 2>&1 | head -1) already installed"
fi

# ── 4. Deploy config ─────────────────────────────────────────────────────────
OPENCLAW_DIR="$HOME/.openclaw"
mkdir -p "$OPENCLAW_DIR"

echo "→  Deploying openclaw.json to $OPENCLAW_DIR/openclaw.json"
cp "$SCRIPT_DIR/openclaw.json" "$OPENCLAW_DIR/openclaw.json"

# ── 5. Validate config ────────────────────────────────────────────────────────
echo "→  Validating config..."
openclaw config validate && echo "✓  Config is valid" || {
  echo "✗  Config validation failed — check openclaw.json"
  exit 1
}

# ── 6. Register the Telegram channel ─────────────────────────────────────────
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
echo "    2. Send your bot a DM on Telegram — it will reply with a pairing code"
echo "    3. Run:  openclaw pairing list telegram"
echo "    4. Run:  openclaw pairing approve telegram <CODE>"
echo ""
echo "  To add the bot to a group:"
echo "    • Add @YourBot to the group"
echo "    • Mention the bot or use /setprivacy in BotFather to disable privacy mode"
echo "    • Check group IDs:  openclaw logs --follow"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
