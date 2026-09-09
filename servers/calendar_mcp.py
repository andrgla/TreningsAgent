"""Calendar MCP with Trening-only write access.

Reads all calendars. Creates and deletes events only on the calendar named
Trening (configurable via TRAINING_CALENDAR_NAME or CALENDAR_WRITABLE_NAME).

Backed by macOS EventKit locally and iCloud CalDAV in the cloud — see
calendar_backend.
"""

from __future__ import annotations

import json
import os
from datetime import date, datetime, timedelta

from mcp.server.fastmcp import FastMCP

from calendar_backend import (
    create_event as bridge_create,
    delete_event as bridge_delete,
    list_calendars as bridge_list_calendars,
    list_events as bridge_list_events,
    today_events as bridge_today,
)

mcp = FastMCP("calendar")

WRITE_CALENDAR = (
    os.environ.get("TRAINING_CALENDAR_NAME")
    or os.environ.get("CALENDAR_WRITABLE_NAME")
    or "Trening"
).strip().lower()
_trening_id: str | None = None


def _trening_calendar() -> dict | None:
    for cal in bridge_list_calendars():
        if (cal.get("title") or "").strip().lower() == WRITE_CALENDAR:
            return cal
    return None


def _trening_id() -> str:
    global _trening_id
    if _trening_id:
        return _trening_id
    cal = _trening_calendar()
    if not cal:
        raise RuntimeError(
            f'Calendar "{WRITE_CALENDAR.title()}" not found. Create it in the Calendar app.'
        )
    _trening_id = cal["id"]
    return _trening_id


def _annotate_calendars(cals: list[dict]) -> list[dict]:
    out = []
    for cal in cals:
        writable = (cal.get("title") or "").strip().lower() == WRITE_CALENDAR
        out.append(
            {
                **cal,
                "access": "read-write" if writable else "read-only",
                "writableByAgent": writable,
            }
        )
    return out


def _dump(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2, default=str)


def _reject_write(cal_title: str, action: str) -> str:
    return (
        f'Refused to {action}: calendar "{cal_title}" is read-only. '
        f'Agent writes are allowed only on "{WRITE_CALENDAR.title()}".'
    )


def _find_event(event_id: str, occurrence_date: str | None = None) -> dict | None:
    """Locate an event across calendars to verify its calendar before delete."""
    if occurrence_date:
        try:
            occ = datetime.fromisoformat(occurrence_date.replace("Z", "+00:00"))
            start = (occ - timedelta(days=1)).strftime("%Y-%m-%dT00:00:00Z")
            end = (occ + timedelta(days=2)).strftime("%Y-%m-%dT00:00:00Z")
        except ValueError:
            start, end = _default_search_range()
    else:
        start, end = _default_search_range()

    for event in bridge_list_events(start, end):
        if event.get("id") == event_id or event.get("externalId") == event_id:
            return event
    return None


def _default_search_range() -> tuple[str, str]:
    today = date.today()
    start = (today - timedelta(days=30)).isoformat() + "T00:00:00Z"
    end = (today + timedelta(days=400)).isoformat() + "T23:59:59Z"
    return start, end


@mcp.tool()
def get_calendars() -> str:
    """List calendars. Only Trening is writable; all others are read-only."""
    try:
        return _dump(_annotate_calendars(bridge_list_calendars()))
    except Exception as e:  # noqa: BLE001
        return f"Could not list calendars: {e}"


@mcp.tool()
def get_events(
    start_date: str,
    end_date: str,
    calendars: str = "",
    calendar_ids: str = "",
) -> str:
    """Events in a date range (ISO8601). Optional comma-separated calendar names or ids."""
    try:
        names = [c.strip() for c in calendars.split(",") if c.strip()] or None
        ids = [c.strip() for c in calendar_ids.split(",") if c.strip()] or None
        events = bridge_list_events(start_date, end_date, calendars=names, calendar_ids=ids)
        return _dump(events)
    except Exception as e:  # noqa: BLE001
        return f"Could not fetch events: {e}"


@mcp.tool()
def get_today_events() -> str:
    """All events today across every calendar (read-only view)."""
    try:
        return _dump(bridge_today())
    except Exception as e:  # noqa: BLE001
        return f"Could not fetch today's events: {e}"


@mcp.tool()
def search_events(query: str, start_date: str = "", end_date: str = "") -> str:
    """Search event title, location, or notes (case-insensitive)."""
    try:
        if not start_date or not end_date:
            today = date.today()
            start_date = start_date or (today.isoformat() + "T00:00:00Z")
            end_date = end_date or (
                (today + timedelta(days=30)).isoformat() + "T23:59:59Z"
            )
        needle = query.lower()
        events = bridge_list_events(start_date, end_date)
        hits = [
            e
            for e in events
            if needle in (e.get("title") or "").lower()
            or needle in (e.get("location") or "").lower()
            or needle in (e.get("notes") or "").lower()
        ]
        return _dump(hits)
    except Exception as e:  # noqa: BLE001
        return f"Search failed: {e}"


@mcp.tool()
def create_event(
    title: str,
    start_date: str,
    end_date: str,
    time_zone: str = "Europe/Oslo",
    all_day: bool = False,
    location: str = "",
    notes: str = "",
    calendar_id: str = "",
) -> str:
    """Create an event on the Trening calendar only. Other calendars are rejected."""
    try:
        trening_id = _trening_id()
        if calendar_id and calendar_id != trening_id:
            cal = next(
                (c for c in bridge_list_calendars() if c.get("id") == calendar_id),
                None,
            )
            title_name = (cal or {}).get("title", calendar_id)
            return _reject_write(str(title_name), "create event")
        event = bridge_create(
            calendar_id=trening_id,
            title=title,
            start=start_date,
            end=end_date,
            time_zone=time_zone or None,
            all_day=all_day,
            location=location or None,
            notes=notes or None,
        )
        return _dump(event)
    except Exception as e:  # noqa: BLE001
        return f"Could not create event: {e}"


@mcp.tool()
def delete_event(
    event_id: str,
    span: str = "this",
    occurrence_date: str = "",
) -> str:
    """Delete an event only if it lives on the Trening calendar."""
    try:
        trening_id = _trening_id()
        event = _find_event(event_id, occurrence_date or None)
        if not event:
            return f"Event {event_id} not found in the searchable date range."
        if event.get("calendarId") != trening_id:
            return _reject_write(event.get("calendarTitle", "?"), "delete event")
        bridge_delete(
            event_id=event_id,
            span=span if span in ("this", "all") else "this",
            occurrence=occurrence_date or None,
        )
        return _dump({"deleted": True, "eventId": event_id})
    except Exception as e:  # noqa: BLE001
        return f"Could not delete event: {e}"


if __name__ == "__main__":
    mcp.run()
