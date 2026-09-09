"""Pick the calendar backend for this machine.

Two implementations, one interface:

  apple_bridge     macOS EventKit via the Swift apple-bridge binary. Fast, no
                   credentials, but needs a Mac with Calendar access granted.
  caldav_backend   iCloud CalDAV over HTTPS. Works on any Linux runner, so this
                   is what the scheduled cloud jobs use.

Both write to the same iCloud calendars, so a session created in CI shows up in
Calendar.app on the Mac and iPhone.

Selection order:
  1. CALENDAR_BACKEND=apple|caldav        explicit override
  2. iCloud credentials present + not macOS → caldav
  3. macOS → apple, otherwise caldav
"""

from __future__ import annotations

import os
import platform


def _has_icloud_creds() -> bool:
    return bool(
        (os.environ.get("ICLOUD_USERNAME") or "").strip()
        and (os.environ.get("ICLOUD_APP_PASSWORD") or "").strip()
    )


def backend_name() -> str:
    choice = (os.environ.get("CALENDAR_BACKEND") or "").strip().lower()
    if choice in ("apple", "eventkit"):
        return "apple"
    if choice in ("caldav", "icloud"):
        return "caldav"
    if platform.system() != "Darwin":
        return "caldav"
    # On a Mac, EventKit needs no credentials and no network — prefer it.
    return "apple"


_BACKEND = backend_name()

if _BACKEND == "caldav":
    from caldav_backend import (  # noqa: F401
        create_event,
        delete_event,
        list_calendars,
        list_events,
        today_events,
    )
else:
    from apple_bridge import (  # noqa: F401
        create_event,
        delete_event,
        list_calendars,
        list_events,
        today_events,
    )

__all__ = [
    "backend_name",
    "create_event",
    "delete_event",
    "list_calendars",
    "list_events",
    "today_events",
]
