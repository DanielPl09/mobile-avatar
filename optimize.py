#!/usr/bin/env python3
"""
Vital optimization loop.

How it works per iteration:
  1. Start bot.py locally
  2. Clear topics → simulate 4 personas → run 19 safety probes → generate reports
  3. Stop bot
  4. DM @vital_lifestyle_bot to snapshot current skills (read-only)
  5. LLM reflects on reports → proposes 1-3 line additive Hebrew tweak
  6. DM @vital_lifestyle_bot with the tuning instruction (the canonical way to tune)
  7. Also patch VITAL_PERSONA in bot.py (local effect) + restart bot
  8. Quick safety recheck → revert DM + bot.py patch if safety regressed
  9. Log everything in docs/VITAL_TUNING_LOG.md

Usage:
    python optimize.py                    # 3 iterations
    python optimize.py --iterations 5
    python optimize.py --dry-run          # eval + report only, no tuning
    python optimize.py --no-manage-bot    # bot already running externally
"""

import argparse
import asyncio
import io
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from huggingface_hub import InferenceClient
from telethon import TelegramClient

load_dotenv()

# Force UTF-8 output on Windows so Hebrew doesn't crash print()
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "buffer"):
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

ROOT        = Path(__file__).parent
HF_TOKEN    = os.environ["HF_TOKEN"]
HF_MODEL    = os.getenv("HF_MODEL", "Qwen/Qwen3-32B")
TARGET_BOT  = os.getenv("SIMULATOR_BOT", "vital_lifestyle_bot").lstrip("@")
API_ID      = int(os.environ.get("api_app_id") or os.environ["API_ID"])
API_HASH    = os.environ.get("api_app_hash") or os.environ["API_HASH"]
PHONE       = os.environ["PHONE"]
SESSION     = str(ROOT / "patient_session")

ALIGN_REPORT  = ROOT / "reports" / "alignment_report.md"
SAFETY_REPORT = ROOT / "reports" / "safety_report.md"
TUNING_LOG    = ROOT / "docs" / "VITAL_TUNING_LOG.md"
SNAP_DIR      = ROOT / "docs" / "skill_snapshots"


# ── bot process management ────────────────────────────────────────────────────

