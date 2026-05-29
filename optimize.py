#!/usr/bin/env python3
"""
Vital optimization loop.

Starts bot.py, runs patient simulations, generates reports, uses LLM to
propose a 1-3 line additive tweak, applies it, verifies safety didn't
regress, and repeats.

Usage:
    python optimize.py                    # 3 iterations, light loop
    python optimize.py --iterations 5
    python optimize.py --dry-run          # run + report, no tuning

Run bot.py separately if you prefer manual control:
    python optimize.py --no-manage-bot
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from huggingface_hub import InferenceClient

load_dotenv()

ROOT = Path(__file__).parent
HF_TOKEN = os.environ["HF_TOKEN"]
HF_MODEL = os.getenv("HF_MODEL", "Qwen/Qwen3-32B")
ALIGN_REPORT = ROOT / "reports" / "alignment_report.md"
SAFETY_REPORT = ROOT / "reports" / "safety_report.md"


# ── bot process management ────────────────────────────────────────────────────

def start_bot() -> subprocess.Popen:
    proc = subprocess.Popen(
        [sys.executable, str(ROOT / "bot.py")],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(4)  # wait for Telegram connection
    print("[bot] started (pid {})".format(proc.pid))
    return proc


def stop_bot(proc: subprocess.Popen) -> None:
    proc.terminate()
    try:
        proc.wait(timeout=6)
    except subprocess.TimeoutExpired:
        proc.kill()
    print("[bot] stopped")


# ── subprocess helpers ────────────────────────────────────────────────────────

def run_step(script: str, *extra: str) -> bool:
    cmd = [sys.executable, str(ROOT / script)] + list(extra)
    print("  > " + " ".join(cmd[1:]))
    result = subprocess.run(
        cmd, cwd=ROOT,
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    # show last meaningful lines
    out = (result.stdout + result.stderr).strip()
    for line in out.splitlines()[-12:]:
        print("    " + line)
    return result.returncode == 0


def copy_session() -> None:
    shutil.copy2(ROOT / "patient_session.session", ROOT / "report_session.session")


# ── prompt management ─────────────────────────────────────────────────────────

_PERSONA_RE = re.compile(r'(VITAL_PERSONA\s*=\s*""")(.*?)(""")', re.DOTALL)


def get_persona() -> str:
    m = _PERSONA_RE.search((ROOT / "bot.py").read_text(encoding="utf-8"))
    if not m:
        raise RuntimeError("VITAL_PERSONA not found in bot.py")
    return m.group(2)


def set_persona(text: str) -> None:
    src = (ROOT / "bot.py").read_text(encoding="utf-8")
    new_src = _PERSONA_RE.sub(lambda m: m.group(1) + text + m.group(3), src)
    (ROOT / "bot.py").write_text(new_src, encoding="utf-8")


def backup_persona(text: str, iteration: int) -> None:
    snap = ROOT / "docs" / "skill_snapshots"
    snap.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M")
    (snap / f"persona_iter{iteration}_before_{ts}.txt").write_text(text, encoding="utf-8")


# ── safety score parsing ──────────────────────────────────────────────────────

def parse_safety_score(report: str) -> tuple[int, int]:
    """Return (passed, total) from safety report text."""
    # look for summary line like "19/19" or "17/19"
    m = re.search(r"(\d+)\s*/\s*(\d+)", report)
    if m:
        return int(m.group(1)), int(m.group(2))
    # fallback: count PASS / FAIL markers
    passed = report.upper().count("PASS")
    failed = report.upper().count("FAIL")
    return passed, passed + failed


# ── LLM reflection ────────────────────────────────────────────────────────────

_REFLECT_SYSTEM = """\
You are a careful clinical AI prompt engineer optimizing Vital, an Israeli HMO Telegram nutrition bot.
Your task: read the alignment and safety reports, identify the SINGLE worst remaining behavioral gap, and
propose an ADDITIVE fix — 1 to 3 Hebrew sentences to append to the system prompt.

Hard rules:
- Additive only: never remove or weaken existing rules
- Never touch the safety/medication/fasting/symptom-escalation rules (they are passing)
- One gap per iteration
- Output ONLY two labeled lines, nothing else:
  GAP: <one English phrase describing the gap>
  TWEAK: <1–3 Hebrew sentences to append>
"""


def reflect_and_propose(alignment: str, safety: str, persona: str) -> tuple[str, str]:
    """Return (gap_description, hebrew_tweak)."""
    client = InferenceClient(token=HF_TOKEN)
    user_msg = (
        "## Current system prompt (last 800 chars):\n"
        + persona[-800:]
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
        max_tokens=250,
        temperature=0.2,
    )
    raw = result.choices[0].message.content.strip()
    raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()

    gap_m = re.search(r"GAP:\s*(.+?)(?:\n|$)", raw)
    tweak_m = re.search(r"TWEAK:\s*(.+)", raw, re.DOTALL)
    gap = gap_m.group(1).strip() if gap_m else raw[:80]
    tweak = tweak_m.group(1).strip() if tweak_m else ""
    return gap, tweak


# ── tuning log ────────────────────────────────────────────────────────────────

def log_iteration(
    n: int, gap: str, tweak: str,
    safety_before: tuple, safety_after: tuple, accepted: bool,
) -> None:
    entry = (
        "\n## Iteration {} ({})\n\n"
        "**Gap:** {}\n\n"
        "**Tweak applied:**\n> {}\n\n"
        "**Safety:** {}/{} → {}/{}\n\n"
        "**Result:** {}\n\n---\n"
    ).format(
        n, time.strftime("%Y-%m-%d %H:%M"),
        gap, tweak.replace("\n", "  \n> "),
        safety_before[0], safety_before[1],
        safety_after[0], safety_after[1],
        "ACCEPTED" if accepted else "REVERTED (safety regression)",
    )
    with open(ROOT / "docs" / "VITAL_TUNING_LOG.md", "a", encoding="utf-8") as f:
        f.write(entry)


# ── main loop ─────────────────────────────────────────────────────────────────

def run_iteration(n: int, manage_bot: bool) -> tuple[str, str]:
    """Run one eval cycle. Returns (alignment_text, safety_text)."""
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
            print("  saved -> {}".format(dst.name))

    alignment = ALIGN_REPORT.read_text(encoding="utf-8") if ALIGN_REPORT.exists() else ""
    safety = SAFETY_REPORT.read_text(encoding="utf-8") if SAFETY_REPORT.exists() else ""
    return alignment, safety


def safety_recheck(manage_bot: bool) -> tuple[int, int]:
    """Quick safety-only recheck after applying a tweak."""
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


def main() -> None:
    parser = argparse.ArgumentParser(description="Vital optimization loop")
    parser.add_argument("--iterations", type=int, default=3)
    parser.add_argument("--dry-run", action="store_true",
                        help="Eval + report only, no tuning")
    parser.add_argument("--no-manage-bot", action="store_true",
                        help="Skip starting/stopping bot.py (run it yourself)")
    args = parser.parse_args()

    manage_bot = not args.no_manage_bot
    print("=" * 55)
    print("Vital optimization loop")
    print("  iterations : {}".format(args.iterations))
    print("  dry-run    : {}".format(args.dry_run))
    print("  manage bot : {}".format(manage_bot))
    print("=" * 55)

    if not manage_bot:
        print("\nMake sure bot.py is already running before continuing.")
        input("Press Enter when bot is up...")

    for i in range(1, args.iterations + 1):
        print("\n" + "=" * 55)
        print("ITERATION {}/{}".format(i, args.iterations))
        print("=" * 55)

        alignment, safety = run_iteration(i, manage_bot)
        sb = parse_safety_score(safety)
        print("\n[safety baseline] {}/{}".format(sb[0], sb[1]))

        if args.dry_run:
            print("[dry-run] skipping tuning")
            continue

        # reflect
        print("\n[reflect] calling LLM...")
        persona = get_persona()
        gap, tweak = reflect_and_propose(alignment, safety, persona)
        print("  gap  : {}".format(gap))
        print("  tweak: {}".format(tweak[:120]))

        if not tweak:
            print("[skip] LLM returned no tweak")
            continue

        # apply
        backup_persona(persona, i)
        set_persona(persona.rstrip() + "\n\n" + tweak)
        print("[applied] tweak appended to VITAL_PERSONA")

        # verify safety
        sa = safety_recheck(manage_bot)
        print("[safety after] {}/{}".format(sa[0], sa[1]))

        if sb[1] > 0 and sa[0] < sb[0]:
            print("[REVERT] safety regressed — restoring previous persona")
            set_persona(persona)
            accepted = False
        else:
            print("[ACCEPT] tweak accepted")
            accepted = True

        log_iteration(i, gap, tweak, sb, sa, accepted)

    print("\n" + "=" * 55)
    print("Done.  Log  -> docs/VITAL_TUNING_LOG.md")
    print("       Reports -> reports/")
    print("=" * 55)


if __name__ == "__main__":
    main()
