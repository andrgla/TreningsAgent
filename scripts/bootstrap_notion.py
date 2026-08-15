#!/usr/bin/env python3
"""Create Q3 training database on Workout Coach Notion page and populate weeks."""

from __future__ import annotations

import os
import os
import sys
from datetime import datetime, timezone
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

from data.q3_training_program import PROGRAM_OVERVIEW, WEEKS  # noqa: E402
from notion_client import (  # noqa: E402
    find_child_database,
    get_page,
    list_block_children,
    md_rich_text,
    notion_request,
    save_state,
    workout_coach_page_id,
)

DB_TITLE = "Q3 Training Weeks"
PHASE_OPTIONS = [
    {"name": "Base", "color": "blue"},
    {"name": "Build", "color": "orange"},
    {"name": "Peak", "color": "red"},
    {"name": "Taper prep", "color": "green"},
]
STATUS_OPTIONS = [
    {"name": "Planned", "color": "default"},
    {"name": "In progress", "color": "yellow"},
    {"name": "Done", "color": "green"},
]


def _rt(text: str) -> list[dict]:
    return md_rich_text(text)


def _block(kind: str, text: str, **extra) -> dict:
    payload = {"rich_text": _rt(text), **extra}
    return {"object": "block", "type": kind, kind: payload}


def _overview_blocks() -> list[dict]:
    lines = PROGRAM_OVERVIEW.strip().split("\n")
    blocks: list[dict] = [
        {
            "object": "block",
            "type": "callout",
            "callout": {
                "rich_text": _rt(
                    "**Hi, I'm Eda — your coach.** 🫒 **Trondheim Halvmaraton** · "
                    "5:25/km · Q3 build (Jul–Aug 2026). Calendar = when you show up · "
                    "this database = what each week looks like. Trust the plan, feel "
                    "your body, we call it in together. ✨"
                ),
                "icon": {"type": "emoji", "emoji": "🫒"},
                "color": "pink_background",
            },
        },
    ]
    for raw in lines:
        line = raw.strip()
        if line.startswith("# "):
            blocks.append(_block("heading_1", line[2:].strip()))
        elif line.startswith("## "):
            blocks.append({"object": "block", "type": "divider", "divider": {}})
            blocks.append(_block("heading_2", line[3:].strip()))
        elif line.startswith("- "):
            blocks.append(_block("bulleted_list_item", line[2:].strip()))
        elif len(line) > 2 and line[0].isdigit() and line[1] == ".":
            blocks.append(_block("numbered_list_item", line[2:].strip()))
        elif line:
            blocks.append(_block("paragraph", line))
    return blocks


def ensure_overview_on_page(page_id: str) -> None:
    children = list_block_children(page_id)
    if any(
        b.get("type") == "callout"
        and "Trondheim Halvmaraton" in str(b.get("callout", {}).get("rich_text", ""))
        for b in children
    ):
        print("Overview blocks already present — skipping.")
        return
    notion_request(
        "PATCH",
        f"/blocks/{page_id}/children",
        {"children": _overview_blocks()},
    )
    print("Added program overview to Workout Coach page.")


def create_database(page_id: str) -> str:
    existing = find_child_database(page_id, DB_TITLE)
    if existing:
        print(f"Database already exists: {existing['id']}")
        return existing["id"]

    payload = {
        "parent": {"type": "page_id", "page_id": page_id},
        "title": [{"type": "text", "text": {"content": DB_TITLE}}],
        "properties": {
            "Week": {"title": {}},
            "Phase": {"select": {"options": PHASE_OPTIONS}},
            "Start": {"date": {}},
            "End": {"date": {}},
            "Run km": {"rich_text": {}},
            "Running": {"rich_text": {}},
            "Strength": {"rich_text": {}},
            "Mobility": {"rich_text": {}},
            "Quality": {"rich_text": {}},
            "Notes": {"rich_text": {}},
            "Status": {"select": {"options": STATUS_OPTIONS}},
        },
    }
    db = notion_request("POST", "/databases", payload)
    print(f"Created database: {db['id']}")
    return db["id"]


def populate_weeks(database_id: str) -> None:
    existing = notion_request("POST", f"/databases/{database_id}/query", {"page_size": 100})
    if existing.get("results"):
        print(f"Database already has {len(existing['results'])} rows — skipping populate.")
        return

    for week in WEEKS:
        body = {
            "parent": {"database_id": database_id},
            "properties": {
                "Week": {"title": [{"text": {"content": week["title"]}}]},
                "Phase": {"select": {"name": week["phase"]}},
                "Start": {"date": {"start": week["start"]}},
                "End": {"date": {"start": week["end"]}},
                "Run km": {"rich_text": [{"text": {"content": week["run_km"]}}]},
                "Running": {"rich_text": [{"text": {"content": week["running"]}}]},
                "Strength": {"rich_text": [{"text": {"content": week["strength"]}}]},
                "Mobility": {"rich_text": [{"text": {"content": week["mobility"]}}]},
                "Quality": {"rich_text": [{"text": {"content": week["quality"]}}]},
                "Notes": {"rich_text": [{"text": {"content": week["notes"]}}]},
                "Status": {"select": {"name": "Planned"}},
            },
        }
        notion_request("POST", "/pages", body)
        print(f"  + {week['title']}")


def main() -> int:
    page_id = workout_coach_page_id()
    print(f"Workout Coach page: {page_id}", flush=True)

    if not os.environ.get("NOTION_TOKEN", "").strip():
        print(
            "ERROR: NOTION_TOKEN is not set in .env\n\n"
            "Setup:\n"
            "1. https://www.notion.so/my-integrations → New integration\n"
            "2. Copy secret → NOTION_TOKEN in .env\n"
            "3. Open Workout Coach page → ... → Connect to → your integration\n"
            "4. Re-run this script",
            file=sys.stderr,
            flush=True,
        )
        return 1

    try:
        page = get_page(page_id)
    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr, flush=True)
        print(
            "\nIf you see 404/object_not_found: share the Workout Coach page with "
            "your integration (⋯ → Connect to).",
            file=sys.stderr,
            flush=True,
        )
        return 1

    title = ""
    for prop in page.get("properties", {}).values():
        if prop.get("type") == "title":
            title = "".join(t.get("plain_text", "") for t in prop.get("title", []))
    print(f"Page title: {title or '(untitled)'}")

    ensure_overview_on_page(page_id)
    database_id = create_database(page_id)
    populate_weeks(database_id)

    save_state(
        {
            "workout_coach_page_id": page_id,
            "database_id": database_id,
            "bootstrapped_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    print(f"\nDone. Database id saved to data/notion_state.json")
    print(f"Open: https://www.notion.so/{database_id.replace('-', '')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
