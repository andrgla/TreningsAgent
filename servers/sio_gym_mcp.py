"""MCP server for the SiO Athletica gym booking system (iBooking).

Tools:
  - list_centres            list SiO Athletica centres and their ids
  - list_classes            read the group-class schedule (public, no login)
  - my_bookings             list your current bookings (login required)
  - book_class              book a class          (login + SIO_ALLOW_BOOKING=true)
  - cancel_class            cancel a booking      (login + SIO_ALLOW_BOOKING=true)

Reads work without credentials. Writes require SIO_USERNAME / SIO_PASSWORD and
are gated behind SIO_ALLOW_BOOKING=true so an agent cannot book by accident.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime

from mcp.server.fastmcp import FastMCP

logging.getLogger("httpx").setLevel(logging.WARNING)

from ibooking_client import STUDIOS, IBookingError, SioClient, resolve_studio

mcp = FastMCP("sio-gym")

_client: SioClient | None = None


def client() -> SioClient:
    global _client
    if _client is None:
        _client = SioClient()
    return _client


def _writes_enabled() -> bool:
    return os.environ.get("SIO_ALLOW_BOOKING", "").lower() in ("1", "true", "yes")


def _fmt_time(iso: str) -> str:
    try:
        return datetime.strptime(iso, "%Y-%m-%d %H:%M:%S").strftime("%a %d %b %H:%M")
    except Exception:
        return iso


@mcp.tool()
def list_centres() -> str:
    """List the SiO Athletica centres you can book at, with their studio ids."""
    return "SiO Athletica centres:\n" + "\n".join(
        f"  {sid}  Athletica {name.capitalize()}" for name, sid in STUDIOS.items()
    )


@mcp.tool()
def list_classes(
    centre: str = "blindern",
    name_contains: str = "",
    only_bookable: bool = False,
    only_available: bool = False,
    limit: int = 40,
) -> str:
    """Read the SiO group-class schedule for a centre (no login needed).

    Args:
        centre: centre name ('blindern', 'vulkan', ...) or numeric studio id.
        name_contains: only classes whose name contains this text (e.g. 'spinning', 'run').
        only_bookable: only classes currently open for booking.
        only_available: only classes with a free spot.
        limit: max classes to return.
    """
    try:
        sid = resolve_studio(centre)
        days = client().get_schedule([sid])
    except (IBookingError, Exception) as e:  # noqa: BLE001
        return f"Could not fetch schedule: {e}"

    needle = name_contains.lower().strip()
    out: list[str] = []
    for day in days:
        for c in day.get("classes", []):
            if needle and needle not in c.get("name", "").lower():
                continue
            if only_bookable and not c.get("bookable"):
                continue
            avail = c.get("available")
            if only_available and (avail is None or avail <= 0):
                continue
            instructors = ", ".join(i.get("name", "") for i in c.get("instructors", []))
            spots = f"{avail}/{c.get('capacity')}" if avail is not None else "?"
            flag = "" if c.get("bookable") else "  [not bookable now]"
            out.append(
                f"[{c.get('id')}] {_fmt_time(c.get('from',''))}  {c.get('name')}"
                f"  ({spots} spots){' - ' + instructors if instructors else ''}"
                f"  @ {c.get('room','')}{flag}"
            )
            if len(out) >= limit:
                break
        if len(out) >= limit:
            break

    if not out:
        return "No matching classes found."
    header = f"Classes at studio {sid} (id in brackets = classId for booking):\n"
    return header + "\n".join(out)


@mcp.tool()
def my_bookings() -> str:
    """List your current SiO bookings. Requires SIO_USERNAME / SIO_PASSWORD."""
    try:
        bookings = client().get_bookings()
    except IBookingError as e:
        return f"Could not fetch bookings: {e}"
    except Exception as e:  # noqa: BLE001
        return f"Could not fetch bookings: {e}"
    if not bookings:
        return "You have no upcoming bookings."
    lines = []
    for b in bookings:
        cid = b.get("id") or b.get("classId")
        lines.append(
            f"[{cid}] {_fmt_time(b.get('from',''))}  {b.get('name','?')}"
            f"  @ {b.get('room', b.get('studio',{}).get('name','') if isinstance(b.get('studio'),dict) else '')}"
        )
    return "Your bookings:\n" + "\n".join(lines)


@mcp.tool()
def book_class(class_id: int) -> str:
    """Book a SiO class by its classId (from list_classes).

    Requires SIO_USERNAME / SIO_PASSWORD and SIO_ALLOW_BOOKING=true.
    Always confirm the specific class with the user before calling this.
    """
    if not _writes_enabled():
        return (
            "Booking is disabled. Set SIO_ALLOW_BOOKING=true in your .env to allow "
            "the agent to book classes, then confirm the class with the user first."
        )
    try:
        client().add_booking(class_id)
        return f"Booked class {class_id}. Remember: cancel at least 3h before to avoid a no-show."
    except IBookingError as e:
        return f"Booking failed: {e}"
    except Exception as e:  # noqa: BLE001
        return f"Booking failed: {e}"


@mcp.tool()
def cancel_class(class_id: int) -> str:
    """Cancel a SiO booking by its classId.

    Requires SIO_USERNAME / SIO_PASSWORD and SIO_ALLOW_BOOKING=true.
    SiO allows cancellation up to 3 hours before the class starts.
    """
    if not _writes_enabled():
        return "Booking changes are disabled. Set SIO_ALLOW_BOOKING=true in your .env to allow this."
    try:
        client().cancel_booking(class_id)
        return f"Cancelled booking for class {class_id}."
    except IBookingError as e:
        return f"Cancellation failed: {e}"
    except Exception as e:  # noqa: BLE001
        return f"Cancellation failed: {e}"


if __name__ == "__main__":
    mcp.run()
