"""
One-time setup: creates Telegram forum topics for all probes and scenarios that
don't yet have a topic_id, then patches the IDs back into the JSON files.

Usage:
  python setup_topics.py                  # create missing topics in both files
  python setup_topics.py --dry-run        # print what would be created, no changes
  python setup_topics.py --safety-only    # only safety_probes.json
  python setup_topics.py --scenarios-only # only scenarios.json
"""

import argparse
import asyncio
import json
import logging
import os
import random
from pathlib import Path

from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.tl.functions.channels import CreateForumTopicRequest
from telethon.tl.types import PeerChannel

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

API_ID: int = int(os.environ.get("api_app_id") or os.environ["API_ID"])
API_HASH: str = os.environ.get("api_app_hash") or os.environ["API_HASH"]
PHONE: str = os.environ["PHONE"]

_raw_chat = os.environ["ALLOWED_CHAT_IDS"].split(",")[0].strip()
TARGET_CHANNEL_ID: int = int(_raw_chat.lstrip("-100").lstrip("-"))

SAFETY_FILE = Path(__file__).parent / "safety_probes.json"
SCENARIOS_FILE = Path(__file__).parent / "scenarios.json"


def _extract_topic_id(updates) -> int | None:
    """Robustly extract the new topic's message ID from CreateForumTopicRequest response."""
    for upd in getattr(updates, "updates", []):
        mid = getattr(upd, "id", None)
        if mid is not None:
            return int(mid)
        msg = getattr(upd, "message", None)
        if msg is not None:
            mid = getattr(msg, "id", None)
            if mid is not None:
                return int(mid)
    return None


async def create_topic(client, channel, name: str) -> int | None:
    result = await client(CreateForumTopicRequest(
        channel=channel,
        title=name,
        random_id=random.randint(1, 2**31 - 1),
    ))
    topic_id = _extract_topic_id(result)
    if topic_id is None:
        logger.error("Could not extract topic_id for '%s'", name)
        return None
    logger.info("Created topic '%s' -> id=%d", name, topic_id)
    return topic_id


async def setup(dry_run: bool, do_safety: bool, do_scenarios: bool) -> None:
    client = TelegramClient("report_session", API_ID, API_HASH)
    await client.start(phone=PHONE)

    channel = await client.get_entity(PeerChannel(TARGET_CHANNEL_ID))
    logger.info("Group: %s", channel.title)

    if do_safety:
        probes = json.loads(SAFETY_FILE.read_text(encoding="utf-8"))
        changed = False
        for name, cfg in probes.items():
            if name.startswith("_"):
                continue
            if cfg.get("topic_id") is not None:
                logger.info("  [safety] %s — already has topic_id=%s, skipping", name, cfg["topic_id"])
                continue
            if dry_run:
                logger.info("  [DRY RUN] would create topic: %s", name.upper())
                continue
            topic_id = await create_topic(client, channel, name.upper())
            if topic_id is None:
                logger.error("  [safety] %s — failed to create topic, skipping", name)
                continue
            cfg["topic_id"] = topic_id
            changed = True
            await asyncio.sleep(1)  # avoid flood limits

        if changed and not dry_run:
            SAFETY_FILE.write_text(json.dumps(probes, indent=2, ensure_ascii=False), encoding="utf-8")
            logger.info("Saved updated safety_probes.json")

    if do_scenarios:
        scenarios = json.loads(SCENARIOS_FILE.read_text(encoding="utf-8"))
        # Scenarios are keyed by topic_id already — check if they exist in Telegram
        # Scenarios don't need creation (user already has these topics), but log them
        for topic_id_str, cfg in scenarios.items():
            name = cfg.get("name", topic_id_str)
            logger.info("  [scenario] %s — topic_id=%s (pre-existing, no action needed)", name, topic_id_str)

    logger.info("Setup complete.")
    await client.disconnect()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create Telegram topics for all test probes")
    parser.add_argument("--dry-run", action="store_true", help="Print what would be created without making changes")
    parser.add_argument("--safety-only", action="store_true")
    parser.add_argument("--scenarios-only", action="store_true")
    args = parser.parse_args()

    do_safety = not args.scenarios_only
    do_scenarios = not args.safety_only
    asyncio.run(setup(args.dry_run, do_safety, do_scenarios))
