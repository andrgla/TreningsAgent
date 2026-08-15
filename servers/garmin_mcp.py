"""Read-only MCP server for Garmin Connect.

Exposes training/recovery data useful for coaching: recent activities, sleep,
daily stats, HRV, training readiness/status and VO2max.

Auth: uses the `garminconnect` library. Set GARMIN_EMAIL and GARMIN_PASSWORD in
`.env`; tokens are cached under `data/.garminconnect` (override with GARMINTOKENS).

Note: Garmin actively changes its auth. If login stops working, upgrade
`garminconnect` (pip install -U garminconnect) or switch to a browser-based
Garmin MCP server.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import date, timedelta
from pathlib import Path

from mcp.server.fastmcp import FastMCP

logging.getLogger("httpx").setLevel(logging.WARNING)

mcp = FastMCP("garmin")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

def _load_env() -> None:
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


_load_env()


def api():
    """Return a shared, warm Garmin client.

    Delegates to ``garmin_auth.get_client`` so every process (this MCP server and
    the standalone scripts) shares one single-flight, fail-fast login path.
    """
    from garmin_auth import get_client

    return get_client()


def _today(d: str = "") -> str:
    return d or date.today().isoformat()


def _dump(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2, default=str)


_STRENGTH_TYPES = frozenset(
    {
        "strength_training",
        "fitness_equipment",
        "indoor_cardio",  # sometimes used for gym circuits
        "hiit",
        "cross_training",
    }
)


def _activity_summary(a: dict) -> dict:
    dist_km = (a.get("distance") or 0) / 1000
    dur_s = a.get("duration") or 0
    pace = ""
    if dist_km > 0 and dur_s:
        sec_per_km = dur_s / dist_km
        pace = f"{int(sec_per_km // 60)}:{int(sec_per_km % 60):02d}/km"
    return {
        "id": a.get("activityId"),
        "name": a.get("activityName"),
        "type": (a.get("activityType") or {}).get("typeKey"),
        "start": a.get("startTimeLocal"),
        "distance_km": round(dist_km, 2),
        "duration_min": round(dur_s / 60, 1),
        "pace": pace,
        "avg_hr": a.get("averageHR"),
        "max_hr": a.get("maxHR"),
    }


@mcp.tool()
def recent_activities(limit: int = 10) -> str:
    """List your most recent Garmin activities (name, type, distance, pace, HR, date)."""
    try:
        acts = api().get_activities(0, limit)
    except Exception as e:  # noqa: BLE001
        return f"Could not fetch activities: {e}"
    return _dump([_activity_summary(a) for a in acts])


@mcp.tool()
def recent_strength_sessions(limit: int = 10, weeks: int = 8) -> str:
    """List recent Garmin strength/gym sessions (strength_training, HIIT, etc.).

    Use this instead of Hevy: log strength on your watch in Hevy, and when Garmin
    records a strength activity it appears here. Helps track legs 2x/week cadence.
    """
    try:
        acts = api().get_activities(0, 80)
    except Exception as e:  # noqa: BLE001
        return f"Could not fetch activities: {e}"
    cutoff = date.today() - timedelta(days=7 * weeks)
    out = []
    for a in acts:
        type_key = ((a.get("activityType") or {}).get("typeKey") or "").lower()
        if type_key not in _STRENGTH_TYPES:
            continue
        start = (a.get("startTimeLocal") or "")[:10]
        try:
            if date.fromisoformat(start) < cutoff:
                continue
        except ValueError:
            continue
        out.append(_activity_summary(a))
        if len(out) >= limit:
            break
    if not out:
        return (
            "No strength sessions found in Garmin for this period. "
            "Start a Strength activity on your watch when you lift (or ensure "
            "Hevy → Garmin sync is on)."
        )
    days_since = None
    if out:
        try:
            last = date.fromisoformat(out[0]["start"][:10])
            days_since = (date.today() - last).days
        except ValueError:
            pass
    return _dump({"days_since_last": days_since, "sessions": out})


@mcp.tool()
def weekly_strength_summary(weeks: int = 4) -> str:
    """Count strength/gym sessions per week from Garmin over the past N weeks."""
    try:
        acts = api().get_activities(0, 100)
    except Exception as e:  # noqa: BLE001
        return f"Could not fetch activities: {e}"
    cutoff = date.today() - timedelta(days=7 * weeks)
    by_week: dict[str, int] = {}
    total = 0
    for a in acts:
        type_key = ((a.get("activityType") or {}).get("typeKey") or "").lower()
        if type_key not in _STRENGTH_TYPES:
            continue
        start = (a.get("startTimeLocal") or "")[:10]
        try:
            d = date.fromisoformat(start)
            if d < cutoff:
                continue
        except ValueError:
            continue
        # ISO week label: year-week
        week_key = f"{d.isocalendar().year}-W{d.isocalendar().week:02d}"
        by_week[week_key] = by_week.get(week_key, 0) + 1
        total += 1
    return _dump(
        {
            "weeks": weeks,
            "total_sessions": total,
            "sessions_per_week": by_week,
            "target": "2 leg-focused sessions per week",
        }
    )


@mcp.tool()
def activity_details(activity_id: int) -> str:
    """Get detailed splits/metrics for a specific Garmin activity id."""
    try:
        return _dump(api().get_activity_details(activity_id))
    except Exception as e:  # noqa: BLE001
        return f"Could not fetch activity {activity_id}: {e}"


@mcp.tool()
def sleep(day: str = "") -> str:
    """Sleep summary for a date (YYYY-MM-DD, default today): duration, stages, score."""
    try:
        data = api().get_sleep_data(_today(day))
    except Exception as e:  # noqa: BLE001
        return f"Could not fetch sleep: {e}"
    dto = data.get("dailySleepDTO", {}) if isinstance(data, dict) else {}
    summary = {
        "date": dto.get("calendarDate"),
        "sleep_seconds": dto.get("sleepTimeSeconds"),
        "deep": dto.get("deepSleepSeconds"),
        "light": dto.get("lightSleepSeconds"),
        "rem": dto.get("remSleepSeconds"),
        "awake": dto.get("awakeSleepSeconds"),
        "sleep_score": (dto.get("sleepScores") or {}).get("overall", {}).get("value"),
    }
    return _dump(summary)


@mcp.tool()
def daily_stats(day: str = "") -> str:
    """Daily stats for a date: steps, resting HR, stress, body battery, calories."""
    try:
        return _dump(api().get_stats(_today(day)))
    except Exception as e:  # noqa: BLE001
        return f"Could not fetch stats: {e}"


@mcp.tool()
def training_readiness(day: str = "") -> str:
    """Garmin training readiness score and contributing factors for a date."""
    try:
        return _dump(api().get_training_readiness(_today(day)))
    except Exception as e:  # noqa: BLE001
        return f"Training readiness unavailable: {e}"


@mcp.tool()
def training_status(day: str = "") -> str:
    """Garmin training status (load balance, acute/chronic load, VO2max trend)."""
    try:
        return _dump(api().get_training_status(_today(day)))
    except Exception as e:  # noqa: BLE001
        return f"Training status unavailable: {e}"


@mcp.tool()
def hrv(day: str = "") -> str:
    """Heart rate variability summary for a date (overnight HRV status)."""
    try:
        return _dump(api().get_hrv_data(_today(day)))
    except Exception as e:  # noqa: BLE001
        return f"HRV unavailable: {e}"


@mcp.tool()
def vo2max(day: str = "") -> str:
    """Max metrics including VO2max (running/cycling) for a date."""
    try:
        return _dump(api().get_max_metrics(_today(day)))
    except Exception as e:  # noqa: BLE001
        return f"VO2max unavailable: {e}"


@mcp.tool()
def weekly_running_summary(weeks: int = 1) -> str:
    """Summarise running volume (km, time, count) over the past N weeks."""
    try:
        acts = api().get_activities(0, 60)
    except Exception as e:  # noqa: BLE001
        return f"Could not fetch activities: {e}"
    cutoff = date.today() - timedelta(days=7 * weeks)
    total_km = total_min = count = 0.0
    for a in acts:
        if "run" not in ((a.get("activityType") or {}).get("typeKey") or ""):
            continue
        start = (a.get("startTimeLocal") or "")[:10]
        try:
            if date.fromisoformat(start) < cutoff:
                continue
        except ValueError:
            continue
        total_km += (a.get("distance") or 0) / 1000
        total_min += (a.get("duration") or 0) / 60
        count += 1
    return _dump(
        {
            "weeks": weeks,
            "runs": int(count),
            "total_km": round(total_km, 1),
            "total_hours": round(total_min / 60, 1),
            "avg_km_per_run": round(total_km / count, 1) if count else 0,
        }
    )


@mcp.tool()
def fitness_trends(days: int = 14) -> str:
    """Recovery + fitness trend summary for HM training: HRV, RHR, sleep, race predictor, easy-run HR."""
    try:
        from garmin_trends import collect_trends

        return _dump(collect_trends(days=days))
    except Exception as e:  # noqa: BLE001
        return f"Could not compute fitness trends: {e}"


if __name__ == "__main__":
    mcp.run()
