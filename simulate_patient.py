"""
Patient simulator — runs one or more personas, with optional multi-session arc mode.

Single session (default):
  python simulate_patient.py -p yotam              # fresh wave, session 1
  python simulate_patient.py -p yotam --session 2  # continue arc, session 2
  python simulate_patient.py -p rina,yotam         # both personas simultaneously

Full arc (runs all sessions sequentially, no human intervention needed):
  python simulate_patient.py -p yotam --arc
  python simulate_patient.py -p all --arc

Resume mid-thread (debug):
  python simulate_patient.py -p rina --resume

Safety red-team probes (loads safety_probes.json):
  python simulate_patient.py --safety -p all                  # all probes whose topic_id is set
  python simulate_patient.py --safety -p t1-medication        # one specific probe
"""

import argparse
import asyncio
import json
import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv
from huggingface_hub import InferenceClient
from telethon import TelegramClient, events
from telethon.tl.types import PeerChannel

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ── credentials ───────────────────────────────────────────────────────────────
API_ID: int = int(os.environ.get("api_app_id") or os.environ["API_ID"])
API_HASH: str = os.environ.get("api_app_hash") or os.environ["API_HASH"]
PHONE: str = os.environ["PHONE"]
HF_TOKEN: str = os.environ["HF_TOKEN"]
HF_MODEL: str = os.getenv("HF_MODEL", "Qwen/Qwen2.5-72B-Instruct")
TARGET_BOT: str = os.getenv("SIMULATOR_BOT", "vital_lifestyle_bot").lstrip("@")
MAX_TURNS: int = int(os.getenv("SIMULATOR_MAX_TURNS", "4"))
CONTEXT_LIMIT: int = int(os.getenv("SIMULATOR_CONTEXT_MESSAGES", "6"))
ARC_SESSION_DELAY: int = int(os.getenv("ARC_SESSION_DELAY", "3"))  # seconds between sessions in arc mode

_raw_chat = os.environ["ALLOWED_CHAT_IDS"].split(",")[0].strip()
TARGET_CHANNEL_ID: int = int(_raw_chat.lstrip("-100").lstrip("-"))

hf = InferenceClient(token=HF_TOKEN)


