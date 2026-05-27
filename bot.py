"""
Telegram group bot that role-plays a different persona in each topic thread.
Powered by HuggingFace Inference API.

Setup:
  cp .env.example .env   # fill in your tokens
  pip install -r requirements.txt
  python bot.py

Commands (usable by group admins):
  /setpersona <description>  – set the persona for the current topic
  /getpersona                – show the active persona for the current topic
  /clearhistory              – wipe conversation history for the current topic
"""

import json
import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from huggingface_hub import InferenceClient
from telegram import Message, Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

BOT_TOKEN: str = os.environ["BOT_TOKEN"]
HF_TOKEN: str = os.environ["HF_TOKEN"]
HF_MODEL: str = os.getenv("HF_MODEL", "mistralai/Mistral-7B-Instruct-v0.3")
# How many recent exchanges to keep in context per topic
HISTORY_LIMIT: int = int(os.getenv("HISTORY_LIMIT", "12"))
# Max tokens the model may generate per reply
MAX_TOKENS: int = int(os.getenv("MAX_TOKENS", "350"))

PERSONAS_FILE = Path("personas.json")

# Persisted state: str(topic_id) -> {"name": str, "persona": str, "history": list}
state: dict[str, dict] = {}


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def load_state() -> None:
    global state
    if PERSONAS_FILE.exists():
        state = json.loads(PERSONAS_FILE.read_text())


def save_state() -> None:
    PERSONAS_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False))


# ---------------------------------------------------------------------------
# Topic helpers
# ---------------------------------------------------------------------------

def topic_key(message: Message) -> str:
    # message_thread_id is None for the main (non-forum) chat → use "0"
    return str(message.message_thread_id or 0)


def get_topic(key: str, name: str = "") -> dict:
    """Return the topic entry, creating a default one if absent."""
    if key not in state:
        persona = _default_persona(name or f"topic-{key}")
        state[key] = {"name": name, "persona": persona, "history": []}
        save_state()
    return state[key]


def _default_persona(topic_name: str) -> str:
    return (
        f"You are a real person participating in a group chat. "
        f"The current discussion topic is '{topic_name}'. "
        f"Adapt your personality, expertise, and tone to fit the topic naturally. "
        f"Be conversational, opinionated, and realistic — avoid sounding like an AI assistant. "
        f"Keep replies short and casual unless the conversation calls for detail."
    )


# ---------------------------------------------------------------------------
# AI response
# ---------------------------------------------------------------------------

async def generate_reply(persona: str, history: list, user_text: str) -> str:
    client = InferenceClient(token=HF_TOKEN)
    messages = [{"role": "system", "content": persona}]
    messages.extend(history[-(HISTORY_LIMIT * 2):])
    messages.append({"role": "user", "content": user_text})

    result = client.chat_completion(
        model=HF_MODEL,
        messages=messages,
        max_tokens=MAX_TOKENS,
        temperature=0.85,
    )
    return result.choices[0].message.content.strip()


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if not message or not message.text:
        return

    bot_user = await context.bot.get_me()
    text = message.text.strip()

    # Respond only when mentioned or when replying directly to the bot
    mentioned = f"@{bot_user.username}" in text
    replied_to_bot = (
        message.reply_to_message is not None
        and message.reply_to_message.from_user is not None
        and message.reply_to_message.from_user.id == bot_user.id
    )

    if not (mentioned or replied_to_bot):
        return

    # Strip the mention so it doesn't end up in the prompt
    clean = text.replace(f"@{bot_user.username}", "").strip() or "Hey!"

    key = topic_key(message)
    data = get_topic(key)

    try:
        await context.bot.send_chat_action(
            chat_id=message.chat_id,
            action="typing",
            message_thread_id=message.message_thread_id,
        )

        reply = await generate_reply(data["persona"], data["history"], clean)

        data["history"].append({"role": "user", "content": clean})
        data["history"].append({"role": "assistant", "content": reply})
        save_state()

        await message.reply_text(reply)

    except Exception:
        logger.exception("Failed to generate reply")
        await message.reply_text("Having trouble responding right now — try again in a moment.")


async def on_topic_created(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Capture the topic name when a new forum topic is opened."""
    message = update.effective_message
    if not message or not message.forum_topic_created:
        return

    key = topic_key(message)
    name = message.forum_topic_created.name
    logger.info("New topic '%s' (key=%s)", name, key)

    # Register the topic with its real name
    if key not in state:
        state[key] = {"name": name, "persona": _default_persona(name), "history": []}
    else:
        state[key]["name"] = name
    save_state()


async def cmd_set_persona(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if not context.args:
        await message.reply_text("Usage: /setpersona <persona description>")
        return

    persona = " ".join(context.args)
    key = topic_key(message)
    entry = get_topic(key)
    entry["persona"] = persona
    entry["history"] = []  # fresh start with new persona
    save_state()
    await message.reply_text(f"Persona updated. History cleared.\n\n{persona[:200]}")


async def cmd_get_persona(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    key = topic_key(message)
    data = state.get(key)
    if not data:
        await message.reply_text("No persona set for this topic yet.")
    else:
        await message.reply_text(f"Current persona for this topic:\n\n{data['persona']}")


async def cmd_clear_history(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    key = topic_key(message)
    if key in state:
        state[key]["history"] = []
        save_state()
    await message.reply_text("Conversation history cleared for this topic.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    load_state()

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("setpersona", cmd_set_persona))
    app.add_handler(CommandHandler("getpersona", cmd_get_persona))
    app.add_handler(CommandHandler("clearhistory", cmd_clear_history))

    # Capture new topic creation to record the topic name
    app.add_handler(
        MessageHandler(filters.StatusUpdate.FORUM_TOPIC_CREATED, on_topic_created)
    )

    # Main message handler
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_message))

    logger.info("Bot running — polling for updates…")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