def start_bot() -> subprocess.Popen:
    proc = subprocess.Popen(
        [sys.executable, str(ROOT / "bot.py")],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(5)  # wait for Telegram connection
    print(f"[bot] started (pid {proc.pid})")
    return proc


def stop_bot(proc: subprocess.Popen) -> None:
    proc.terminate()
    try:
        proc.wait(timeout=6)
    except subprocess.TimeoutExpired:
        proc.kill()
    print("[bot] stopped")


# ── subprocess step runner ────────────────────────────────────────────────────

def run_step(script: str, *extra: str) -> bool:
    cmd = [sys.executable, str(ROOT / script)] + list(extra)
    print("  > " + " ".join(str(a) for a in cmd[1:]))
    result = subprocess.run(
        cmd, cwd=ROOT,
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    out = (result.stdout + result.stderr).strip()
    for line in out.splitlines()[-12:]:
        try:
            print("    " + line)
        except Exception:
            print("    " + line.encode("ascii", errors="replace").decode())
    return result.returncode == 0


def copy_session() -> None:
    shutil.copy2(ROOT / "patient_session.session", ROOT / "report_session.session")


# ── Telegram DM helpers (Telethon) ────────────────────────────────────────────

async def _dm(message: str, wait_secs: int = 10) -> str:
    """Send a DM to @vital_lifestyle_bot, wait, return its reply."""
    async with TelegramClient(SESSION, API_ID, API_HASH) as client:
        await client.start(phone=PHONE)
        await client.send_message(TARGET_BOT, message)
        await asyncio.sleep(wait_secs)
        msgs = await client.get_messages(TARGET_BOT, limit=5)
        me = await client.get_me()
        for msg in msgs:
            if msg.sender_id != me.id and msg.text:
                return msg.text.strip()
    return ""


def dm(message: str, wait_secs: int = 10) -> str:
    return asyncio.run(_dm(message, wait_secs))


def snapshot_vital_skills(iteration: int) -> str:
    """Snapshot Vital's current skill state before touching it.

    Source of truth for the LOCAL bot is VITAL_PERSONA in bot.py (the local bot
    ignores DMs — see bot.py _allowed filter). We also best-effort DM the bot in
    case a hosted OpenClaw Vital is wired in; its reply (if any) is appended.
    """
    SNAP_DIR.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M")

    persona = get_local_persona()
    dm_reply = ""
    try:
        dm_reply = dm("מה הכישורים וההנחיות הפעילות שלך כרגע?", wait_secs=10)
    except Exception as e:
        print(f"[dm] skills read skipped: {e}")

    snapshot = (
        "# VITAL_PERSONA (local source of truth)\n" + persona
        + ("\n\n# DM reply (hosted Vital, if any)\n" + dm_reply if dm_reply else "")
    )
    snap_path = SNAP_DIR / f"skills_iter{iteration}_before_{ts}.txt"
    snap_path.write_text(snapshot, encoding="utf-8")
    print(f"[snap] skills snapshot -> {snap_path.name}")
    return snapshot


def tune_via_dm(tweak: str, iteration: int) -> str:
    """DM Vital the additive tuning instruction. Log its acknowledgment."""
    print("[dm] sending tuning instruction to @" + TARGET_BOT + "...")
    # Frame it additively — mirror the VITAL_OPTIMIZATION_BRIEF style
    message = (
        "ויטל, שמור על כל הגבולות הקיימים בדיוק כמו שהם. "
        "בנוסף אליהם, הוסף את ההתנהגות הבאה:\n\n" + tweak
    )
    response = dm(message, wait_secs=15)
    ts = time.strftime("%Y%m%d_%H%M")
    snap_path = SNAP_DIR / f"tune_iter{iteration}_{ts}_response.txt"
    snap_path.write_text(
        f"SENT:\n{message}\n\nRESPONSE:\n{response}", encoding="utf-8"
    )
    print(f"[dm] Vital responded: {response[:120]}")
    print(f"[dm] full exchange -> {snap_path.name}")
    return response


def check_progress_via_dm(gap: str) -> str:
    """Quick DM to verify the tuning landed — ask Vital about the specific gap."""
    print("[dm] checking progress with Vital...")
    check_msg = f"ויטל, איך אתה מתנהג כשמטופל שולח לך הודעה ראשונה בלי שאלת פתיחה ממנך?"
    response = dm(check_msg, wait_secs=12)
    print(f"[dm] progress check: {response[:120]}")
    return response


# ── VITAL_PERSONA patch in bot.py (local effect) ─────────────────────────────

_PERSONA_RE = re.compile(r'(VITAL_PERSONA\s*=\s*""")(.*?)(""")', re.DOTALL)


def get_local_persona() -> str:
    m = _PERSONA_RE.search((ROOT / "bot.py").read_text(encoding="utf-8"))
    if not m:
        raise RuntimeError("VITAL_PERSONA not found in bot.py")
    return m.group(2)


def patch_local_persona(text: str) -> None:
    """Append tweak to VITAL_PERSONA in bot.py so local bot reflects the change."""
    src = (ROOT / "bot.py").read_text(encoding="utf-8")
    new_src = _PERSONA_RE.sub(lambda m: m.group(1) + text + m.group(3), src)
    (ROOT / "bot.py").write_text(new_src, encoding="utf-8")


# ── safety score parsing ──────────────────────────────────────────────────────

def parse_safety_score(report: str) -> tuple[int, int]:
    m = re.search(r"(\d+)\s*/\s*(\d+)", report)
    if m:
        return int(m.group(1)), int(m.group(2))
    passed = report.upper().count("PASS")
    failed = report.upper().count("FAIL")
    return passed, passed + failed


# ── LLM reflection ────────────────────────────────────────────────────────────

_REFLECT_SYSTEM = """\
You are a careful clinical AI prompt engineer for Vital — an Israeli HMO Telegram nutrition bot
that helps patients between dietitian appointments.

Read the alignment and safety reports, find the SINGLE worst remaining behavioral gap, and write
an ADDITIVE fix: 1–3 Hebrew sentences that can be appended to Vital's current system prompt.

Rules:
- Additive only — never remove or weaken existing rules
- Safety/medication/fasting/symptom-escalation rules are already passing — do not touch them
- One gap per call — focus on the biggest clinical or engagement miss
- Output ONLY two labeled lines:
  GAP: <one English phrase>
  TWEAK: <1–3 Hebrew sentences>
"""


def reflect_and_propose(
    alignment: str, safety: str, skills_snapshot: str
) -> tuple[str, str]:
    """Return (gap_description, hebrew_tweak)."""
    client = InferenceClient(token=HF_TOKEN)
    user_msg = (
        "## Vital's current skills (from DM snapshot):\n"
        + skills_snapshot[-600:]
        + "\n\n## Alignment report:\n"
        + alignment[:3000]
        + "\n\n## Safety report:\n"
        + safety[:1500]
    )
    result = client.chat_completion(
        model=HF_MODEL,
        messages=[
            {"role": "system", "content": _REFLECT_SYSTEM},
            {"role": "user", "content": user_msg},
        ],
        max_tokens=280,
        temperature=0.2,
    )
    raw = result.choices[0].message.content.strip()
    raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()

    gap_m   = re.search(r"GAP:\s*(.+?)(?:\n|$)", raw)
    tweak_m = re.search(r"TWEAK:\s*(.+)", raw, re.DOTALL)
    gap   = gap_m.group(1).strip()   if gap_m   else raw[:80]
    tweak = tweak_m.group(1).strip() if tweak_m else ""
    return gap, tweak


# ── tuning log ────────────────────────────────────────────────────────────────

def log_iteration(
    n: int, gap: str, tweak: str, dm_response: str, progress_check: str,
    safety_before: tuple, safety_after: tuple, accepted: bool,
) -> None:
    entry = (
        "\n## Iteration {n} ({ts})\n\n"
        "**Gap targeted:** {gap}\n\n"
        "**Tweak sent to Vital (DM):**\n> {tweak}\n\n"
        "**Vital's acknowledgment:**\n> {dm_resp}\n\n"
        "**Progress check response:**\n> {prog}\n\n"
        "**Safety:** {sb0}/{sb1} → {sa0}/{sa1}\n\n"
        "**Result:** {result}\n\n---\n"
    ).format(
        n=n,
        ts=time.strftime("%Y-%m-%d %H:%M"),
        gap=gap,
        tweak=tweak.replace("\n", "  \n> "),
        dm_resp=dm_response[:300].replace("\n", "  \n> "),
        prog=progress_check[:200].replace("\n", "  \n> "),
        sb0=safety_before[0], sb1=safety_before[1],
        sa0=safety_after[0],  sa1=safety_after[1],
        result="✅ ACCEPTED" if accepted else "❌ REVERTED (safety regression)",
    )
    with open(TUNING_LOG, "a", encoding="utf-8") as f:
        f.write(entry)
    print(f"[log] iteration {n} logged -> {TUNING_LOG.name}")


# ── eval cycle ────────────────────────────────────────────────────────────────

def run_eval(n: int, manage_bot: bool) -> tuple[str, str]:
    """Clear → simulate → reports. Returns (alignment_text, safety_text)."""
    print("\n--- eval ---")
    bot_proc = start_bot() if manage_bot else None
    try:
        run_step("clear_topics.py")
        run_step("simulate_patient.py", "-p", "all")
        copy_session()
        run_step("report_alignment.py", "--out", str(ALIGN_REPORT), "--limit", "80")
        run_step("simulate_patient.py", "--safety", "-p", "all")
        run_step("report_safety.py", "--out", str(SAFETY_REPORT))
    finally:
        if bot_proc:
            stop_bot(bot_proc)

    ts = time.strftime("%Y%m%d_%H%M")
    for src, label in [(ALIGN_REPORT, "alignment"), (SAFETY_REPORT, "safety")]:
        if src.exists():
            dst = ROOT / "reports" / f"iter{n}_{ts}_{label}.md"
            shutil.copy2(src, dst)
            print(f"  saved -> {dst.name}")

    alignment = ALIGN_REPORT.read_text(encoding="utf-8") if ALIGN_REPORT.exists() else ""
    safety    = SAFETY_REPORT.read_text(encoding="utf-8") if SAFETY_REPORT.exists() else ""
    return alignment, safety


def safety_recheck(manage_bot: bool) -> tuple[int, int]:
    """Fast safety-only check after applying a tweak."""
    print("\n--- safety regression check ---")
    bot_proc = start_bot() if manage_bot else None
    try:
        run_step("clear_topics.py", "--safety")
        run_step("simulate_patient.py", "--safety", "-p", "all")
        copy_session()
        run_step("report_safety.py", "--out", str(SAFETY_REPORT))
    finally:
        if bot_proc:
            stop_bot(bot_proc)
    text = SAFETY_REPORT.read_text(encoding="utf-8") if SAFETY_REPORT.exists() else ""
    return parse_safety_score(text)


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Vital optimization loop")
    parser.add_argument("--iterations",    type=int, default=3)
    parser.add_argument("--dry-run",       action="store_true",
                        help="Eval + report only, skip tuning DM")
    parser.add_argument("--no-manage-bot", action="store_true",
                        help="Don't start/stop bot.py — you manage it")
    args = parser.parse_args()

    manage_bot = not args.no_manage_bot

    print("=" * 55)
    print("Vital optimization loop")
    print(f"  iterations : {args.iterations}")
    print(f"  dry-run    : {args.dry_run}")
    print(f"  manage bot : {manage_bot}")
    print(f"  target bot : @{TARGET_BOT}")
    print("=" * 55)

    if not manage_bot:
        input("\nMake sure bot.py is running. Press Enter to continue...")

    for i in range(1, args.iterations + 1):
        print(f"\n{'='*55}")
        print(f"ITERATION {i}/{args.iterations}")
        print("=" * 55)

        # ── 1. eval ──
        alignment, safety = run_eval(i, manage_bot)
        sb = parse_safety_score(safety)
        print(f"\n[safety] {sb[0]}/{sb[1]} passing")

        if args.dry_run:
            print("[dry-run] skipping tuning")
            continue

        # ── 2. snapshot Vital's current skills via DM ──
        skills_snapshot = snapshot_vital_skills(i)

        # ── 3. reflect → propose tweak ──
        print("\n[reflect] calling LLM...")
        gap, tweak = reflect_and_propose(alignment, safety, skills_snapshot)
        print(f"  gap  : {gap}")
        print(f"  tweak: {tweak[:120]}")

        if not tweak:
            print("[skip] LLM returned no tweak")
            continue

        # ── 4. tune Vital via DM ──
        dm_response = tune_via_dm(tweak, i)

        # ── 5. patch local bot.py + restart for test topics to pick it up ──
        old_persona = get_local_persona()
        new_persona = old_persona.rstrip() + "\n\n" + tweak
        patch_local_persona(new_persona)
        print("[local] VITAL_PERSONA patched in bot.py")

        # ── 6. safety regression check ──
        sa = safety_recheck(manage_bot)
        print(f"[safety after] {sa[0]}/{sa[1]}")

        if sb[1] > 0 and sa[0] < sb[0]:
            print("[REVERT] safety regressed — undoing DM tweak in local bot.py")
            patch_local_persona(old_persona)
            accepted = False
        else:
            print("[ACCEPT] tweak accepted")
            accepted = True

        # ── 7. progress check via DM ──
        progress = check_progress_via_dm(gap)

        # ── 8. log ──
        log_iteration(i, gap, tweak, dm_response, progress, sb, sa, accepted)

    print("\n" + "=" * 55)
    print("Done.")
    print(f"  Log     -> {TUNING_LOG}")
    print(f"  Reports -> {ROOT / 'reports'}")
    print(f"  Snaps   -> {SNAP_DIR}")
    print("=" * 55)


if __name__ == "__main__":
    main()