# ── per-scenario isolated runner ──────────────────────────────────────────────
@dataclass
class ScenarioRunner:
    topic_id: int
    name: str
    system_prompt: str
    opening_prompt: str
    test_objective: str
    leak_terms: list[str] = field(default_factory=list)
    sessions: list[dict] = field(default_factory=list)   # arc session configs
    resume: bool = False
    direct_opening: str = ""        # safety probe: send this verbatim instead of LLM-generated
    max_turns_override: int = 0     # safety probe: per-probe turn cap (0 = use env MAX_TURNS)
    # runtime state — reset between arc sessions
    session: int = 1
    history: list[dict] = field(default_factory=list)
    turn_count: int = 0
    done: bool = False

    _CLOSING_WORDS = ["לילה טוב", "שבוע טוב", "בהצלחה", "נתראה", "bye", "good night", "goodbye", "shalom"]

    # ── helpers ───────────────────────────────────────────────────────────────

    def in_topic(self, msg) -> bool:
        rt = msg.reply_to
        if rt is None:
            return False
        top = getattr(rt, "reply_to_top_id", None)
        mid = getattr(rt, "reply_to_msg_id", None)
        return top == self.topic_id or mid == self.topic_id

    def _clean(self, text: str) -> str:
        text = re.sub(r'[一-鿿　-〿＀-￯]+', '', text)
        lines = [l for l in text.splitlines() if not re.match(r'^[A-Za-z].{10,}[:/]', l)]
        return '\n'.join(lines).strip()

    def _is_sane(self, text: str) -> bool:
        if not text:
            return False
        hebrew = sum(1 for c in text if 'א' <= c <= 'ת')
        alpha = sum(1 for c in text if c.isalpha())
        return alpha > 0 and (hebrew / alpha) >= 0.40

    def _is_closing(self, text: str) -> bool:
        t = text.lower()
        return any(w in t for w in self._CLOSING_WORDS)

    def _check_leak(self, bot_text: str) -> list[str]:
        found = [term for term in self.leak_terms if term in bot_text]
        if found:
            logger.critical("🚨 ISOLATION BREACH in topic %d [%s]: Vital mentioned %s",
                            self.topic_id, self.name, found)
            logger.critical("   Offending message: %s", bot_text[:200])
        return found

    def get_session_config(self) -> dict | None:
        if not self.sessions or self.session < 1 or self.session > len(self.sessions):
            return None
        return self.sessions[self.session - 1]

    def reset_for_next_session(self) -> None:
        """Reset runtime state for the next arc session."""
        self.session += 1
        self.history = []
        self.turn_count = 0
        self.done = False

    # ── LLM calls ─────────────────────────────────────────────────────────────

    async def _llm(self, messages: list[dict], max_tokens: int = 160, temperature: float = 0.8) -> str:
        for attempt in range(3):
            result = hf.chat_completion(
                model=HF_MODEL,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            text = self._clean(result.choices[0].message.content.strip())
            if self._is_sane(text):
                return text
            logger.warning("[%s] attempt %d garbage: %s", self.name, attempt + 1, text[:80])
        logger.error("[%s] all attempts failed — using fallback", self.name)
        return "יש לי עוד שאלה בנושא."

    async def generate_opening(self) -> str:
        """Session 1: fresh opening, no history."""
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user",   "content": self.opening_prompt},
        ]
        text = await self._llm(messages, max_tokens=120, temperature=0.9)
        logger.info("[%s] Generated opening: %s", self.name, text)
        return text

    async def generate_session_opening(self) -> str:
        """Session N>1: opening that builds naturally on previous sessions."""
        cfg = self.get_session_config()
        if not cfg:
            return await self.generate_opening()

        day = cfg.get("day", self.session * 3)
        days_left = cfg.get("days_to_meeting")
        context = cfg.get("session_context", "")
        op_prompt = cfg.get("opening_prompt", self.opening_prompt)

        time_note = f" | {days_left} ימים לפני הפגישה" if days_left is not None else ""
        augmented_system = (
            f"{self.system_prompt}\n\n"
            f"[סשן {self.session} מתוך {len(self.sessions)} | יום {day}{time_note}]\n"
            f"{context}"
        )

        messages = [
            {"role": "system", "content": augmented_system},
            *self.history,   # full history from all previous sessions
            {"role": "user",  "content": op_prompt},
        ]
        text = await self._llm(messages, max_tokens=150, temperature=0.85)
        logger.info("[%s] Session %d opening: %s", self.name, self.session, text)
        return text

    async def generate_reply(self, bot_text: str, force_continue: bool = False) -> str:
        """Generate the persona's next reply."""
        user_content = bot_text
        if force_continue:
            user_content += "\n\n[המשך לנושא הבא שלך — אל תגיב לפרידה]"

        cfg = self.get_session_config()
        if cfg:
            day = cfg.get("day", self.session * 3)
            days_left = cfg.get("days_to_meeting")
            time_note = f" | {days_left} ימים לפני הפגישה" if days_left is not None else ""
            augmented_system = (
                f"{self.system_prompt}\n\n"
                f"[סשן {self.session} | יום {day}{time_note}]\n"
                f"{cfg.get('session_context', '')}"
            )
        else:
            augmented_system = self.system_prompt

        self.history.append({"role": "user", "content": bot_text})
        messages = (
            [{"role": "system", "content": augmented_system}]
            + self.history[:-1]
            + [{"role": "user", "content": user_content}]
        )
        text = await self._llm(messages)
        self.history.append({"role": "assistant", "content": text})
        return text

    # ── lifecycle ─────────────────────────────────────────────────────────────

    async def load_context(self, client, channel, me, limit: int | None = None) -> str | None:
        """Load recent topic messages into history. Returns last bot text if bot spoke last."""
        effective_limit = limit or CONTEXT_LIMIT
        msgs = []
        async for msg in client.iter_messages(channel, reply_to=self.topic_id, limit=effective_limit):
            if msg.text:
                msgs.append(msg)
        msgs.reverse()
        if not msgs:
            return None

        last_bot_msg = None
        for msg in msgs:
            sender = await msg.get_sender()
            if not sender:
                continue
            username = (getattr(sender, "username", "") or "").lower()
            if sender.id == me.id:
                self.history.append({"role": "assistant", "content": msg.text})
            elif username == TARGET_BOT.lower():
                self.history.append({"role": "user", "content": msg.text})
                last_bot_msg = msg.text

        logger.info("[%s] Loaded %d messages as context (session %d)", self.name, len(self.history), self.session)
        if self.history and self.history[-1]["role"] == "user":
            return last_bot_msg
        return None

    async def kickoff(self, client, channel, me) -> None:
        """Start this session. Session 1 = fresh; Session N>1 = loads history, continues arc."""
        if self.session > 1:
            # Load full conversation history from all previous sessions
            await self.load_context(client, channel, me, limit=80)
            opening = await self.generate_session_opening()
            self.history.append({"role": "assistant", "content": opening})
            sent = await client.send_message(channel, opening, reply_to=self.topic_id)
            logger.info("[%s] Session %d sent (id=%d)", self.name, self.session, sent.id)
            return

        # Session 1
        if self.resume:
            pending = await self.load_context(client, channel, me)
            if pending and not self._is_closing(pending):
                logger.info("[%s] Resuming from: %s", self.name, pending[:80])
                await asyncio.sleep(2)
                reply = await self.generate_reply(pending)
                logger.info("[%s] → %s", self.name, reply)
                await client.send_message(channel, reply, reply_to=self.topic_id)
                return
            else:
                logger.info("[%s] Nothing useful to resume — starting fresh", self.name)
                self.history.clear()

        # Safety probes use a verbatim opening (deterministic test surface).
        # Persona scenarios generate the opening with the LLM for natural variation.
        if self.direct_opening:
            opening = self.direct_opening
            logger.info("[%s] Direct opening (safety probe): %s", self.name, opening[:120])
        else:
            opening = await self.generate_opening()
        self.history = [{"role": "assistant", "content": opening}]
        sent = await client.send_message(channel, opening, reply_to=self.topic_id)
        logger.info("[%s] Fresh wave sent (id=%d)", self.name, sent.id)

    async def handle(self, client, channel, msg) -> None:
        """Handle an incoming bot message for this topic."""
        if self.done:
            return

        self.turn_count += 1
        bot_text = msg.text or ""
        logger.info("[%s] s%d t%d ← %s", self.name, self.session, self.turn_count, bot_text[:120])

        effective_max = self.max_turns_override or MAX_TURNS
        if self.turn_count >= effective_max:
            logger.info("[%s] Max turns reached for session %d (cap=%d). Done.",
                        self.name, self.session, effective_max)
            self.done = True
            return

        self._check_leak(bot_text)

        closing = self._is_closing(bot_text)
        if closing:
            logger.info("[%s] Vital closing — nudging persona to continue", self.name)

        await asyncio.sleep(3)
        reply = await self.generate_reply(bot_text, force_continue=closing)
        logger.info("[%s] s%d t%d → %s", self.name, self.session, self.turn_count, reply)
        await client.send_message(channel, reply, reply_to=msg.id)


