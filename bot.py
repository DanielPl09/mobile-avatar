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
import re
import time
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
HF_MODEL: str = os.getenv("HF_MODEL", "Qwen/Qwen3-14B")
HISTORY_LIMIT: int = int(os.getenv("HISTORY_LIMIT", "12"))
MAX_TOKENS: int = int(os.getenv("MAX_TOKENS", "350"))

# Comma-separated list of chat IDs the bot will respond in.
# Leave empty to allow any group.
# Find your group's ID by adding @userinfobot to the group.
_raw_allowed = os.getenv("ALLOWED_CHAT_IDS", "")
ALLOWED_CHAT_IDS: set[int] = (
    {int(cid.strip()) for cid in _raw_allowed.split(",") if cid.strip()}
    if _raw_allowed.strip()
    else set()
)

# Bot-to-bot back-and-forth settings
BOT_EXCHANGE_LIMIT: int = int(os.getenv("BOT_EXCHANGE_LIMIT", "6"))
BOT_COOLDOWN: int = int(os.getenv("BOT_COOLDOWN", "60"))

PERSONAS_FILE = Path("personas.json")

# Persisted state: str(topic_id) -> {"name": str, "persona": str, "history": list}
state: dict[str, dict] = {}

# In-memory bot-exchange counters: str(topic_id) -> {"count": int, "paused_at": float|None}
bot_exchange: dict[str, dict] = {}


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
    return str(message.message_thread_id or 0)


def get_topic(key: str, name: str = "") -> dict:
    if key not in state:
        persona = _default_persona(name or f"topic-{key}")
        state[key] = {"name": name, "persona": persona, "history": []}
        save_state()
    return state[key]


VITAL_PERSONA = """אתה ויטל — בוט תזונה של קופת חולים, שומר על קשר עם מטופלים בין פגישות עם הדיאטנית.

תפקידך:
- לעזור למטופלים להבין עקרונות תזונה כלליים ולעשות שינויים קטנים ומעשיים
- להכין אותם לפגישה עם הדיאטנית שלהם
- לתת תמיכה רגשית וליווי בין הפגישות

גבולות ברורים — לא מתפשר עליהם:
- אסור לתת הנחיות לגבי תרופות, מינונים, או שינויי טיפול — תמיד מפנה לרופא
- אסור להמליץ על דיאטות קיצוניות: צום ממושך (OMAD, 24+ שעות), קטוגנית כ"ריפוי", הגבלה קלורית חמורה
- כשמטופל מזכיר תסמין פיזי (סחרחורת, כאב, חולשה) — חייב לציין שזה דורש בדיקת רופא, לא הסבר תזונתי בלבד
- לא עוסק בנושאים שאינם תזונה ובריאות — אם שואלים על דברים אחרים (טכנולוגיה, חדשות וכו') — מסיט בעדינות לנושא
- לא מתכנן תפריטים מלאים — זה עבודת הדיאטנית

מה כן אפשרי:
- להסביר עקרונות כמו: מדד גליקמי, חלבון, סיבים, שעות אכילה
- להציע החלפות פשוטות ("במקום לחם לבן — לחם מלא")
- לתת טיפ אחד מעשי קטן לפעולה מיידית
- לעזור למטופל לנסח מה לשאול את הדיאטנית

סגנון תגובה — חשוב מאוד:
- עברית בלבד
- קצר: 2-3 משפטים מקסימום. ארוך יותר רק אם נדרש הסבר רפואי בטיחותי
- סגנון וואטסאפ — ישיר, חם, לא פורמלי. ללא כותרות, ללא רשימות ממוספרות, ללא הדגשות בולד
- שאל שאלה אחת ומחכה לתשובה לפני שאתה ממשיך עם עצות
- אל תסיים הודעות ב"לילה טוב" או פרידות — השיחה פתוחה"""


def _default_persona(topic_name: str) -> str:
    return VITAL_PERSONA


# ---------------------------------------------------------------------------
# Bot-exchange throttle
# ---------------------------------------------------------------------------

def should_reply_to_bot(key: str) -> bool:
    """
    Return True if we are allowed to reply to another bot right now.
    Increments the exchange counter; resets it after the cooldown period.
    """
    entry = bot_exchange.setdefault(key, {"count": 0, "paused_at": None})

    # If currently in cooldown, check whether it has expired
    if entry["paused_at"] is not None:
        elapsed = time.monotonic() - entry["paused_at"]
        if elapsed < BOT_COOLDOWN:
            logger.info(
                "topic=%s bot-exchange cooldown: %ds left",
                key,
                int(BOT_COOLDOWN - elapsed),
            )
            return False
        # Cooldown expired — reset
        entry["count"] = 0
        entry["paused_at"] = None

    entry["count"] += 1

    if entry["count"] > BOT_EXCHANGE_LIMIT:
        logger.info("topic=%s bot-exchange limit hit, entering cooldown", key)
        entry["paused_at"] = time.monotonic()
        return False

    return True


def reset_bot_exchange(key: str) -> None:
    """Call when a human sends a message — resets the exchange counter."""
    bot_exchange[key] = {"count": 0, "paused_at": None}


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
    text = result.choices[0].message.content.strip()
    # Strip Qwen3 thinking blocks if present
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    return text


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

def _allowed(chat_id: int) -> bool:
    return not ALLOWED_CHAT_IDS or chat_id in ALLOWED_CHAT_IDS


async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if not message or not message.text:
        return

    if not _allowed(message.chat_id):
        return

    sender = message.from_user
    if not sender:
        return

    bot_user = await context.bot.get_me()

    # Ignore our own messages
    if sender.id == bot_user.id:
        return

    text = message.text.strip()
    key = topic_key(message)
    sender_is_bot = sender.is_bot

    # --- Decide whether to respond ---
    if sender_is_bot:
        # Another bot sent this message — engage in back-and-forth if allowed
        if not should_reply_to_bot(key):
            return
        clean = text
        logger.info("Replying to bot '%s' in topic %s", sender.username, key)
    else:
        # Human message: reset exchange counter, then check trigger conditions
        reset_bot_exchange(key)

        mentioned = f"@{bot_user.username}" in text
        replied_to_bot = (
            message.reply_to_message is not None
            and message.reply_to_message.from_user is not None
            and message.reply_to_message.from_user.id == bot_user.id
        )

        if not (mentioned or replied_to_bot):
            return

        clean = text.replace(f"@{bot_user.username}", "").strip() or "Hey!"

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
    message = update.effective_message
    if not message or not message.forum_topic_created:
        return

    if not _allowed(message.chat_id):
        return

    key = topic_key(message)
    name = message.forum_topic_created.name
    logger.info("New topic '%s' (key=%s)", name, key)

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
    entry["history"] = []
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

    app.add_handler(
        MessageHandler(filters.StatusUpdate.FORUM_TOPIC_CREATED, on_topic_created)
    )

    # Handle ALL text messages (including from other bots) except commands
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, on_message)
    )

    logger.info("Bot running — polling for updates…")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
