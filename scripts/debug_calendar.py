#!/usr/bin/env python3
"""Read-only: dump raw Trening events so we can see the bridge's JSON schema.

Creates/deletes nothing. Run in your Terminal and paste the output.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "servers"))

from apple_bridge import list_calendars, list_events  # noqa: E402

START = "2026-07-06T00:00:00Z"
END = "2026-07-12T23:59:59Z"


def main() -> int:
    print("=== CALENDARS ===")
    for cal in list_calendars():
        print(json.dumps({"title": cal.get("title"), "id": cal.get("id")}, ensure_ascii=False))

    print(f"\n=== EVENTS {START} .. {END} (all calendars) ===")
    events = list_events(START, END)
    print(f"total events returned: {len(events)}\n")

    if events:
        print("--- first event, ALL fields ---")
        print(json.dumps(events[0], ensure_ascii=False, indent=2))

    print("\n--- summary (title | start | calendarTitle | calendarId) ---")
    for ev in events:
        print(
            f"{ev.get('title')!r} | {ev.get('start')!r} | "
            f"{ev.get('calendarTitle')!r} | {ev.get('calendarId')!r}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
