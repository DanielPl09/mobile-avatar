# Vital Optimization Tuning Log

Professional iteration log for reflection-driven prompt optimization.
Inspired by dspy.GEPA: each iteration captures goal → action → metric → reflection.

---

## Run 0: Baseline (2026-05-29)

**Scope:** All 19 safety probes + Itai (single-session light loop).

**Baseline metrics:**
- Safety pass rate: TBD (baseline established before tuning)
- Alignment scores (per persona, per tier): TBD

**No tuning in Run 0** — this is the reference point.

---

## Iteration 1 (scheduled)

**Target gap:** (data-driven — TBD after Run 0 report)

**Baseline metric:** (from Run 0 report)

**Tweak:** (1–3 lines, additive only)

**Skill affected:** (which existing Vital skill was extended, or new skill created)

**Applied:** (timestamp + commit SHA)

**Metrics after:**
- Safety pass rate: (should be ≥ baseline)
- Alignment scores: (per persona)
- Regression check: (any persona score dropped? any safety dropped?)

**Reflection:**
- What worked?
- What was unexpected?
- Next gap to target?

---

## Tuning guardrails

✅ **Non-negotiable:**
- Every tweak additive-only (never weaken PRESERVE list from VITAL_OPTIMIZATION_BRIEF.md).
- Safety pass rate ≥ baseline. If regresses → revert.
- One gap per iteration.
- Snapshot skill before edit; exact revert available if needed.

✅ **Gates:**
- Full arc + safety run every 3rd accepted iteration (catch arc-level regressions light loop misses).

✅ **Stop conditions:**
- All 7 brief gaps closed without regression.
- Diminishing returns observed.
- User stops.

---

