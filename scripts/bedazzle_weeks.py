#!/usr/bin/env python3
"""Bedazzle the Q3 Training Weeks database: one emoji per week as the row icon.

Idempotent — safe to re-run. Matches each row by its "Week N" number and sets
the page icon so the table reads bubbly. The title text is kept clean (no inline
emoji) — Notion renders the page icon next to the title, so an emoji in the title
too would show up doubled.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "servers"))


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


load_env_file(ROOT / ".env")

from notion_client import (  # noqa: E402
    find_child_database,
    load_state,
    notion_request,
    query_database,
    workout_coach_page_id,
)

try:
    from data.q3_training_program import DB_TITLE
except Exception:  # pragma: no cover - fallback if program module moves
    DB_TITLE = "Q4 Training Weeks"

# Week number -> emoji (from Andrea's palette): seed → bloom → ocean → disco → moon.
WEEK_EMOJI = {
    1: "🌱",
    2: "🌷",
    3: "🌺",
    4: "🐠",
    5: "🌊",
    6: "🪩",
    7: "💫",
    8: "🌙",
}

# Any leading emoji/space we may have added on a previous run.
LEADING_EMOJI = re.compile(r"^[\U0001F000-\U0001FAFF\u2600-\u27BF\u2B00-\u2BFF\uFE0F\u200d]+\s*")


def _database_id() -> str | None:
    state = load_state()
    if state.get("database_id"):
        return state["database_id"]
    block = find_child_database(workout_coach_page_id(), DB_TITLE)
    return block.get("id") if block else None


def _plain(rich: list[dict]) -> str:
    return "".join(p.get("plain_text", "") for p in rich if isinstance(p, dict))


def _week_title_prop(page: dict) -> tuple[str, str]:
    """Return (property_name, plain_title) for the title property."""
    for name, prop in page.get("properties", {}).items():
        if prop.get("type") == "title":
            return name, _plain(prop.get("title", []))
    return "Week", ""


def main() -> int:
    if not os.environ.get("NOTION_TOKEN", "").strip():
        print("ERROR: NOTION_TOKEN not set in .env", file=sys.stderr)
        return 1

    db_id = _database_id()
    if not db_id:
        print("ERROR: Q3 Training Weeks database not found. Run bootstrap_notion.py first.", file=sys.stderr)
        return 1

    print(f"Bedazzling database: {db_id}")
    rows = query_database(db_id)
    updated = 0

    for page in rows:
        prop_name, title = _week_title_prop(page)
        m = re.search(r"week\s*(\d+)", title, re.IGNORECASE)
        if not m:
            print(f"  skip (no week number): {title[:40]}")
            continue
        n = int(m.group(1))
        emoji = WEEK_EMOJI.get(n)
        if not emoji:
            print(f"  skip (week {n} not in map): {title[:40]}")
            continue

        base = LEADING_EMOJI.sub("", title).strip()

        notion_request(
            "PATCH",
            f"/pages/{page['id']}",
            {
                "icon": {"type": "emoji", "emoji": emoji},
                "properties": {prop_name: {"title": [{"text": {"content": base}}]}},
            },
        )
        print(f"  {emoji}  {base}")
        updated += 1

    print(f"\nDone. Bedazzled {updated} week(s). 🫧")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
