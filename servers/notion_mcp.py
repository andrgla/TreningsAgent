"""Notion MCP — Q3 training program on Workout Coach page."""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

from mcp.server.fastmcp import FastMCP

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data.q3_training_program import PROGRAM_OVERVIEW, WEEKS  # noqa: E402
from notion_client import (  # noqa: E402
    find_child_database,
    load_state,
    query_database,
    week_row_to_dict,
    workout_coach_page_id,
)

mcp = FastMCP("notion")

DB_TITLE = "Q3 Training Weeks"


def _dump(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2, default=str)


def _database_id() -> str | None:
    state = load_state()
    if state.get("database_id"):
        return state["database_id"]
    block = find_child_database(workout_coach_page_id(), DB_TITLE)
    return block.get("id") if block else None


def _local_weeks() -> list[dict]:
    return [
        {
            "week": w["title"],
            "phase": w["phase"],
            "start": w["start"],
            "end": w["end"],
            "run_km": w["run_km"],
            "running": w["running"],
            "strength": w["strength"],
            "mobility": w["mobility"],
            "quality": w["quality"],
            "notes": w["notes"],
            "status": "Planned",
        }
        for w in WEEKS
    ]


def _weeks_from_notion() -> list[dict]:
    db_id = _database_id()
    if not db_id:
        return []
    pages = query_database(db_id)
    rows = [week_row_to_dict(p) for p in pages]
    return sorted(rows, key=lambda r: r.get("start", ""))


@mcp.tool()
def get_program_overview() -> str:
    """Quarter plan overview (Trondheim HM build, Jul–Aug 2026)."""
    state = load_state()
    page_id = workout_coach_page_id()
    payload = {
        "workoutCoachPageId": page_id,
        "workoutCoachUrl": f"https://www.notion.so/Workout-Coach-{page_id.replace('-', '')}",
        "databaseId": _database_id(),
        "bootstrapped": bool(state.get("database_id")),
        "overview": PROGRAM_OVERVIEW,
    }
    return _dump(payload)


@mcp.tool()
def list_training_weeks() -> str:
    """All weekly rows from Notion (falls back to local program if not bootstrapped)."""
    try:
        rows = _weeks_from_notion()
        source = "notion"
        if not rows:
            rows = _local_weeks()
            source = "local_fallback"
        return _dump({"source": source, "weeks": rows})
    except Exception as e:  # noqa: BLE001
        return _dump({"source": "local_fallback", "error": str(e), "weeks": _local_weeks()})


@mcp.tool()
def get_training_week(week_number: int = 0, on_date: str = "") -> str:
    """Get one program week by number (1–8) or ISO date (YYYY-MM-DD)."""
    try:
        rows = _weeks_from_notion() or _local_weeks()
        if on_date:
            target = date.fromisoformat(on_date)
            for row in rows:
                start_s = (row.get("start") or "").split("→")[0].strip()[:10]
                end_s = (row.get("end") or row.get("start") or "").split("→")[-1].strip()[:10]
                if start_s and end_s:
                    if date.fromisoformat(start_s) <= target <= date.fromisoformat(end_s):
                        return _dump(row)
            return f"No program week contains date {on_date}."
        if week_number < 1 or week_number > len(rows):
            return f"week_number must be 1–{len(rows)}."
        return _dump(rows[week_number - 1])
    except Exception as e:  # noqa: BLE001
        return f"Could not fetch week: {e}"


@mcp.tool()
def get_current_training_week() -> str:
    """Program week that contains today's date."""
    return get_training_week(on_date=date.today().isoformat())


@mcp.tool()
def notion_status() -> str:
    """Bootstrap state: page id, database id, whether Notion is wired."""
    state = load_state()
    return _dump(
        {
            "workoutCoachPageId": workout_coach_page_id(),
            "databaseId": _database_id(),
            "bootstrappedAt": state.get("bootstrapped_at"),
            "bootstrapCommand": "./.venv/bin/python scripts/bootstrap_notion.py",
        }
    )


if __name__ == "__main__":
    mcp.run()
