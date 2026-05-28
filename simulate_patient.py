"""
Human-side patient simulator using Telethon (user account, not bot).
Sends and receives messages in ONE specific supergroup topic only.
Listens for replies from the target bot and responds as Rina the patient.

Usage:
  pip install -r requirements.txt
  python simulate_patient.py

First run will ask for your Telegram auth code.
Session is saved to patient_session.session so subsequent runs skip login.
"""

import asyncio
import logging
import os

from dotenv import load_dotenv
from huggingface_hub import InferenceClient
from telethon import TelegramClient, events
from telethon.tl.functions.channels import GetFullChannelRequest

load_dotenv()

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
)
logger = logging.getLogger(__name__)

# ── credentials ──────────────────────────────────────────────────────────────
API_ID: int = int(os.environ.get("api_app_id") or os.environ["API_ID"])
API_HASH: str = os.environ.get("api_app_hash") or os.environ["API_HASH"]
PHONE: str = os.environ["PHONE"]
HF_TOKEN: str = os.environ["HF_TOKEN"]
HF_MODEL: str = os.getenv("HF_MODEL", "HuggingFaceH4/zephyr-7b-beta")

# ── target: ONE supergroup, ONE topic, ONE bot ────────────────────────────────
# chat_id from ALLOWED_CHAT_IDS is like -1003943200370;
# Telethon needs the raw channel id (strip -100 prefix).
_raw_chat = os.environ["ALLOWED_CHAT_IDS"].split(",")[0].strip()
TARGET_CHANNEL_ID: int = int(_raw_chat.lstrip("-100").lstrip("-"))  # e.g. 3943200370  # noqa
TARGET_TOPIC_ID: int = int(os.getenv("SIMULATOR_TOPIC_ID", "30"))
TARGET_BOT: str = os.getenv("SIMULATOR_BOT", "vital_lifestyle_bot").lstrip("@")
MAX_TURNS: int = int(os.getenv("SIMULATOR_MAX_TURNS", "12"))

# ── patient persona ───────────────────────────────────────────────────────────
SYSTEM_PROMPT = """\
You are Rina, a 65-year-old retired Israeli woman.
You are speaking in Hebrew with a dietitian chatbot.
Medical background: type 2 diabetes, slightly overweight, mild hypertension.
Personality: warm, a little anxious about her health, asks follow-up questions,
sometimes forgets what was already said, uses simple everyday language.
Rules:
- Always write in Hebrew only.
- Keep each reply to 2-3 short sentences.
- Be natural and conversational, not clinical.
- Do not repeat information the bot already gave you.
- Progress the conversation: ask a new follow-up question each turn."""

history: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]
turn_count: int = 0
hf = InferenceClient(token=HF_TOKEN)


async def patient_reply(bot_text: str) -> str:
    history.append({"role": "user", "content": bot_text})
    result = hf.chat_completion(
        model=HF_MODEL,
        messages=history,
        max_tokens=160,
    )
    text = result.choices[0].message.content.strip()
    history.append({"role": "assistant", "content": text})
    return text


def in_target_topic(msg) -> bool:
    """Return True only if the message belongs to TARGET_TOPIC_ID."""
    rt = msg.reply_to
    if rt is None:
        return False
    top = getattr(rt, "reply_to_top_id", None)
    mid = getattr(rt, "reply_to_msg_id", None)
    return top == TARGET_TOPIC_ID or mid == TARGET_TOPIC_ID


async def main() -> None:
    global turn_count

    client = TelegramClient("patient_session", API_ID, API_HASH)
    await client.start(phone=PHONE)

    me = await client.get_me()
    logger.info("Logged in as %s (@%s)", me.first_name, me.username)

    # Resolve the channel entity
    channel = await client.get_entity(TARGET_CHANNEL_ID)
    logger.info("Target group: %s", channel.title)

    # ── send opening message into the topic ──────────────────────────────────
    opening = (
        "שלום! אני רינה, בת 65. הרופא שלי המליץ לי לדבר עם דיאטנית. "
        "אני סובלת מסוכרת סוג 2 ומעט עודף משקל. "
        "אני מתקשה עם רמות הסוכר בבוקר – יש לך עצות לגבי ארוחת הבוקר?"
    )
    history.append({"role": "assistant", "content": opening})
    sent = await client.send_message(channel, opening, reply_to=TARGET_TOPIC_ID)
    logger.info("Opening message sent (id=%d)", sent.id)

    # ── listen for bot replies ───────────────────────────────────────────────
    @client.on(events.NewMessage(chats=channel))
    async def on_message(event):
        global turn_count
        msg = event.message

        # Strict guard: only this topic
        if not in_target_topic(msg):
            return

        # Only react to the target bot
        sender = await event.get_sender()
        if not sender:
            return
        bot_username = getattr(sender, "username", "") or ""
        if bot_username.lower() != TARGET_BOT.lower():
            return

        turn_count += 1
        logger.info("[turn %d] %s: %s", turn_count, bot_username, msg.text)

        if turn_count >= MAX_TURNS:
            logger.info("Reached max turns (%d). Stopping.", MAX_TURNS)
            await client.disconnect()
            return

        # Simulate reading + typing delay
        await asyncio.sleep(4)

        reply_text = await patient_reply(msg.text or "")
        logger.info("[turn %d] Rina: %s", turn_count, reply_text)
        await client.send_message(channel, reply_text, reply_to=msg.id)

    logger.info(
        "Listening in topic %d for @%s (max %d turns) …",
        TARGET_TOPIC_ID,
        TARGET_BOT,
        MAX_TURNS,
    )
    await client.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(main())
