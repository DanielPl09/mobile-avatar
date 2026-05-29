"""
Full test pipeline runner.

Steps:
  1. Simulate all patient scenarios (persona arc or single session)
  2. Simulate all safety probes
  3. Run alignment report
  4. Run safety report
  5. Print a summary with links to both output files

Usage:
  python run_all.py                      # full run, arc mode for scenarios
  python run_all.py --session 1          # single session only (faster)
  python run_all.py --safety-only        # skip scenario simulation
  python run_all.py --alignment-only     # skip safety simulation
  python run_all.py --no-simulate        # reports only (transcripts already in Telegram)
  python run_all.py --out-dir ./reports  # save reports to specific directory
"""

import argparse
import asyncio
import subprocess
import sys
from datetime import datetime
from pathlib import Path


def run(cmd: list[str], label: str) -> int:
    print(f"\n{'='*60}")
    print(f"▶  {label}")
    print(f"{'='*60}")
    result = subprocess.run(cmd, check=False)
    if result.returncode != 0:
        print(f"⚠️  {label} exited with code {result.returncode}", file=sys.stderr)
    return result.returncode


def main() -> None:
    parser = argparse.ArgumentParser(description="Vital full test pipeline")
    parser.add_argument("--session", type=int, default=0,
                        help="Run a specific arc session (0 = full arc)")
    parser.add_argument("--personas", default="all",
                        help="Comma-separated persona names or 'all'")
    parser.add_argument("--safety-only", action="store_true")
    parser.add_argument("--alignment-only", action="store_true")
    parser.add_argument("--no-simulate", action="store_true",
                        help="Skip simulation, run reports on existing transcripts")
    parser.add_argument("--out-dir", default="reports", help="Directory for report files (default: reports/)")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now().strftime("%Y%m%d_%H%M")
    alignment_out = str(out_dir / f"alignment_{ts}.md")
    safety_out    = str(out_dir / f"safety_{ts}.md")

    errors = []

    if not args.no_simulate:
        if not args.safety_only:
            # Scenario simulation
            sim_cmd = [sys.executable, "simulate_patient.py", "-p", args.personas]
            if args.session > 0:
                sim_cmd += ["--session", str(args.session)]
            else:
                sim_cmd += ["--arc"]
            rc = run(sim_cmd, f"Simulate scenarios ({args.personas})")
            if rc != 0:
                errors.append("scenario simulation")

        if not args.alignment_only:
            # Safety probe simulation
            rc = run(
                [sys.executable, "simulate_patient.py", "--safety", "-p", "all"],
                "Simulate safety probes"
            )
            if rc != 0:
                errors.append("safety simulation")

    if not args.safety_only:
        rc = run(
            [sys.executable, "report_alignment.py", "--out", alignment_out, "--limit", "80"],
            "Alignment report"
        )
        if rc != 0:
            errors.append("alignment report")

    if not args.alignment_only:
        rc = run(
            [sys.executable, "report_safety.py", "--out", safety_out],
            "Safety report"
        )
        if rc != 0:
            errors.append("safety report")

    print(f"\n{'='*60}")
    print("📋 PIPELINE COMPLETE")
    print(f"{'='*60}")
    if not args.safety_only and Path(alignment_out).exists():
        print(f"  Alignment report → {alignment_out}")
    if not args.alignment_only and Path(safety_out).exists():
        print(f"  Safety report    → {safety_out}")
    if errors:
        print(f"\n⚠️  Steps with errors: {', '.join(errors)}")
        sys.exit(1)
    else:
        print("\n✅ All steps completed successfully.")


if __name__ == "__main__":
    main()
