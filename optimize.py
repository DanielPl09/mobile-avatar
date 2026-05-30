#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Vital optimization loop — DM-driven, reflection-based (dspy.GEPA-style).

Vital (@vital_lifestyle_bot) is an OpenClaw agent. Each iteration:
  1. Simulate a natural patient conversation in the topics (time-boxed ~2 min,
     context carried across iterations so the dialogue flows).
  2. Judge it (alignment report; full safety probes on a gate).
  3. Reflect on the report with an LLM -> propose ONE careful, additive 1-3 line tweak.
  4. DM that tweak to Vital (the canonical way to tune an OpenClaw agent).
  5. If a safety gate runs and safety regressed -> DM a revert + log it.

Context is MAINTAINED across iterations within a run. It is RESET between runs
(via /new + /reset DM and a topic clear) unless --keep-context is passed.

One command to run it all:
    python optimize.py

Common flags:
    python optimize.py --iterations 5 --minutes-per-iter 2
    python optimize.py --keep-context        # continue from where Vital left off
    python optimize.py --safety-gate 3       # full safety probes every 3rd iter (0=never)
    python optimize.py --manage-bot          # also start/stop a LOCAL bot.py
    python optimize.py --personas svetlana,ahmad
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

# UTF-8 stdout so Hebrew never crashes print() on Windows.
# write_through=True keeps output unbuffered so progress streams live.
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                  errors="replace", line_buffering=True, write_through=True)
if hasattr(sys.stderr, "buffer"):
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8",
                                  errors="replace", line_buffering=True, write_through=True)

ROOT       = Path(__file__).parent
HF_TOKEN   = os.environ["HF_TOKEN"]
HF_MODEL   = os.getenv("HF_MODEL", "Qwen/Qwen3-32B")
TARGET_BOT = os.getenv("SIMULATOR_BOT", "vital_lifestyle_bot").lstrip("@")
API_ID     = int(os.environ.get("api_app_id") or os.environ["API_ID"])
API_HASH   = os.environ.get("api_app_hash") or os.environ["API_HASH"]
PHONE      = os.environ["PHONE"]
SESSION    = str(ROOT / "patient_session")

ALIGN_REPORT  = ROOT / "reports" / "alignment_report.md"
SAFETY_REPORT = ROOT / "reports" / "safety_report.md"
TUNING_LOG    = ROOT / "docs" / "VITAL_TUNING_LOG.md"
SNAP_DIR      = ROOT / "docs" / "skill_snapshots"


# ── local bot (optional) ──────────────────────────────────────────────────────

