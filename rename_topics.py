"""Rename Telegram forum topics to match the standard: שם, תפקיד, גיל"""
import asyncio, os, json
from pathlib import Path
from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.tl.types import PeerChannel
from telethon.tl.functions.channels import EditForumTopicRequest

load_dotenv()
API_ID   = int(os.environ.get("api_app_id") or os.environ["API_ID"])
API_HASH = os.environ.get("api_app_hash") or os.environ["API_HASH"]
PHONE    = os.environ["PHONE"]
raw_chat = os.environ["ALLOWED_CHAT_IDS"].split(",")[0].strip()
CHANNEL_ID = int(raw_chat.lstrip("-100").lstrip("-"))

scenarios = json.loads(Path("scenarios.json").read_text(encoding="utf-8"))

async def main():
    async with TelegramClient("patient_session", API_ID, API_HASH) as client:
        await client.start(phone=PHONE)
        entity = await client.get_entity(PeerChannel(CHANNEL_ID))
        for topic_id_str, cfg in scenarios.items():
            title = cfg.get("topic_title")
            if not title:
                print(f"  skip {cfg['name']} — no topic_title set")
                continue
            tid = int(topic_id_str)
            try:
                await client(EditForumTopicRequest(channel=entity, topic_id=tid, title=title))
                print(f"  OK topic {tid} renamed")
            except Exception as e:
                if "NOT_MODIFIED" in str(e):
                    print(f"  already set topic {tid}")
                else:
                    print(f"  ERROR topic {tid}: {e}")

asyncio.run(main())
