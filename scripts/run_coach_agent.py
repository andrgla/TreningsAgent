#!/usr/bin/env python3
"""Headless coach: run the training-coach-loop skill on a schedule.

Unlike the deterministic scripts, generating a week of sessions and a quarter
plan is *agent* work - it reads Garmin readiness, infers drinking days from the
calendar, respects the volume cap, and writes in Eda's voice. This runner drives
a Claude Code agent (Claude Agent SDK) so that intelligence runs unattended,
on the Mac or in GitHub Actions.

Modes:
  weekly     - generate next week's Trening calendar sessions (adaptive).
  quarterly  - one week before the current program ends, generate the next
               training block in Notion.

The agent loads project settings (CLAUDE.md -> AGENTS.md, .claude/skills,
.mcp.json) via setting_sources, so it has the same tools and persona as the
interactive coach. A carve-out in AGENTS.md authorises THIS runner to write the
calendar / Notion without interactive confirmation.

Requirements (one-time):
  1. pip install claude-agent-sdk         (in servers/requirements.txt)
  2. npm install -g @anthropic-ai/claude-code
  3. ANTHROPIC_API_KEY in the environment (LOCAL_ENV_FILE locally, repository
     secrets in GitHub Actions)

Exit codes: 0 ok / skipped, 1 startup failure (auth/config), 2 run failed,
3 missing prerequisite.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Trigger the quarterly job when the current program ends within this many days.
QUARTER_LOOKAHEAD_DAYS = 8
DEFAULT_MODEL = os.environ.get("COACH_AGENT_MODEL", "claude-opus-5")

# Ceiling per run so a confused agent cannot spin forever. Weekly needs roughly
# 30-60 turns of Garmin/Notion/calendar reads plus the edit-and-push; the
# quarterly build is a bigger piece of work.
MAX_TURNS = {"weekly": 120, "quarterly": 200}


LOCAL_ENV_FILE = ".env"


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
    # Fire once the block is inside the lookahead *or already over*. The old
    # `0 <= days_left` lower bound meant a program that expired without anyone
    # noticing could never trigger a rebuild — the window had closed behind it,
    # and the job would skip forever. Overdue is the strongest reason to run.
    if days_left <= QUARTER_LOOKAHEAD_DAYS:
        if days_left < 0:
            print(f"Quarterly: program ended {-days_left}d ago — generating next block.")
        else:
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
   `python scripts/push_calendar_plan.py --confirm --reset`
   (the calendar backend is picked automatically: EventKit on the Mac,
   iCloud CalDAV in the cloud - you do not need to configure it)

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
   `python scripts/bootstrap_notion.py && python scripts/prettify_notion.py`

This is the AUTHORISED automated quarterly run: write the new quarter to Notion
WITHOUT asking me for confirmation (see the automation carve-out in AGENTS.md).
Keep all copy in Eda's voice. End with a one-line summary of the new block."""


def _options(mode: str):
    from claude_agent_sdk import ClaudeAgentOptions  # noqa: PLC0415

    # The agent launches the MCP servers itself. Point them at this checkout and
    # this interpreter so one .mcp.json works on the Mac and on a CI runner.
    os.environ.setdefault("TRENINGSAGENT_ROOT", str(ROOT))
    os.environ.setdefault("TRENINGSAGENT_PYTHON", sys.executable)

    return ClaudeAgentOptions(
        cwd=str(ROOT),
        model=DEFAULT_MODEL,
        # "project" loads CLAUDE.md (-> AGENTS.md), .claude/skills, .mcp.json
        # and .claude/settings.json, so the headless coach has the same persona
        # and tools as the interactive one. "user" adds personal settings when
        # this runs on the Mac.
        setting_sources=["user", "project"],
        # Unattended: nobody is here to approve a prompt. Writes stay fenced -
        # calendar_mcp refuses every calendar except Trening.
        permission_mode="bypassPermissions",
        max_turns=MAX_TURNS[mode],
    )


async def _run(mode: str, prompt: str) -> tuple[str, str]:
    """Drive the agent to completion; return (status, final text)."""
    from claude_agent_sdk import (  # noqa: PLC0415
        AssistantMessage,
        ResultMessage,
        TextBlock,
        query,
    )

    status = "unknown"
    final = ""
    async for message in query(prompt=prompt, options=_options(mode)):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock) and block.text.strip():
                    # Stream progress into the job log so a failed run can be
                    # diagnosed from the GitHub Actions output alone.
                    print(block.text.strip(), flush=True)
        elif isinstance(message, ResultMessage):
            final = getattr(message, "result", "") or ""
            status = "error" if getattr(message, "is_error", False) else "finished"
    return status, final


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the headless coach agent.")
    parser.add_argument("mode", choices=["weekly", "quarterly"])
    parser.add_argument(
        "--force",
        action="store_true",
        help="Run quarterly even if the program isn't ending soon.",
    )
    args = parser.parse_args()

    load_env_file(ROOT / LOCAL_ENV_FILE)

    # Gate first: the quarterly job runs daily and does nothing on ~355 of those
    # days, so it should exit cleanly without needing a key or the SDK at all.
    if args.mode == "quarterly" and not _quarter_due(args.force):
        return 0

    if not os.environ.get("ANTHROPIC_API_KEY", "").strip():
        print(
            "ERROR: ANTHROPIC_API_KEY not set. Create a key at "
            "console.anthropic.com and add it to the local env file or to the "
            "repository secrets (GitHub Actions).",
            file=sys.stderr,
        )
        return 3

    try:
        import claude_agent_sdk  # noqa: F401,PLC0415
    except ImportError:
        print(
            "ERROR: claude-agent-sdk not installed. Run: "
            "pip install -r servers/requirements.txt",
            file=sys.stderr,
        )
        return 3

    prompt = WEEKLY_PROMPT if args.mode == "weekly" else QUARTERLY_PROMPT

    try:
        status, text = asyncio.run(_run(args.mode, prompt))
    except Exception as e:  # noqa: BLE001
        # Startup failures - missing `claude` CLI, bad key, an MCP server that
        # will not launch - land here; the run never executed.
        print(f"Coach agent startup failed ({type(e).__name__}): {e}", file=sys.stderr)
        return 1

    print(f"Coach agent [{args.mode}] status={status}")
    if text:
        print(text)
    return 0 if status == "finished" else 2


if __name__ == "__main__":
    raise SystemExit(main())
