# OpenClaw — Telegram AI Bot

Self-hosted personal AI assistant connected to Telegram via [OpenClaw](https://openclaw.ai/).

**Provider:** HuggingFace Inference (Llama 3.3 70B · DeepSeek R1 · Qwen3 32B fallback chain)  
**Channel:** Telegram (long-poll, bot mode via grammY)

---

## Quick Start

### 1. Prerequisites

- Node.js 18+ (for `npm install -g openclaw`)
- A Telegram bot token from [@BotFather](https://t.me/BotFather)
- _(Optional but recommended)_ A HuggingFace token with inference permissions

### 2. Configure secrets

```bash
cp .env.example .env
```

Edit `.env` and fill in your values:

| Variable | Where to get it |
|---|---|
| `TELEGRAM_BOT_TOKEN` | DM [@BotFather](https://t.me/BotFather) → `/newbot` |
| `HUGGINGFACE_HUB_TOKEN` | [HF Settings → Tokens](https://huggingface.co/settings/tokens/new?ownUserPermissions=inference.serverless.write&tokenType=fineGrained) — enable **Make calls to Inference Providers** |

> `.env` is gitignored and never committed.

### 3. Run setup (first time only)

```bash
chmod +x setup.sh start.sh
./setup.sh
```

This installs OpenClaw, deploys the config, and registers your Telegram bot.

### 4. Start the gateway

```bash
./start.sh
```

### 5. Pair your Telegram account

Send a DM to your bot on Telegram. It will reply with a pairing code.  
Then run:

```bash
openclaw pairing list telegram
openclaw pairing approve telegram <CODE>
```

---

## Adding the Bot to Groups

1. Add the bot to any Telegram group
2. The bot is configured with `groupPolicy: "open"` — it responds in any group it joins
3. It only replies when **@mentioned** in groups (default safe behavior)
4. To let it see all messages in a group, either:
   - Disable Privacy Mode: DM [@BotFather](https://t.me/BotFather) → `/setprivacy` → select bot → disable
   - **Or** make the bot a group admin

To check which groups the bot is in and their IDs:

```bash
openclaw logs --follow
```

---

## Configuration

All settings live in `openclaw.json`. After editing, re-run setup to redeploy:

```bash
cp openclaw.json ~/.openclaw/openclaw.json
openclaw config validate
openclaw gateway restart   # or restart start.sh
```

### Key settings

| Setting | Default | Description |
|---|---|---|
| `channels.telegram.dmPolicy` | `pairing` | Secure DMs: new users must pair first |
| `channels.telegram.groupPolicy` | `open` | Responds in any group it's added to |
| `channels.telegram.groups."*".requireMention` | `true` | Only responds when @mentioned |
| `agents.defaults.model.primary` | `huggingface/meta-llama/Llama-3.3-70B-Instruct` | Primary model |

### Locking to specific groups

To restrict the bot to only specific groups, change `groupPolicy` to `"allowlist"` and add group IDs:

```json
"channels": {
  "telegram": {
    "groupPolicy": "allowlist",
    "groupAllowFrom": ["tg:YOUR_USER_ID"],
    "groups": {
      "-1001234567890": { "requireMention": true },
      "-1009876543210": { "requireMention": false }
    }
  }
}
```

Get group IDs by checking `openclaw logs --follow` after the bot receives a message in the group.

---

## Useful Commands

```bash
openclaw status                        # Gateway, channel, and model health
openclaw channels status --probe       # Deep Telegram connectivity check
openclaw logs --follow                 # Live gateway logs (shows group IDs too)
openclaw pairing list telegram         # Pending DM pairing codes
openclaw models list --provider huggingface  # Available HuggingFace models
openclaw doctor --fix                  # Auto-repair common issues
```

---

## Models

OpenClaw is configured with a HuggingFace fallback chain:

| Priority | Model | HF Ref |
|---|---|---|
| 1 (primary) | Llama 3.3 70B Instruct | `huggingface/meta-llama/Llama-3.3-70B-Instruct` |
| 2 (fallback) | DeepSeek R1 | `huggingface/deepseek-ai/DeepSeek-R1` |
| 3 (fallback) | Qwen3 32B | `huggingface/Qwen/Qwen3-32B` |

You can change the primary model in `openclaw.json` under `agents.defaults.model.primary`.  
All available models: `openclaw models list --provider huggingface`

---

## Architecture

```
Telegram ←──── grammY (long-poll) ──── OpenClaw Gateway ──── HuggingFace Inference API
                                              │
                                     ~/.openclaw/openclaw.json
                                     ~/.openclaw/workspace/
```

OpenClaw version: `2026.5.26`  
Docs: [docs.openclaw.ai](https://docs.openclaw.ai)