def start_bot() -> subprocess.Popen:
    proc = subprocess.Popen(
        [sys.executable, str(ROOT / "bot.py")],
        cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    time.sleep(5)
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

def run_step(script: str, *extra: str, timeout: int | None = None) -> bool:
    cmd = [sys.executable, str(ROOT / script)] + [str(a) for a in extra]
    print("  > " + " ".join(cmd[1:]) + (f"   (cap {timeout}s)" if timeout else ""))
    try:
        result = subprocess.run(
            cmd, cwd=ROOT, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=timeout,
        )
        out = (result.stdout + result.stderr).strip()
        for line in out.splitlines()[-10:]:
            try:
                print("    " + line)
            except Exception:
                print("    " + line.encode("ascii", "replace").decode())
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        print(f"    [time budget reached — wrapping up this turn]")
        return True


def copy_session() -> None:
    shutil.copy2(ROOT / "patient_session.session", ROOT / "report_session.session")


# ── Telegram DM helpers (talk to Vital the OpenClaw agent) ────────────────────

async def _dm(message: str, wait_secs: int) -> str:
    async with TelegramClient(SESSION, API_ID, API_HASH) as client:
        await client.start(phone=PHONE)
        before = time.time()
        await client.send_message(TARGET_BOT, message)
        await asyncio.sleep(wait_secs)
        me = await client.get_me()
        reply = ""
        async for msg in client.iter_messages(TARGET_BOT, limit=8):
            if msg.sender_id != me.id and msg.text and msg.date.timestamp() >= before:
                reply = msg.text.strip()
                break
        return reply


def dm(message: str, wait_secs: int = 12) -> str:
    try:
        return asyncio.run(_dm(message, wait_secs))
    except Exception as e:
        print(f"    [dm error: {e}]")
        return ""


def reset_vital_context() -> None:
    """Reset the OpenClaw chat so a new run starts clean."""
    print("[reset] clearing Vital's conversation context (/new, /reset)...")
    for cmd in ("/new", "/reset"):
        ack = dm(cmd, wait_secs=6)
        print(f"    {cmd} -> {ack[:80] or '(no reply)'}")
    # also clear the simulation topics so threads start fresh
    run_step("clear_topics.py")


def snapshot_vital_skills(iteration: int) -> str:
    """Read-only: ask Vital what it can do, save the snapshot before tuning."""
    SNAP_DIR.mkdir(parents=True, exist_ok=True)
    reply = dm("מה הכישורים וההנחיות הפעילות שלך כרגע? (לתיעוד בלבד)", wait_secs=12)
    ts = time.strftime("%Y%m%d_%H%M")
    path = SNAP_DIR / f"skills_iter{iteration}_{ts}.txt"
    path.write_text(reply or "(no reply)", encoding="utf-8")
    print(f"[snap] skills -> {path.name}")
    return reply


def tune_via_dm(tweak: str, iteration: int) -> str:
    """DM Vital a careful, additive incremental update."""
    message = (
        "ויטל, שמור בדיוק על כל מה שאתה כבר עושה טוב — אל תשנה גבולות בטיחות. "
        "בנוסף, אמץ מעכשיו את ההתנהגות הבאה:\n\n" + tweak
    )
    reply = dm(message, wait_secs=15)
    ts = time.strftime("%Y%m%d_%H%M")
    SNAP_DIR.mkdir(parents=True, exist_ok=True)
    (SNAP_DIR / f"tune_iter{iteration}_{ts}.txt").write_text(
        f"SENT:\n{message}\n\nREPLY:\n{reply}", encoding="utf-8"
    )
    print(f"[tune] DM sent. Vital: {reply[:100] or '(no reply)'}")
    return reply


def revert_last_tune() -> str:
    print("[revert] asking Vital to undo the last change...")
    return dm(
        "ויטל, בטל את העדכון האחרון שביקשתי. חזור בדיוק להתנהגות שהייתה לפניו.",
        wait_secs=12,
    )


# ── safety parsing + reflection ───────────────────────────────────────────────

def parse_safety_score(report: str) -> tuple[int, int]:
    m = re.search(r"(\d+)\s*/\s*(\d+)", report)
    if m:
        return int(m.group(1)), int(m.group(2))
    return report.upper().count("PASS"), 0


_REFLECT_SYSTEM = """\
You are a careful clinical prompt engineer tuning Vital — an Israeli HMO Telegram nutrition bot
that supports patients between dietitian appointments.

Read the report, find the SINGLE biggest remaining behavioral gap, and write an ADDITIVE fix:
1–3 natural Hebrew sentences Vital can adopt without weakening anything it already does.

Rules:
- Additive only. Never weaken safety / medication / fasting / symptom-escalation rules.
- One gap per call. Prefer the gap that hurts natural, helpful conversation most.
- Output EXACTLY two lines:
  GAP: <one English phrase>
  TWEAK: <1–3 Hebrew sentences>
"""


def reflect(alignment: str, safety: str, skills: str) -> tuple[str, str]:
    client = InferenceClient(token=HF_TOKEN)
    user = (
        "## Vital current skills (DM snapshot):\n" + (skills[-600:] or "(none)")
        + "\n\n## Alignment report:\n" + alignment[:3000]
        + "\n\n## Safety report:\n" + safety[:1200]
    )
    res = client.chat_completion(
        model=HF_MODEL,
        messages=[{"role": "system", "content": _REFLECT_SYSTEM},
                  {"role": "user", "content": user}],
        max_tokens=280, temperature=0.2,
    )
    raw = re.sub(r"<think>.*?</think>", "", res.choices[0].message.content,
                 flags=re.DOTALL).strip()
    gap_m   = re.search(r"GAP:\s*(.+?)(?:\n|$)", raw)
    tweak_m = re.search(r"TWEAK:\s*(.+)", raw, re.DOTALL)
    return (gap_m.group(1).strip() if gap_m else raw[:80],
            tweak_m.group(1).strip() if tweak_m else "")


def log_iteration(n, gap, tweak, reply, sb, sa, note) -> None:
    entry = (
        f"\n## Iteration {n} ({time.strftime('%Y-%m-%d %H:%M')})\n\n"
        f"**Gap:** {gap}\n\n"
        f"**Tweak DM'd to Vital:**\n> {tweak.replace(chr(10), '  '+chr(10)+'> ')}\n\n"
        f"**Vital reply:** {reply[:200] or '(none)'}\n\n"
        f"**Safety:** {sb[0]}/{sb[1]} → {sa[0]}/{sa[1]}\n\n"
        f"**Result:** {note}\n\n---\n"
    )
    TUNING_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(TUNING_LOG, "a", encoding="utf-8") as f:
        f.write(entry)
    print(f"[log] -> {TUNING_LOG.name}")


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(description="Vital DM-driven optimization loop")
    ap.add_argument("--iterations", type=int, default=3)
    ap.add_argument("--minutes-per-iter", type=float, default=2.0,
                    help="Wall-clock budget for each iteration's conversation")
    ap.add_argument("--keep-context", action="store_true",
                    help="Do NOT reset Vital's chat at start (default: reset)")
    ap.add_argument("--safety-gate", type=int, default=3,
                    help="Run full safety probes every Nth iteration (0 = never)")
    ap.add_argument("--manage-bot", action="store_true",
                    help="Start/stop a LOCAL bot.py (only if Vital runs locally)")
    ap.add_argument("--personas", default="all")
    args = ap.parse_args()

    sim_cap = int(args.minutes_per_iter * 60)

    print("=" * 58)
    print("Vital optimization loop (DM-driven, GEPA-style)")
    print(f"  target       : @{TARGET_BOT}")
    print(f"  iterations   : {args.iterations}")
    print(f"  min/iter     : {args.minutes_per_iter}  (sim cap {sim_cap}s)")
    print(f"  keep-context : {args.keep_context}")
    print(f"  safety-gate  : every {args.safety_gate or '∞'}")
    print("=" * 58)

    bot = start_bot() if args.manage_bot else None
    try:
        # Reset context between RUNS unless told to keep it
        if not args.keep_context:
            reset_vital_context()
        else:
            print("[reset] --keep-context set: continuing existing conversation")

        for i in range(1, args.iterations + 1):
            print(f"\n{'='*58}\nITERATION {i}/{args.iterations}\n{'='*58}")

            # 1. natural conversation — context carried across iterations.
            #    iter 1 opens fresh; later iters resume the same threads.
            print(f"\n--- conversation ({args.minutes_per_iter} min) ---")
            sim_args = ["-p", args.personas]
            if i > 1:
                sim_args.append("--resume")   # continue the flowing dialogue
            run_step("simulate_patient.py", *sim_args, timeout=sim_cap)

            # 2. judge
            copy_session()
            run_step("report_alignment.py", "--out", str(ALIGN_REPORT), "--limit", "80")
            alignment = ALIGN_REPORT.read_text(encoding="utf-8") if ALIGN_REPORT.exists() else ""

            run_full_safety = args.safety_gate and (i % args.safety_gate == 0)
            sb = (0, 0)
            if run_full_safety:
                print("\n--- safety gate ---")
                run_step("simulate_patient.py", "--safety", "-p", "all")
                copy_session()
                run_step("report_safety.py", "--out", str(SAFETY_REPORT))
            safety = SAFETY_REPORT.read_text(encoding="utf-8") if SAFETY_REPORT.exists() else ""
            sb = parse_safety_score(safety)

            ts = time.strftime("%Y%m%d_%H%M")
            for src, label in [(ALIGN_REPORT, "alignment"), (SAFETY_REPORT, "safety")]:
                if src.exists():
                    shutil.copy2(src, ROOT / "reports" / f"iter{i}_{ts}_{label}.md")

            # 3. reflect -> one careful additive tweak
            print("\n[reflect] ...")
            skills = snapshot_vital_skills(i)
            gap, tweak = reflect(alignment, safety, skills)
            print(f"  gap  : {gap}")
            print(f"  tweak: {tweak[:120]}")
            if not tweak:
                print("[skip] no tweak proposed")
                log_iteration(i, gap, "(none)", "", sb, sb, "SKIPPED (no tweak)")
                continue

            # 4. tune Vital via DM
            reply = tune_via_dm(tweak, i)

            # 5. safety guard (only meaningful when the gate ran)
            note = "✅ ACCEPTED"
            sa = sb
            if run_full_safety:
                print("\n--- post-tune safety recheck ---")
                run_step("simulate_patient.py", "--safety", "-p", "all")
                copy_session()
                run_step("report_safety.py", "--out", str(SAFETY_REPORT))
                sa = parse_safety_score(SAFETY_REPORT.read_text(encoding="utf-8"))
                if sb[1] and sa[0] < sb[0]:
                    revert_last_tune()
                    note = "❌ REVERTED (safety regressed)"
            print(f"[result] {note}")

            log_iteration(i, gap, tweak, reply, sb, sa, note)

    finally:
        if bot:
            stop_bot(bot)

    print("\n" + "=" * 58)
    print("Done.")
    print(f"  Tuning log -> {TUNING_LOG}")
    print(f"  Reports    -> {ROOT/'reports'}")
    print(f"  Snapshots  -> {SNAP_DIR}")
    print("=" * 58)


if __name__ == "__main__":
    main()
