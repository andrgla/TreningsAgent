"""iCloud CalDAV backend — the cloud-runnable twin of apple_bridge.

apple_bridge talks to macOS EventKit through a Swift binary, so it only works on
a Mac that has granted Calendar access to the calling GUI app. This module
speaks CalDAV to caldav.icloud.com instead, which works from any Linux runner.

It writes to the *same* iCloud calendars, so events created here sync straight
down to Calendar.app on the Mac and iPhone.

Contract: same five functions and the same dict shapes as apple_bridge, so
calendar_backend can swap between them without callers noticing.

Credentials (see .env.example):
  ICLOUD_USERNAME          Apple ID email
  ICLOUD_APP_PASSWORD      app-specific password from appleid.apple.com
  ICLOUD_CALDAV_URL        override; defaults to https://caldav.icloud.com/
"""

from __future__ import annotations

import os
import uuid
from datetime import date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

DEFAULT_URL = "https://caldav.icloud.com/"
DEFAULT_TZ = os.environ.get("TRAINING_TIMEZONE", "Europe/Oslo")

# href lookups for delete_event. list_events populates this; a cold delete falls
# back to a UID search across the account.
_HREF_BY_ID: dict[str, str] = {}
_principal = None


def _require(name: str) -> str:
    value = (os.environ.get(name) or "").strip()
    if not value:
        raise RuntimeError(
            f"{name} is not set. iCloud CalDAV needs ICLOUD_USERNAME and "
            "ICLOUD_APP_PASSWORD (create an app-specific password at "
            "appleid.apple.com → Sign-In and Security → App-Specific Passwords)."
        )
    return value


def principal():
    """Cached CalDAV principal for the iCloud account."""
    global _principal
    if _principal is not None:
        return _principal
    try:
        import caldav  # noqa: PLC0415
    except ImportError as e:  # pragma: no cover
        raise RuntimeError(
            "caldav is not installed. Run: pip install -r servers/requirements.txt"
        ) from e

    client = caldav.DAVClient(
        url=os.environ.get("ICLOUD_CALDAV_URL") or DEFAULT_URL,
        username=_require("ICLOUD_USERNAME"),
        password=_require("ICLOUD_APP_PASSWORD"),
    )
    _principal = client.principal()
    return _principal


def _calendars() -> list:
    return list(principal().calendars())


def _title_of(cal) -> str:
    try:
        return (cal.get_display_name() or "").strip()
    except Exception:  # noqa: BLE001
        return ""


def _supports_events(cal) -> bool:
    """Skip reminder/task-only collections, which iCloud also exposes."""
    try:
        comps = cal.get_supported_components()
    except Exception:  # noqa: BLE001
        return True
    return not comps or "VEVENT" in comps


def _as_dt(value: Any, tz: ZoneInfo) -> datetime | None:
    """icalendar gives date, naive datetime, or aware datetime — normalise."""
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=tz)
    if isinstance(value, date):
        return datetime.combine(value, time.min, tzinfo=tz)
    return None


def _parse_bound(raw: str, tz: ZoneInfo) -> datetime:
    """Accept the ISO shapes callers already pass to apple_bridge."""
    text = (raw or "").strip().replace("Z", "+00:00")
    if not text:
        raise ValueError("empty date bound")
    if len(text) == 10:  # YYYY-MM-DD
        text += "T00:00:00"
    dt = datetime.fromisoformat(text)
    return dt if dt.tzinfo else dt.replace(tzinfo=tz)


# --- read -------------------------------------------------------------------


def list_calendars() -> list[dict]:
    out = []
    for cal in _calendars():
        if not _supports_events(cal):
            continue
        out.append({"id": str(cal.url), "title": _title_of(cal), "source": "iCloud"})
    return out


def _event_dicts(cal, comp, tz: ZoneInfo) -> dict:
    uid = str(comp.get("uid") or "")
    start = _as_dt(getattr(comp.get("dtstart"), "dt", None), tz)
    end = _as_dt(getattr(comp.get("dtend"), "dt", None), tz)
    if end is None and start is not None:
        duration = comp.get("duration")
        end = start + (duration.dt if duration else timedelta(hours=1))
    all_day = isinstance(getattr(comp.get("dtstart"), "dt", None), date) and not isinstance(
        getattr(comp.get("dtstart"), "dt", None), datetime
    )
    # Recurrence instances share a UID, so key them by start to stay unique.
    event_id = f"{uid}::{start.isoformat()}" if (uid and comp.get("recurrence-id")) else uid
    return {
        "id": event_id,
        "uid": uid,
        "title": str(comp.get("summary") or ""),
        "startDate": start.isoformat() if start else "",
        "endDate": end.isoformat() if end else "",
        "allDay": all_day,
        "location": str(comp.get("location") or ""),
        "notes": str(comp.get("description") or ""),
        "calendarId": str(cal.url),
        "calendarTitle": _title_of(cal),
        "hasRecurrenceRules": bool(comp.get("rrule")),
    }


