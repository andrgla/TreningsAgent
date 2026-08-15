"""Thin wrapper around apple-calendar-mcp's Swift apple-bridge binary."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any


def bridge_bin() -> str:
    env = os.environ.get("APPLE_BRIDGE_BIN")
    if env:
        return env
    # Default: local npm install in this repo.
    root = Path(__file__).resolve().parents[1]
    return str(
        root
        / "node_modules"
        / "apple-calendar-mcp"
        / "swift"
        / ".build"
        / "release"
        / "apple-bridge"
    )


def run_bridge(args: list[str]) -> Any:
    result = subprocess.run(
        [bridge_bin(), *args],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0 and not result.stdout.strip():
        raise RuntimeError(
            f"apple-bridge failed (exit {result.returncode}): {result.stderr.strip()}"
        )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        raise RuntimeError(
            f"Failed to parse apple-bridge output: {result.stdout[:300]}"
        ) from e
    if payload.get("status") == "error":
        raise RuntimeError(payload.get("error") or "Unknown bridge error")
    return payload.get("data")


def list_calendars() -> list[dict]:
    data = run_bridge(["calendars"])
    return data if isinstance(data, list) else []


def list_events(
    start: str,
    end: str,
    *,
    calendars: list[str] | None = None,
    calendar_ids: list[str] | None = None,
) -> list[dict]:
    args = ["events", "--start", start, "--end", end]
    if calendars:
        args.extend(["--calendars", *calendars])
    if calendar_ids:
        args.extend(["--calendar-ids", *calendar_ids])
    data = run_bridge(args)
    return data if isinstance(data, list) else []


def today_events() -> list[dict]:
    data = run_bridge(["today"])
    return data if isinstance(data, list) else []


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
    args = [
        "create-event",
        "--calendar-id",
        calendar_id,
        "--title",
        title,
        "--start",
        start,
        "--end",
        end,
    ]
    if time_zone:
        args.extend(["--time-zone", time_zone])
    if all_day:
        args.append("--all-day")
    if location:
        args.extend(["--location", location])
    if notes:
        args.extend(["--notes", notes])
    data = run_bridge(args)
    return data if isinstance(data, dict) else {"result": data}


def delete_event(
    *,
    event_id: str,
    span: str = "this",
    occurrence: str | None = None,
) -> None:
    args = ["delete-event", "--id", event_id, "--span", span]
    if occurrence:
        args.extend(["--occurrence", occurrence])
    run_bridge(args)
