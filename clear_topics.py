"""
Delete all messages from persona topics (and optionally security probe topics).

Usage:
    python clear_topics.py            # clear persona topics only (30, 566, 11, 1016)
    python clear_topics.py --all      # also clear security probe topics (read from safety_probes.json)
    python clear_topics.py --safety   # clear security probe topics ONLY
"""
import asyncio
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from telethon import TelegramClient

load_dotenv()
API_ID   = int(os.environ.get("api_app_id") or os.environ["API_ID"])
API_HASH = os.environ.get("api_app_hash") or os.environ["API_HASH"]
PHONE    = os.environ["PHONE"]
raw_chat = os.environ["ALLOWED_CHAT_IDS"].split(",")[0].strip()
CHANNEL_ID = int(raw_chat.lstrip("-100").lstrip("-"))

PERSONA_TOPIC_IDS = [30, 566, 11, 1016]


def _load_security_topic_ids() -> list[int]:
    path = Path(__file__).parent / "safety_probes.json"
    if not path.exists():
        return []
    probes = json.loads(path.read_text(encoding="utf-8"))
    return [
        int(cfg["topic_id"])
        for name, cfg in probes.items()
        if not name.startswith("_") and cfg.get("topic_id") is not None
    ]


async def clear_topics(topic_ids: list[int]) -> None:
    async with TelegramClient("patient_session", API_ID, API_HASH) as client:
        await client.start(phone=PHONE)
        entity = await client.get_entity(CHANNEL_ID)
        for tid in topic_ids:
            msgs = await client.get_messages(entity, limit=200, reply_to=tid)
            ids = [m.id for m in msgs]
            if ids:
                await client.delete_messages(entity, ids)
                print(f"Deleted {len(ids)} messages from topic {tid}")
            else:
                print(f"Topic {tid} already clean")


if __name__ == "__main__":
    args = set(sys.argv[1:])
    safety_only = "--safety" in args
    include_safety = "--all" in args or safety_only

    if safety_only:
        topic_ids = _load_security_topic_ids()
        if not topic_ids:
            print("No security probe topics found in safety_probes.json. Run create_security_topics.py first.")
            sys.exit(0)
        print(f"Clearing {len(topic_ids)} security topic(s)...")
    elif include_safety:
        security_ids = _load_security_topic_ids()
        topic_ids = PERSONA_TOPIC_IDS + security_ids
        print(f"Clearing {len(PERSONA_TOPIC_IDS)} persona topic(s) + {len(security_ids)} security topic(s)...")
    else:
        topic_ids = PERSONA_TOPIC_IDS
        print(f"Clearing {len(PERSONA_TOPIC_IDS)} persona topic(s)...")

    asyncio.run(clear_topics(topic_ids))
