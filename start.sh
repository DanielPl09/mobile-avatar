#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# Start the OpenClaw Gateway with all required env vars loaded from .env
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Load .env
ENV_FILE="$SCRIPT_DIR/.env"
if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
fi

echo "Starting OpenClaw Gateway..."
echo "  Telegram: enabled (long-poll mode)"
echo "  Model:    huggingface/meta-llama/Llama-3.3-70B-Instruct"
echo ""

exec openclaw gateway run