# ── scenario loading ───────────────────────────────────────────────────────────
def load_scenarios(names: list[str], resume: bool = False, session: int = 1) -> list[ScenarioRunner]:
    path = Path(__file__).parent / "scenarios.json"
    raw: dict = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}

    runners = []
    for topic_id_str, cfg in raw.items():
        if "all" not in names and cfg.get("name", "").lower() not in names:
            continue
        runners.append(ScenarioRunner(
            topic_id=int(topic_id_str),
            name=cfg["name"],
            system_prompt=cfg["system_prompt"],
            opening_prompt=cfg.get("opening_prompt", "פתח את השיחה בשאלה אחת קצרה ואמיתית."),
            test_objective=cfg.get("test_objective", ""),
            leak_terms=cfg.get("leak_terms", []),
            sessions=cfg.get("sessions", []),
            resume=resume,
            session=session,
        ))

    if not runners:
        raise SystemExit(f"No matching scenarios for: {names}. Check scenarios.json.")
    return runners


def load_safety_probes(names: list[str]) -> list[ScenarioRunner]:
    """Load safety red-team probes from safety_probes.json.
    Each probe is a single-shot test of one Vital failure mode.
    Probes with topic_id=null are skipped (user hasn't created the topic yet).
    """
    path = Path(__file__).parent / "safety_probes.json"
    raw: dict = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}

    runners = []
    skipped: list[str] = []
    for probe_name, cfg in raw.items():
        if probe_name.startswith("_"):
            continue
        if "all" not in names and probe_name.lower() not in names:
            continue
        topic_id = cfg.get("topic_id")
        if topic_id is None:
            skipped.append(probe_name)
            continue
        runners.append(ScenarioRunner(
            topic_id=int(topic_id),
            name=probe_name,
            system_prompt=cfg.get("system_prompt", ""),
            opening_prompt=cfg.get("opening_prompt", "המשך באופן טבעי."),
            test_objective=cfg.get("expected_behavior", ""),
            leak_terms=[],
            sessions=[],
            resume=False,
            session=1,
            direct_opening=cfg.get("direct_opening", ""),
            max_turns_override=int(cfg.get("max_turns", 0)),
        ))

    if skipped:
        logger.warning("⚠️  Skipped %d probe(s) with topic_id=null: %s",
                       len(skipped), ", ".join(skipped))
        logger.warning("    Create forum topics in Telegram, then fill topic_id in safety_probes.json.")

    if not runners:
        raise SystemExit(
            f"No safety probes to run. Either none matched '{names}', "
            "or all matching probes have topic_id=null. "
            "Edit safety_probes.json with real topic IDs."
        )
    return runners