def list_events(
    start: str,
    end: str,
    *,
    calendars: list[str] | None = None,
    calendar_ids: list[str] | None = None,
) -> list[dict]:
    tz = ZoneInfo(DEFAULT_TZ)
    start_dt = _parse_bound(start, tz)
    end_dt = _parse_bound(end, tz)

    wanted_names = {c.strip().lower() for c in (calendars or []) if c.strip()}
    wanted_ids = {c.strip() for c in (calendar_ids or []) if c.strip()}

    out: list[dict] = []
    for cal in _calendars():
        if not _supports_events(cal):
            continue
        title = _title_of(cal)
        if wanted_names and title.lower() not in wanted_names:
            continue
        if wanted_ids and str(cal.url) not in wanted_ids:
            continue
        try:
            # expand=True materialises recurring instances (lectures, standing
            # commitments) so availability reads are accurate.
            results = cal.search(start=start_dt, end=end_dt, event=True, expand=True)
        except Exception:  # noqa: BLE001
            try:
                results = cal.search(start=start_dt, end=end_dt, event=True)
            except Exception:  # noqa: BLE001
                continue
        for item in results:
            try:
                vobj = item.icalendar_instance
            except Exception:  # noqa: BLE001
                continue
            for comp in vobj.walk("VEVENT"):
                record = _event_dicts(cal, comp, tz)
                if record["id"]:
                    _HREF_BY_ID[record["id"]] = str(item.url)
                    _HREF_BY_ID.setdefault(record["uid"], str(item.url))
                out.append(record)
    out.sort(key=lambda e: e.get("startDate") or "")
    return out


def today_events() -> list[dict]:
    tz = ZoneInfo(DEFAULT_TZ)
    today = datetime.now(tz).date()
    start = datetime.combine(today, time.min, tzinfo=tz)
    return list_events(start.isoformat(), (start + timedelta(days=1)).isoformat())


# --- write ------------------------------------------------------------------


def _calendar_by_id(calendar_id: str):
    for cal in _calendars():
        if str(cal.url) == calendar_id or _title_of(cal).lower() == calendar_id.strip().lower():
            return cal
    raise RuntimeError(f"Calendar {calendar_id!r} not found on this iCloud account.")


def _ics_dt(dt: datetime, all_day: bool) -> str:
    if all_day:
        return dt.strftime("%Y%m%d")
    return dt.astimezone(ZoneInfo("UTC")).strftime("%Y%m%dT%H%M%SZ")


def _escape(text: str) -> str:
    return (
        text.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\n", "\\n")
    )


def create_event(
    *,
    calendar_id: str,
    title: str,
    start: str,
    end: str,
    time_zone: str | None = None,
    all_day: bool = False,
    location: str | None = None,
    notes: str | None = None,
) -> dict:
    tz = ZoneInfo(time_zone or DEFAULT_TZ)
    cal = _calendar_by_id(calendar_id)
    start_dt = _parse_bound(start, tz)
    end_dt = _parse_bound(end, tz)
    uid = f"{uuid.uuid4()}@treningsagent"

    value_kind = ";VALUE=DATE" if all_day else ""
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//TreningsAgent//CalDAV//EN",
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"DTSTAMP:{_ics_dt(datetime.now(ZoneInfo('UTC')), False)}",
        f"DTSTART{value_kind}:{_ics_dt(start_dt, all_day)}",
        f"DTEND{value_kind}:{_ics_dt(end_dt, all_day)}",
        f"SUMMARY:{_escape(title)}",
    ]
    if location:
        lines.append(f"LOCATION:{_escape(location)}")
    if notes:
        lines.append(f"DESCRIPTION:{_escape(notes)}")
    lines += ["END:VEVENT", "END:VCALENDAR"]

    event = cal.save_event("\r\n".join(lines))
    _HREF_BY_ID[uid] = str(event.url)
    return {
        "id": uid,
        "title": title,
        "startDate": start_dt.isoformat(),
        "endDate": end_dt.isoformat(),
        "calendarId": str(cal.url),
        "calendarTitle": _title_of(cal),
    }


def _find_href(event_id: str) -> str | None:
    if event_id in _HREF_BY_ID:
        return _HREF_BY_ID[event_id]
    uid = event_id.split("::", 1)[0]
    if uid in _HREF_BY_ID:
        return _HREF_BY_ID[uid]
    # Cold process: ask each calendar for the UID directly.
    for cal in _calendars():
        if not _supports_events(cal):
            continue
        try:
            found = cal.event_by_uid(uid)
        except Exception:  # noqa: BLE001
            continue
        if found is not None:
            _HREF_BY_ID[uid] = str(found.url)
            return str(found.url)
    return None


def delete_event(
    *,
    event_id: str,
    span: str = "this",
    occurrence: str | None = None,
) -> None:
    """Delete an event by id.

    CalDAV deletes the whole VEVENT resource, so a single occurrence of a
    recurring series cannot be removed here. TreningsAgent only ever deletes the
    non-recurring sessions it created, so that limit never bites in practice.
    """
    href = _find_href(event_id)
    if not href:
        raise RuntimeError(f"Event {event_id} not found on iCloud.")
    import caldav  # noqa: PLC0415

    caldav.CalendarObjectResource(client=principal().client, url=href).delete()
    _HREF_BY_ID.pop(event_id, None)
    _HREF_BY_ID.pop(event_id.split("::", 1)[0], None)
