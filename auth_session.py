"""
Run this ONCE to authenticate Telethon and save the session file.
After this, all eval scripts run without prompting for a code.

  python auth_session.py
"""
import os, asyncio
from dotenv import load_dotenv
from telethon import TelegramClient

load_dotenv()
API_ID   = int(os.environ.get("api_app_id") or os.environ["API_ID"])
API_HASH = os.environ.get("api_app_hash") or os.environ["API_HASH"]
PHONE    = os.environ["PHONE"]

async def main():
    client = TelegramClient("patient_session", API_ID, API_HASH)
    await client.start(phone=PHONE)
    me = await client.get_me()
    print(f"\n✅ Logged in as {me.first_name} (@{me.username})")
    print("Session saved to patient_session.session — all scripts will reuse it.\n")
    await client.disconnect()

asyncio.run(main())
