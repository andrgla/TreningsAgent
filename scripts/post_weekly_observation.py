#!/usr/bin/env python3
"""Ensure 'My recent observations' exists on Workout Coach and append a weekly note.

Pulls actuals from Garmin + targets from Notion. Idempotent section setup.
Use --refresh to replace the latest observation for the current program week.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import date, datetime
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
    list_block_children,
    md_rich_text,
    notion_request,
    query_database,
    load_state,
    workout_coach_page_id,
)
from garmin_mcp import api, recent_activities  # noqa: E402
from garmin_trends import collect_trends  # noqa: E402

SECTION_MARKER = "My recent observations"
DB_TITLE = "Q3 Training Weeks"
_STRENGTH = frozenset({"strength_training", "fitness_equipment", "hiit", "cross_training", "indoor_cardio"})
_MOBILITY = frozenset({"yoga", "pilates", "breathwork"})


def _plain(rich: list[dict]) -> str:
    return "".join(p.get("plain_text", "") for p in rich if isinstance(p, dict))


def _rt(text: str) -> list[dict]:
    return md_rich_text(text)


def _cell(text: str) -> list[dict]:
    return _rt(text)


def _table_row(cells: list[str]) -> dict:
    return {
        "object": "block",
        "type": "table_row",
        "table_row": {"cells": [_cell(c) for c in cells]},
    }


def _table(headers: list[str], rows: list[list[str]]) -> dict:
    return {
        "object": "block",
        "type": "table",
        "table": {
            "table_width": len(headers),
            "has_column_header": True,
            "has_row_header": False,
            "children": [_table_row(headers)] + [_table_row(r) for r in rows],
        },
    }


def _find_database_block(blocks: list[dict]) -> dict | None:
    for b in blocks:
        if b.get("type") == "child_database":
            title = b.get("child_database", {}).get("title", "")
            if DB_TITLE.lower() in title.lower():
                return b
    return None


def _find_section_heading(blocks: list[dict]) -> dict | None:
    for b in blocks:
        if b.get("type") != "heading_1":
            continue
        text = _plain(b.get("heading_1", {}).get("rich_text", []))
        if SECTION_MARKER.lower() in text.lower():
            return b
    return None


def ensure_section(page_id: str, blocks: list[dict]) -> None:
    if _find_section_heading(blocks):
        print("Observations section already present.")
        return
    db = _find_database_block(blocks)
    section = {
        "object": "block",
        "type": "heading_1",
        "heading_1": {"rich_text": _rt("🍒 My recent observations")},
    }
    body: dict = {"children": [section]}
    if db:
        idx = next(i for i, b in enumerate(blocks) if b["id"] == db["id"])
        if idx > 0:
            body["after"] = blocks[idx - 1]["id"]
    notion_request("PATCH", f"/blocks/{page_id}/children", body)
    print("Created observations section.")


def clear_observations_before_db(page_id: str) -> None:
    blocks = list_block_children(page_id)
    heading = _find_section_heading(blocks)
    db = _find_database_block(blocks)
    if not heading or not db:
        return
    delete_ids: list[str] = []
    past_heading = False
    for b in blocks:
        if b["id"] == heading["id"]:
            past_heading = True
            continue
        if b["id"] == db["id"]:
            break
        if past_heading:
            delete_ids.append(b["id"])
    for bid in delete_ids:
        notion_request("DELETE", f"/blocks/{bid}")
    if delete_ids:
        print(f"Cleared {len(delete_ids)} old observation block(s).")


def _current_week_row() -> dict:
    from data.q3_training_program import WEEKS  # noqa: PLC0415

    today = date.today()
    state = load_state()
    if state.get("database_id"):
        for page in query_database(state["database_id"]):
            start_s = ""
            end_s = ""
            title = ""
            row = {}
            for name, prop in page.get("properties", {}).items():
                ptype = prop.get("type")
                if ptype == "title":
                    title = _plain(prop.get("title", []))
                elif ptype == "date":
                    d = prop.get("date") or {}
                    if name.lower() == "start":
                        start_s = (d.get("start") or "")[:10]
                    elif name.lower() == "end":
                        end_s = (d.get("end") or d.get("start") or "")[:10]
                elif ptype == "rich_text" and name in (
                    "Run km", "Running", "Strength", "Mobility", "Quality", "Notes", "Phase",
                ):
                    row[name.lower().replace(" ", "_")] = _plain(prop.get("rich_text", []))
                elif ptype == "select" and name == "Phase":
                    row["phase"] = (prop.get("select") or {}).get("name", "")
            if start_s and end_s:
                try:
                    if date.fromisoformat(start_s) <= today <= date.fromisoformat(end_s):
                        return {
                            "week": title,
                            "start": start_s,
                            "end": end_s,
                            "run_km": row.get("run_km", ""),
                            "running": row.get("running", ""),
                            "strength": row.get("strength", ""),
                            "mobility": row.get("mobility", ""),
                            "quality": row.get("quality", ""),
                            "notes": row.get("notes", ""),
                            "phase": row.get("phase", ""),
                        }
                except ValueError:
                    pass
    for w in WEEKS:
        if date.fromisoformat(w["start"]) <= today <= date.fromisoformat(w["end"]):
            return w
    raise RuntimeError("No program week contains today's date.")


def _parse_activities() -> list[dict]:
    raw = recent_activities(40)
    if raw.startswith("Could not"):
        raise RuntimeError(raw)
    return json.loads(raw)


def _week_actuals(activities: list[dict], start: str, end: str) -> dict:
    start_d = date.fromisoformat(start)
    end_d = date.fromisoformat(end)
    runs = []
    strength = []
    mobility = []
    for a in activities:
        start_s = (a.get("start") or "")[:10]
        try:
            d = date.fromisoformat(start_s)
        except ValueError:
            continue
        if not (start_d <= d <= end_d):
            continue
        t = (a.get("type") or "").lower()
        if "run" in t:
            runs.append(a)
        elif t in _STRENGTH:
            strength.append(a)
        elif t in _MOBILITY:
            mobility.append(a)
    run_km = round(sum(a.get("distance_km", 0) for a in runs), 1)
    return {
        "runs": runs,
        "run_km": run_km,
        "run_count": len(runs),
        "strength": strength,
        "strength_count": len(strength),
        "mobility": mobility,
        "mobility_count": len(mobility),
    }


def _planned_runs_count(running: str) -> int:
    return len(re.findall(r"\b\d+\s*km\b", running, flags=re.I)) or 3


def _status(done: int, target: int, *, partial_ok: bool = False) -> str:
    if done >= target:
        return "✅"
    if done > 0 and partial_ok:
        return "🟡"
    if done == 0 and target > 0:
        return "🟡"
    return "🟡"


def build_observation() -> dict:
    week = _current_week_row()
    activities = _parse_activities()
    actual = _week_actuals(activities, week["start"], week["end"])
    trends = collect_trends(days=14)

    target_km = week.get("run_km", "32–36")
    planned_runs = _planned_runs_count(week.get("running", ""))
    target_legs = 2
    target_mobility = 1

    run_status = "✅" if actual["run_km"] >= 32 else "🟡"
    if actual["run_count"] == 0:
        run_status = "🟡"

    glance_rows = [
        ["Running km", target_km, str(actual["run_km"]), run_status],
        ["Runs", str(planned_runs), str(actual["run_count"]), _status(actual["run_count"], planned_runs)],
        ["Legs", str(target_legs), str(actual["strength_count"]), _status(actual["strength_count"], target_legs, partial_ok=True)],
        ["Mobility", str(target_mobility), str(actual["mobility_count"]), _status(actual["mobility_count"], target_mobility)],
    ]

    going_well: list[str] = list(trends["going_well"])
    focus_more: list[str] = list(trends["focus_more"])

    # Week adherence — only add if not already covered by trends
    if actual["strength_count"] and not any("Legs" in g or "strength" in g.lower() for g in going_well):
        s = actual["strength"][0]
        going_well.append(
            f"**Legs in the bank** — {s['start'][:10]} · {s['duration_min']:.0f} min logged (week-flexible ✅)."
        )

    if actual["run_count"] == 0 and not any("pace" in f.lower() or "HR" in f for f in focus_more):
        focus_more.append("**Easy 8 km** still to log this week — keep it 6:30–6:45/km.")
    if actual["strength_count"] < target_legs:
        focus_more.append(f"**Second legs session** still needed ({actual['strength_count']}/{target_legs}).")
    if actual["mobility_count"] < target_mobility:
        focus_more.append("**Mobility 1×** — yoga/pilates still on the week.")
    if not any("long" in f.lower() for f in focus_more):
        focus_more.append("**Long 12 km** weekend — anchor session for HM base.")

    verdict = _verdict(actual, trends)

    start_d = datetime.fromisoformat(week["start"]).strftime("%-d %b")
    end_d = datetime.fromisoformat(week["end"]).strftime("%-d %b %Y")
    week_label = f"{start_d}–{end_d} · {week.get('title', week.get('week', 'Current week'))}"

    next_bits = []
    if actual["run_count"] == 0:
        next_bits.append("easy 8 km")
    next_bits.append("Thu easy 7 km")
    next_bits.append("long 12 km weekend")

    return {
        "week_label": week_label,
        "verdict": verdict,
        "glance_rows": glance_rows,
        "signal_rows": trends["signal_rows"],
        "going_well": going_well[:4],
        "focus_more": focus_more[:4],
        "next_up": " · ".join(next_bits),
    }


def _verdict(actual: dict, trends: dict) -> str:
    raw = trends.get("raw", {})
    hrv_last = (raw.get("hrv_last") or [None, None])[1]
    sleep_last = (raw.get("sleep_last") or [None, None])[1]

    if sleep_last and sleep_last < 6 and hrv_last and hrv_last < 45:
        return (
            "Your body's whispering, not screaming — short sleep + softer HRV means we keep it gentle. "
            "Easy work only; we're playing the long HM game. 🌙"
        )
    if hrv_last and hrv_last >= 55 and actual["strength_count"]:
        return (
            "Recovery signals are green-ish and legs are banked — now we earn aerobic fitness with an *easy* 8 km, "
            "not a fast one. That's the glow girl engine build. ✨"
        )
    return (
        "Week 1 is about stacking smart reps toward 21 km — fitness trends say protect sleep & easy pace, "
        "and the week plan says you're on track. 🫒"
    )


def append_observation(page_id: str, *, after_block_id: str, data: dict) -> None:
    children: list[dict] = [
        {"object": "block", "type": "divider", "divider": {}},
        {
            "object": "block",
            "type": "heading_3",
            "heading_3": {"rich_text": _rt(data["week_label"])},
        },
        {
            "object": "block",
            "type": "callout",
            "callout": {
                "rich_text": _rt(data["verdict"]),
                "icon": {"type": "emoji", "emoji": "🫒"},
                "color": "pink_background",
            },
        },
        _table(
            ["Category", "Target", "Done so far", "Status"],
            data["glance_rows"],
        ),
    ]
    if data.get("signal_rows"):
        children.append(
            {
                "object": "block",
                "type": "heading_3",
                "heading_3": {"rich_text": _rt("📈 Fitness signals (14 d)")},
            }
        )
        children.append(
            _table(
                ["Signal", "Latest", "Trend", "↕", "Read"],
                data["signal_rows"],
            )
        )
    children.append(
        {
            "object": "block",
            "type": "heading_3",
            "heading_3": {"rich_text": _rt("✨ Going well")},
        }
    )
    for item in data["going_well"]:
        children.append(
            {
                "object": "block",
                "type": "bulleted_list_item",
                "bulleted_list_item": {"rich_text": _rt(item)},
            }
        )
    children.append(
        {
            "object": "block",
            "type": "heading_3",
            "heading_3": {"rich_text": _rt("🌱 Focus more")},
        }
    )
    for item in data["focus_more"]:
        children.append(
            {
                "object": "block",
                "type": "bulleted_list_item",
                "bulleted_list_item": {"rich_text": _rt(item)},
            }
        )
    if data.get("next_up"):
        children.append(
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {"rich_text": _rt(f"**Next up:** {data['next_up']}")},
            }
        )
    children.append(
        {
            "object": "block",
            "type": "paragraph",
            "paragraph": {"rich_text": _rt("— Eda 🫒")},
        }
    )
    notion_request(
        "PATCH",
        f"/blocks/{page_id}/children",
        {"children": children, "after": after_block_id},
    )
    print(f"Posted observation: {data['week_label']}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Post a weekly observation to Notion.")
    parser.add_argument("--refresh", action="store_true", help="Replace observations with a fresh Garmin-backed report.")
    args = parser.parse_args()

    if not os.environ.get("NOTION_TOKEN", "").strip():
        print("ERROR: NOTION_TOKEN not set in .env", file=sys.stderr)
        return 1
    if not os.environ.get("GARMIN_EMAIL", "").strip():
        print("ERROR: GARMIN_EMAIL not set in .env", file=sys.stderr)
        return 1

    print("Fetching Garmin data...")
    api()
    data = build_observation()

    page_id = workout_coach_page_id()
    blocks = list_block_children(page_id)
    ensure_section(page_id, blocks)

    if args.refresh:
        clear_observations_before_db(page_id)

    blocks = list_block_children(page_id)
    heading = _find_section_heading(blocks)
    if not heading:
        print("ERROR: observations heading not found", file=sys.stderr)
        return 1

    append_observation(page_id, after_block_id=heading["id"], data=data)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
