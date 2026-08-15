#!/usr/bin/env python3
"""Push the next 7-day training block to the Trening Apple calendar."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "servers"))

from data.q3_training_program import CALENDAR_WEEK  # noqa: E402
from apple_bridge import (  # noqa: E402
    create_event,
    delete_event,
    list_calendars,
    list_events,
)

WRITE_CALENDAR = "Trening"
TIME_ZONE = "Europe/Oslo"
_TZ = ZoneInfo(TIME_ZONE)

# (title, date) entries no longer in the plan that should be deleted if present
# (e.g. removed rest-day placeholders from earlier runs).
OBSOLETE_KEYS: set[tuple[str, str]] = {
    ("Rest / mobility optional", "2026-07-08"),
}


def trening_calendar_id() -> str:
    for cal in list_calendars():
        if (cal.get("title") or "").strip().lower() == WRITE_CALENDAR.lower():
            return cal["id"]
    raise RuntimeError(
        f'Calendar "{WRITE_CALENDAR}" not found. Create it in the Calendar app.'
    )


def iso_with_offset(dt_local: str) -> str:
    """Attach the Europe/Oslo offset (DST-aware) so apple-bridge accepts it."""
    dt = datetime.fromisoformat(dt_local)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=_TZ)
    return dt.isoformat()


def _on_trening(ev: dict, cal_id: str) -> bool:
    if ev.get("calendarId") == cal_id:
        return True
    return (ev.get("calendarTitle") or "").strip().lower() == WRITE_CALENDAR.lower()


def _start_raw(ev: dict) -> str:
    """The bridge returns startDate (ISO, UTC); older shapes used start."""
    return ev.get("startDate") or ev.get("start") or ""


def _local_date(ev: dict) -> str:
    """Local (Europe/Oslo) YYYY-MM-DD for the event start."""
    raw = _start_raw(ev)
    if not raw:
        return ""
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if dt.tzinfo is not None:
            dt = dt.astimezone(_TZ)
        return dt.date().isoformat()
    except ValueError:
        return raw[:10]


def existing_events(cal_id: str) -> dict[tuple[str, str], list[dict]]:
    """Map (title, YYYY-MM-DD local) -> Trening events in the plan range.

    Filters to the Trening calendar in Python rather than trusting the bridge's
    --calendar-ids flag, which proved unreliable.
    """
    dates = [s["date"] for s in CALENDAR_WEEK]
    start = f"{min(dates)}T00:00:00Z"
    end = f"{max(dates)}T23:59:59Z"
    groups: dict[tuple[str, str], list[dict]] = {}
    for ev in list_events(start, end):
        if not _on_trening(ev, cal_id):
            continue
        title = (ev.get("title") or "").strip()
        ev_date = _local_date(ev)
        if title and ev_date:
            groups.setdefault((title, ev_date), []).append(ev)
    return groups


def _event_id(ev: dict) -> str | None:
    return ev.get("id") or ev.get("eventId") or ev.get("externalId")


def _delete(ev: dict) -> bool:
    eid = _event_id(ev)
    if not eid:
        return False
    occ = _start_raw(ev) if ev.get("hasRecurrenceRules") else None
    delete_event(event_id=eid, span="this", occurrence=occ or None)
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Push 7-day plan to Trening calendar")
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Actually create events (default is dry-run preview)",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Delete ALL matching plan events first, then recreate exactly one each",
    )
    args = parser.parse_args()

    cal_id = trening_calendar_id()
    print(f"Target calendar: {WRITE_CALENDAR} ({cal_id})\n")

    groups = existing_events(cal_id) if args.confirm else {}
    plan_keys = {(s["title"].strip(), s["date"]) for s in CALENDAR_WEEK}
    total_found = sum(len(v) for k, v in groups.items() if k in plan_keys)
    if args.confirm:
        print(f"Found {total_found} existing plan event(s) on Trening in range.\n")

    created = 0
    skipped = 0
    deleted = 0

    if args.confirm:
        for key, evs in groups.items():
            if key in OBSOLETE_KEYS:
                # Removed from the plan (e.g. rest days) — always delete every copy.
                extras = evs
            elif key in plan_keys:
                # --reset removes every copy; default keeps first, removes extras.
                extras = evs if args.reset else evs[1:]
            else:
                continue
            for ev in extras:
                try:
                    if _delete(ev):
                        deleted += 1
                        print(f"Removed: {key[1]} {key[0]}")
                except Exception as e:  # noqa: BLE001
                    print(f"Could not remove {key[1]} {key[0]}: {e}")
        if args.reset:
            groups = {k: v for k, v in groups.items() if k not in plan_keys}

    for session in CALENDAR_WEEK:
        start = iso_with_offset(session["start"])
        end = iso_with_offset(session["end"])
        key = (session["title"].strip(), session["date"])

        if args.confirm and groups.get(key):
            skipped += 1
            print(f"Skipped (exists): {session['date']} {session['title']}")
            continue

        if args.confirm:
            create_event(
                calendar_id=cal_id,
                title=session["title"],
                start=start,
                end=end,
                time_zone=TIME_ZONE,
                notes=session["notes"],
            )
            created += 1
            print(f"Created: {session['date']} {session['title']}")
        else:
            print(f"[dry-run] {session['date']} {session['title']}  {start} → {end}")

    if not args.confirm:
        print("\nDry run only. Re-run with --confirm to create events on Trening.")
    else:
        print(
            f"\nCreated {created}, skipped {skipped} already present, "
            f"removed {deleted}."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
