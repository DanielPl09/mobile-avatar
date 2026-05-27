#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# Start the OpenClaw Gateway in a persistent tmux session.
# The session survives shell exits and reconnects on re-attach.
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SESSION="openclaw"

# Load secrets
ENV_FILE="$SCRIPT_DIR/.env"
if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
fi

# Kill stale session if present
tmux kill-session -t "$SESSION" 2>/dev/null || true
sleep 1

echo "Starting OpenClaw Gateway in tmux session '$SESSION'..."

tmux new-session -d -s "$SESSION" \
  -e "TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN:-}" \
  -e "OPENCLAW_GATEWAY_TOKEN=${OPENCLAW_GATEWAY_TOKEN:-}" \
  -e "HUGGINGFACE_HUB_TOKEN=${HUGGINGFACE_HUB_TOKEN:-}" \
  "openclaw gateway run --force"

sleep 4

if tmux has-session -t "$SESSION" 2>/dev/null; then
  echo "✓ Gateway running in tmux session '$SESSION'"
  echo ""
  echo "  Attach to logs:  tmux attach -t $SESSION"
  echo "  Stop gateway:    tmux kill-session -t $SESSION"
  echo "  Check status:    openclaw channels status"
else
  echo "✗ Gateway failed to start. Check logs:"
  echo "  tmux capture-pane -t $SESSION -p"
  exit 1
fi
