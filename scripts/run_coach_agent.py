#!/usr/bin/env python3
"""Headless coach: run the training-coach-loop skill on a schedule.

Unlike the deterministic scripts, generating a week of sessions and a quarter
plan is *agent* work — it reads Garmin readiness, infers drinking days from the
calendar, respects the volume cap, and writes in Eda's voice. This runner drives
a local Cursor agent (Cursor SDK) so that intelligence runs unattended.

Modes:
  weekly     — generate next week's Trening calendar sessions (adaptive).
  quarterly  — one week before the current program ends, generate the next
               training block in Notion.

The agent loads project settings (AGENTS.md, skills, .cursor/mcp.json) via
setting_sources, so it has the same tools and persona as the interactive coach.
A carve-out in AGENTS.md authorises THIS runner to write the calendar / Notion
without interactive confirmation.

Requirements (one-time):
  1. pip install cursor-sdk          (added to servers/requirements.txt)
  2. CURSOR_API_KEY in .env          (cursor.com/dashboard/integrations)

Exit codes: 0 ok / skipped, 1 startup failure (auth/config), 2 run failed,
3 missing prerequisite.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Trigger the quarterly job when the current program ends within this many days.
QUARTER_LOOKAHEAD_DAYS = 8
DEFAULT_MODEL = os.environ.get("COACH_AGENT_MODEL", "auto")


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


def _program_end() -> date | None:
    """Latest end date across the program's WEEKS, if importable."""
    try:
        from data.q3_training_program import WEEKS  # noqa: PLC0415
    except Exception:
        return None
    ends = []
    for w in WEEKS:
        try:
            ends.append(date.fromisoformat(w["end"]))
        except Exception:
            continue
    return max(ends) if ends else None


def _quarter_due(force: bool) -> bool:
    if force:
        return True
    end = _program_end()
    if end is None:
        print("Quarterly: could not read program end date; skipping.", file=sys.stderr)
        return False
    days_left = (end - date.today()).days
    if 0 <= days_left <= QUARTER_LOOKAHEAD_DAYS:
        print(f"Quarterly: program ends in {days_left}d — generating next block.")
        return True
    print(f"Quarterly: program ends in {days_left}d (>{QUARTER_LOOKAHEAD_DAYS}); skipping.")
    return False


WEEKLY_PROMPT = """You are Eda, my running/strength coach. Run the **Weekly generation**
procedure from the `training-coach-loop` skill for the UPCOMING week (Mon–Sun,
starting next Monday, Europe/Oslo).

Steps:
1. Read the current/next training week from Notion (`get_current_training_week`).
2. Check Garmin recovery + load (`training_readiness`, `sleep`, `hrv`,
   `daily_stats`, `recent_activities`, `recent_strength_sessions`,
   `weekly_running_summary`) — respect the ~10%/week volume cap.
3. Read my calendar for the target week and INFER drinking/party days; protect
   the morning after (no early, no hard/long) per AGENTS.md.
4. Build the week to my goal paces (legs 2×, one quality, one long, easy runs,
   one mobility), honouring readiness and drinking-day rules.
5. Edit `CALENDAR_WEEK` in `data/q3_training_program.py` to the target week's
   sessions, then push to the Trening calendar:
   `./.venv/bin/python scripts/push_calendar_plan.py --confirm --reset`

This is the AUTHORISED automated weekly run: create the Trening calendar events
WITHOUT asking me for confirmation (see the automation carve-out in AGENTS.md).
Keep session titles/notes in Eda's voice. Do not book any SiO class.
End with a one-line summary of what you scheduled."""

QUARTERLY_PROMPT = """You are Eda, my running/strength coach. The current training block is
ending. Run the **Quarterly generation** procedure from the
`training-coach-loop` skill to create the NEXT block.

Steps:
1. Baseline from Garmin (`vo2max`/`fitness_trends`, `weekly_running_summary`,
   `training_status`, recent `recent_activities`).
2. Anchor to the goals ladder in AGENTS.md (who-is-she → annual → quarterly) —
   read the Notion vision pages if available.
3. Design phases (base → build → peak → taper, ~10%/week) mapped week-by-week.
4. Edit `data/q3_training_program.py`: update `PROGRAM_OVERVIEW`, `WEEKS`, and
   set a NEW `DB_TITLE` for the new quarter so a fresh database is created.
5. Publish to Notion:
   `./.venv/bin/python scripts/bootstrap_notion.py && ./.venv/bin/python scripts/prettify_notion.py`

This is the AUTHORISED automated quarterly run: write the new quarter to Notion
WITHOUT asking me for confirmation (see the automation carve-out in AGENTS.md).
Keep all copy in Eda's voice. End with a one-line summary of the new block."""


def _build_options(api_key: str):
    from cursor_sdk import AgentOptions, LocalAgentOptions

    return AgentOptions(
        api_key=api_key,
        model=DEFAULT_MODEL,
        # Load project AGENTS.md + skills + .cursor/mcp.json so the headless
        # agent has the same persona and MCP tools as the interactive coach.
        local=LocalAgentOptions(cwd=str(ROOT), setting_sources=["all"]),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the headless coach agent.")
    parser.add_argument("mode", choices=["weekly", "quarterly"])
    parser.add_argument(
        "--force",
        action="store_true",
        help="Run quarterly even if the program isn't ending soon.",
    )
    args = parser.parse_args()

    load_env_file(ROOT / ".env")

    api_key = os.environ.get("CURSOR_API_KEY", "").strip()
    if not api_key:
        print(
            "ERROR: CURSOR_API_KEY not set. Create one at "
            "cursor.com/dashboard/integrations and add it to .env.",
            file=sys.stderr,
        )
        return 3

    try:
        from cursor_sdk import Agent  # noqa: PLC0415
    except ImportError:
        print(
            "ERROR: cursor-sdk not installed. Run: "
            "./.venv/bin/pip install cursor-sdk",
            file=sys.stderr,
        )
        return 3

    if args.mode == "quarterly" and not _quarter_due(args.force):
        return 0

    prompt = WEEKLY_PROMPT if args.mode == "weekly" else QUARTERLY_PROMPT

    try:
        from cursor_sdk import CursorAgentError  # noqa: PLC0415

        result = Agent.prompt(prompt, _build_options(api_key))
    except Exception as e:  # noqa: BLE001
        # CursorAgentError (and friends) = the run never executed.
        name = type(e).__name__
        print(f"Coach agent startup failed ({name}): {e}", file=sys.stderr)
        return 1

    status = getattr(result, "status", "unknown")
    text = getattr(result, "result", "") or ""
    print(f"Coach agent [{args.mode}] status={status}")
    if text:
        print(text)
    return 0 if status == "finished" else 2


if __name__ == "__main__":
    raise SystemExit(main())