# ── single-session runner ──────────────────────────────────────────────────────
async def run_session(runners: list[ScenarioRunner], client, channel, me) -> None:
    """Run one session across all runners and return when all are done."""
    done_event = asyncio.Event()

    await asyncio.gather(*[r.kickoff(client, channel, me) for r in runners])

    runner_map = {r.topic_id: r for r in runners}

    @client.on(events.NewMessage(chats=channel))
    async def on_message(event):
        msg = event.message
        sender = await event.get_sender()
        if not sender:
            return
        if (getattr(sender, "username", "") or "").lower() != TARGET_BOT.lower():
            return

        for topic_id, runner in runner_map.items():
            if runner.in_topic(msg):
                await runner.handle(client, channel, msg)
                break

        if all(r.done for r in runners):
            done_event.set()

    await done_event.wait()
    client.remove_event_handler(on_message)


# ── main ──────────────────────────────────────────────────────────────────────
async def main(runners: list[ScenarioRunner], arc_mode: bool = False, arc_max_sessions: int = 0) -> None:
    client = TelegramClient("patient_session", API_ID, API_HASH)
    await client.start(phone=PHONE)

    me = await client.get_me()
    logger.info("Logged in as %s (@%s)", me.first_name, me.username)

    channel = await client.get_entity(PeerChannel(TARGET_CHANNEL_ID))
    logger.info("Group: %s | Personas: %s | mode: %s",
                channel.title,
                [r.name for r in runners],
                "arc" if arc_mode else (f"session {runners[0].session}" if not runners[0].resume else "resume"))

    for r in runners:
        logger.info("[%s] TESTING: %s", r.name, r.test_objective)

    if arc_mode:
        # Determine max sessions across all runners (capped by --max-sessions if set)
        max_sessions = max(
            (len(r.sessions) for r in runners if r.sessions),
            default=1
        )
        if arc_max_sessions:
            max_sessions = min(max_sessions, arc_max_sessions)
        logger.info("Arc mode: %d sessions total", max_sessions)

        for session_num in range(1, max_sessions + 1):
            # Only include runners that have this session
            active = [r for r in runners
                      if not r.sessions or session_num <= len(r.sessions)]
            if not active:
                break

            for r in active:
                r.session = session_num
                r.turn_count = 0
                r.done = False
                r.history = []

            logger.info("═══ Session %d / %d ═══", session_num, max_sessions)
            await run_session(active, client, channel, me)
            logger.info("Session %d complete.", session_num)

            if session_num < max_sessions:
                logger.info("Pausing %ds before next session…", ARC_SESSION_DELAY)
                await asyncio.sleep(ARC_SESSION_DELAY)

        logger.info("Arc complete. All sessions done.")
    else:
        # Single session
        done_event = asyncio.Event()
        await asyncio.gather(*[r.kickoff(client, channel, me) for r in runners])

        runner_map = {r.topic_id: r for r in runners}

        @client.on(events.NewMessage(chats=channel))
        async def on_message(event):
            msg = event.message
            sender = await event.get_sender()
            if not sender:
                return
            if (getattr(sender, "username", "") or "").lower() != TARGET_BOT.lower():
                return

            for topic_id, runner in runner_map.items():
                if runner.in_topic(msg):
                    await runner.handle(client, channel, msg)
                    break

            if all(r.done for r in runners):
                done_event.set()

        logger.info("Listening for @%s across %d topic(s)…", TARGET_BOT, len(runners))
        await done_event.wait()

    logger.info("Disconnecting.")
    await client.disconnect()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Vital bot alignment simulator")
    parser.add_argument("-p", "--personas", required=True,
                        help="Comma-separated names or 'all'. E.g. -p rina,yotam (personas) or -p t1-medication,t2-extended-fast (probes)")
    parser.add_argument("--session", type=int, default=1,
                        help="Which arc session to run (default: 1). Ignored if --arc is set.")
    parser.add_argument("--arc", action="store_true",
                        help="Run all arc sessions sequentially (uses sessions[] in scenarios.json)")
    parser.add_argument("--max-sessions", type=int, default=0,
                        help="Cap number of arc sessions (default: run all)")
    parser.add_argument("--resume", action="store_true",
                        help="Resume from last bot message instead of starting a fresh wave")
    parser.add_argument("--safety", action="store_true",
                        help="Load probes from safety_probes.json (red-team mode). Uses direct_opening, per-probe turn caps.")
    args = parser.parse_args()

    selected = [p.strip().lower() for p in args.personas.split(",")]
    if args.safety:
        if args.arc:
            raise SystemExit("--arc is not supported with --safety (probes are single-shot).")
        runners = load_safety_probes(selected)
    else:
        runners = load_scenarios(selected, resume=args.resume, session=args.session)
    asyncio.run(main(runners, arc_mode=args.arc, arc_max_sessions=args.max_sessions))
