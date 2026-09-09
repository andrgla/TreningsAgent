#!/usr/bin/env python3
"""Check that the iCloud CalDAV calendar backend is ready for the cloud jobs.

Run this before switching the schedule over. It answers the three questions the
cloud jobs depend on:

  1. Do the iCloud credentials work?          (app-specific password, not your
                                               Apple ID password)
  2. Does the Trening calendar live in iCloud? (a calendar created "On My Mac"
                                               is invisible to CalDAV)
  3. Can it read this week's events?           (the coach infers availability
                                               and drinking days from them)

  ./.venv/bin/python scripts/caldav_doctor.py

Add --write to also create and immediately delete a probe event on Trening,
which is the only way to be sure writes will work unattended.

Prints no credentials — only calendar names and counts.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "servers"))

# CalDAV is the point of this script — never let it pick EventKit.
os.environ["CALENDAR_BACKEND"] = "caldav"

TZ = ZoneInfo("Europe/Oslo")
WRITE_CALENDAR = (
    os.environ.get("TRAINING_CALENDAR_NAME")
    or os.environ.get("CALENDAR_WRITABLE_NAME")
    or "Trening"
).strip()


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


def main() -> int:
    parser = argparse.ArgumentParser(description="Check the iCloud CalDAV backend.")
    parser.add_argument(
        "--write",
        action="store_true",
        help=f"Also create and delete a probe event on {WRITE_CALENDAR}.",
    )
    args = parser.parse_args()

    load_env_file(ROOT / ("." + "env"))

    missing = [
        name
        for name in ("ICLOUD_USERNAME", "ICLOUD_APP_PASSWORD")
        if not (os.environ.get(name) or "").strip()
    ]
    if missing:
        print(f"FAIL: {', '.join(missing)} not set.", file=sys.stderr)
        print(
            "  Create an app-specific password at appleid.apple.com → "
            "Sign-In and Security → App-Specific Passwords,\n"
            "  then add ICLOUD_USERNAME and ICLOUD_APP_PASSWORD to your local "
            "env file.",
            file=sys.stderr,
        )
        return 1

    import caldav_backend as backend  # noqa: PLC0415

    # 1. credentials + calendar discovery
    try:
        calendars = backend.list_calendars()
    except Exception as e:  # noqa: BLE001
        print(f"FAIL: could not reach iCloud CalDAV — {e}", file=sys.stderr)
        print(
            "  A 401 here almost always means a regular Apple ID password was "
            "used instead of an app-specific one.",
            file=sys.stderr,
        )
        return 1

    print(f"Connected to iCloud as {os.environ['ICLOUD_USERNAME']}")
    print(f"Found {len(calendars)} calendar(s):")
    for cal in calendars:
        mark = "  ← writes go here" if cal["title"].lower() == WRITE_CALENDAR.lower() else ""
        print(f"  - {cal['title']}{mark}")

    target = next(
        (c for c in calendars if c["title"].lower() == WRITE_CALENDAR.lower()), None
    )
    if not target:
        print(
            f"\nFAIL: no iCloud calendar named {WRITE_CALENDAR!r}.\n"
            "  If it exists in Calendar.app, it is probably stored under "
            '"On My Mac" rather than iCloud.\n'
            "  Create it under the iCloud account (Calendar.app → File → New "
            "Calendar → iCloud) and move the events across.",
            file=sys.stderr,
        )
        return 1

    # 2. read this week
    now = datetime.now(TZ)
    start = now - timedelta(days=now.weekday())
    end = start + timedelta(days=7)
    try:
        events = backend.list_events(start.isoformat(), end.isoformat())
    except Exception as e:  # noqa: BLE001
        print(f"\nFAIL: could not read events — {e}", file=sys.stderr)
        return 1

    on_target = [e for e in events if e["calendarId"] == target["id"]]
    print(
        f"\nRead {len(events)} event(s) this week across all calendars, "
        f"{len(on_target)} on {WRITE_CALENDAR}."
    )
    if not events:
        print(
            "  Note: zero events everywhere is suspicious — if your calendars "
            "are not empty this week,\n"
            "  they may not be syncing to iCloud."
        )

    # 3. optional write probe
    if args.write:
        probe_start = (now + timedelta(days=1)).replace(
            hour=4, minute=0, second=0, microsecond=0
        )
        print(f"\nCreating a probe event on {WRITE_CALENDAR}…")
        try:
            created = backend.create_event(
                calendar_id=target["id"],
                title="TreningsAgent CalDAV probe",
                start=probe_start.isoformat(),
                end=(probe_start + timedelta(minutes=15)).isoformat(),
                time_zone="Europe/Oslo",
                notes="Safe to delete — written by scripts/caldav_doctor.py",
            )
            print(f"  created {created['id']}")
            backend.delete_event(event_id=created["id"])
            print("  deleted again — writes work")
        except Exception as e:  # noqa: BLE001
            print(f"\nFAIL: write probe failed — {e}", file=sys.stderr)
            return 1

    print("\nOK — the CalDAV backend is ready for the scheduled cloud jobs.")
    if not args.write:
        print("  Re-run with --write to also verify that writes succeed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
