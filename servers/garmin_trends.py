"""Derive medium-distance running fitness trends from Garmin data."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta
from statistics import mean
from typing import Any

from garmin_mcp import api, recent_activities


def _trend(recent: float | None, older: float | None, *, higher_is_better: bool) -> str:
    if recent is None or older is None:
        return "—"
    diff = recent - older
    if abs(diff) < 1.5:
        return "→"
    if higher_is_better:
        return "↑" if diff > 0 else "↓"
    return "↓" if diff > 0 else "↑"


def _fmt_pace(sec_per_km: float) -> str:
    m = int(sec_per_km // 60)
    s = int(sec_per_km % 60)
    return f"{m}:{s:02d}/km"


def _latest_vo2_samples(g: Any, dates: list[str]) -> list[tuple[str, float]]:
    """VO2 max is sparse in Garmin API — scan recent days for available readings."""
    samples: list[tuple[str, float]] = []
    for d in reversed(dates):
        raw = g.get_max_metrics(d) or []
        if not isinstance(raw, list):
            continue
        for entry in raw:
            generic = (entry or {}).get("generic") or {}
            val = generic.get("vo2MaxPreciseValue") or generic.get("vo2MaxValue")
            if val is not None:
                samples.append((d, float(val)))
                break
        if len(samples) >= 2:
            break
    return samples


def _fmt_race_time(seconds: int | float | None) -> str:
    if not seconds:
        return "—"
    sec = int(seconds)
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def collect_trends(days: int = 14) -> dict[str, Any]:
    """Pull ~2 weeks of recovery + fitness signals and interpret for HM training."""
    import json

    g = api()
    today = date.today()
    dates = [(today - timedelta(days=i)).isoformat() for i in range(days - 1, -1, -1)]

    def _day_metrics(d: str) -> tuple[str, int | None, str | None, int | None, float | None, int | None]:
        hrv_raw = g.get_hrv_data(d) or {}
        summary = hrv_raw.get("hrvSummary") or {}
        stats = g.get_stats(d) or {}
        rhr = stats.get("restingHeartRate")
        sleep_raw = g.get_sleep_data(d) or {}
        dto = sleep_raw.get("dailySleepDTO") or {}
        secs = dto.get("sleepTimeSeconds")
        hours = round(secs / 3600, 1) if secs else None
        score = (dto.get("sleepScores") or {}).get("overall", {}).get("value")
        return (
            d,
            summary.get("lastNightAvg"),
            summary.get("status"),
            int(rhr) if rhr is not None else None,
            hours,
            score,
        )

    by_date: dict[str, tuple[int | None, str | None, int | None, float | None, int | None]] = {}
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = {pool.submit(_day_metrics, d): d for d in dates}
        for fut in as_completed(futures):
            d, hrv_v, hrv_s, rhr, hours, score = fut.result()
            by_date[d] = (hrv_v, hrv_s, rhr, hours, score)

    hrv_vals = [(d, *by_date[d][:2]) for d in dates]
    rhr_vals = [(d, by_date[d][2]) for d in dates]
    sleep_h = [(d, by_date[d][3], by_date[d][4]) for d in dates]

    hrv_numbers = [v for _, v, _ in hrv_vals if v is not None]
    rhr_numbers = [v for _, v in rhr_vals if v is not None]
    sleep_numbers = [h for _, h, _ in sleep_h if h and h > 0]

    recent_hrv = mean([v for _, v, _ in hrv_vals[-3:] if v is not None]) if hrv_numbers else None
    older_hrv = mean([v for _, v, _ in hrv_vals[:-3] if v is not None]) if len(hrv_numbers) > 3 else None
    recent_rhr = mean([v for _, v in rhr_vals[-3:] if v is not None]) if rhr_numbers else None
    older_rhr = mean([v for _, v in rhr_vals[:-3] if v is not None]) if len(rhr_numbers) > 3 else None
    avg_sleep = mean(sleep_numbers) if sleep_numbers else None

    vo2_samples = _latest_vo2_samples(g, dates)
    vo2_latest = vo2_samples[0] if vo2_samples else None
    vo2_older = vo2_samples[1] if len(vo2_samples) > 1 else None

    race = g.get_race_predictions() or {}
    hm_sec = race.get("timeHalfMarathon")
    hm_pace = _fmt_pace(hm_sec / 21.097) if hm_sec else None

    acts = json.loads(recent_activities(30))
    runs = [a for a in acts if "run" in (a.get("type") or "")]
    easy_runs = [r for r in runs if r.get("distance_km", 0) >= 4][:6]
    avg_hr = round(mean(r["avg_hr"] for r in easy_runs if r.get("avg_hr")), 0) if easy_runs else None
    avg_pace_sec = None
    if easy_runs:
        secs = []
        for r in easy_runs:
            pace = r.get("pace", "")
            if "/" in pace:
                try:
                    m, s = pace.split("/")[0].split(":")
                    secs.append(int(m) * 60 + int(s))
                except ValueError:
                    pass
        if secs:
            avg_pace_sec = mean(secs)

    readiness_raw = g.get_morning_training_readiness(today.isoformat())
    readiness_score = None
    if isinstance(readiness_raw, dict):
        readiness_score = readiness_raw.get("score") or readiness_raw.get("trainingReadinessScore")

    signal_rows: list[list[str]] = []
    if hrv_numbers:
        signal_rows.append([
            "HRV (overnight)",
            f"{hrv_vals[-1][1] or '—'} ms",
            f"~{recent_hrv:.0f} vs {older_hrv:.0f} ms" if recent_hrv and older_hrv else "—",
            _trend(recent_hrv, older_hrv, higher_is_better=True),
            _hrv_note(hrv_vals, recent_hrv, older_hrv),
        ])
    if rhr_numbers:
        signal_rows.append([
            "Resting HR",
            f"{rhr_vals[-1][1] or '—'} bpm",
            f"~{recent_rhr:.0f} vs {older_rhr:.0f} bpm" if recent_rhr and older_rhr else "—",
            _trend(recent_rhr, older_rhr, higher_is_better=False),
            _rhr_note(recent_rhr, older_rhr),
        ])
    if sleep_numbers:
        signal_rows.append([
            "Sleep",
            f"{sleep_h[-1][1] or '—'} h",
            f"~{avg_sleep:.1f} h avg" if avg_sleep else "—",
            "↓" if avg_sleep and avg_sleep < 7.5 else "→",
            _sleep_note(sleep_h, avg_sleep),
        ])
    if vo2_latest:
        latest_val = vo2_latest[1]
        older_val = vo2_older[1] if vo2_older else None
        signal_rows.append([
            "VO2 max (running)",
            f"{latest_val:.1f}",
            vo2_older[0] if vo2_older else "—",
            _trend(latest_val, older_val, higher_is_better=True) if older_val else "→",
            "Stable aerobic engine — race predictor tracks fitness between updates.",
        ])
    if hm_sec:
        signal_rows.append([
            "Race predictor (HM)",
            _fmt_race_time(hm_sec),
            hm_pace or "—",
            "→",
            "Garmin's current-fitness estimate — gap to 5:25 goal is normal in base phase.",
        ])
    if avg_hr and avg_pace_sec:
        signal_rows.append([
            "Easy-run stress",
            f"HR {avg_hr}",
            _fmt_pace(avg_pace_sec),
            "↑" if avg_hr >= 155 else "→",
            _easy_hr_note(avg_hr, avg_pace_sec),
        ])
    if readiness_score is not None:
        signal_rows.append([
            "Training readiness",
            str(readiness_score),
            "today",
            "→",
            "Higher = greener light for quality; low = protect easy days.",
        ])

    going_well, focus_more = _insights(
        hrv_vals=hrv_vals,
        sleep_h=sleep_h,
        recent_hrv=recent_hrv,
        older_hrv=older_hrv,
        recent_rhr=recent_rhr,
        older_rhr=older_rhr,
        avg_sleep=avg_sleep,
        hm_sec=hm_sec,
        avg_hr=avg_hr,
        avg_pace_sec=avg_pace_sec,
    )

    return {
        "signal_rows": signal_rows,
        "going_well": going_well,
        "focus_more": focus_more,
        "raw": {
            "hrv_last": hrv_vals[-1] if hrv_vals else None,
            "rhr_last": rhr_vals[-1] if rhr_vals else None,
            "sleep_last": sleep_h[-1] if sleep_h else None,
            "race_half_sec": hm_sec,
            "race_half_pace": hm_pace,
            "vo2_latest": vo2_latest,
        },
    }


def _hrv_note(
    hrv_vals: list[tuple[str, int | None, str | None]],
    recent: float | None,
    older: float | None,
) -> str:
    last_val, last_status = hrv_vals[-1][1], hrv_vals[-1][2]
    if last_val and last_val < 40:
        return "Overnight HRV dipped — body asking for easy + sleep."
    if recent and older and recent > older + 3:
        return "HRV trending up — absorbing load well."
    if last_status == "BALANCED":
        return "In balanced range — recovery on track."
    return "Watch for stacked hard days."


def _rhr_note(recent: float | None, older: float | None) -> str:
    if recent and older and recent > older + 2:
        return "RHR creeping up — classic fatigue signal; ease aerobic intensity."
    if recent and older and recent < older - 2:
        return "RHR easing down — good recovery sign."
    return "Stable — keep monitoring around hard weeks."


def _sleep_note(
    sleep_h: list[tuple[str, float | None, int | None]],
    avg: float | None,
) -> str:
    short_nights = [d for d, h, _ in sleep_h if h and h < 6.5]
    if short_nights and short_nights[-1] == sleep_h[-1][0]:
        return f"Short night ({sleep_h[-1][1]} h) — protect tomorrow's session."
    if avg and avg < 7.5:
        return f"Avg {avg:.1f} h — below your 8 h glow-girl non-negotiable."
    return "Sleep supporting training."


def _easy_hr_note(avg_hr: float, avg_pace_sec: float) -> str:
    if avg_hr >= 160:
        return f"Easy runs ~{_fmt_pace(avg_pace_sec)} but HR {avg_hr:.0f} — likely too hot for true aerobic base."
    if avg_hr >= 150:
        return f"HR {avg_hr:.0f} on easy days — slow 10–15 s/km to build engine for 21 km."
    return "Aerobic stress looks controlled on easy days."


def _insights(
    *,
    hrv_vals: list[tuple[str, int | None, str | None]],
    sleep_h: list[tuple[str, float | None, int | None]],
    recent_hrv: float | None,
    older_hrv: float | None,
    recent_rhr: float | None,
    older_rhr: float | None,
    avg_sleep: float | None,
    hm_sec: int | float | None,
    avg_hr: float | None,
    avg_pace_sec: float | None,
) -> tuple[list[str], list[str]]:
    going_well: list[str] = []
    focus_more: list[str] = []

    if recent_hrv and older_hrv and recent_hrv >= older_hrv:
        going_well.append(
            f"**HRV recovering** — 3-night avg ~{recent_hrv:.0f} ms vs ~{older_hrv:.0f} ms prior. "
            "Body is absorbing the return to structure."
        )
    last_hrv = hrv_vals[-1][1] if hrv_vals else None
    if last_hrv and last_hrv >= 55:
        going_well.append(
            f"**Last night HRV {last_hrv} ms (balanced)** — green light for easy aerobic work today, not all-out."
        )

    if hm_sec:
        goal_sec = 114 * 60 + 20  # 1:54:20
        gap_min = round((hm_sec - goal_sec) / 60)
        going_well.append(
            f"**Race predictor HM {_fmt_race_time(hm_sec)}** (~{_fmt_pace(hm_sec / 21.097)}) — "
            f"~{gap_min} min off race goal in base phase is expected; we're building, not peaking."
        )

    if recent_rhr and older_rhr and recent_rhr < older_rhr:
        going_well.append(
            f"**Resting HR easing** — ~{recent_rhr:.0f} bpm recently vs ~{older_rhr:.0f} bpm. Parasympathetic bounce."
        )

    # Negative / focus signals
    short = [(d, h) for d, h, _ in sleep_h if h and h < 6.5]
    if short:
        d, h = short[-1]
        focus_more.append(
            f"**Sleep debt** — {h} h on {d} tanked recovery (HRV/sleep score followed). "
            "8 h before the long run is the highest-ROI move this week."
        )
    elif avg_sleep and avg_sleep < 7.5:
        focus_more.append(
            f"**Sleep avg ~{avg_sleep:.1f} h** — under your 8 h target; HM fitness is built in bed as much as on the road."
        )

    if recent_rhr and older_rhr and recent_rhr > older_rhr + 2:
        focus_more.append(
            f"**RHR trend up** (~{recent_rhr:.0f} vs ~{older_rhr:.0f} bpm) — back off intensity until easy days feel truly easy."
        )

    if avg_hr and avg_hr >= 155 and avg_pace_sec:
        focus_more.append(
            f"**Easy pace vs HR mismatch** — recent ~{_fmt_pace(avg_pace_sec)} at HR ~{avg_hr:.0f}. "
            "For 21 km, slow easy runs to ~6:30–6:45/km until HR drops; that's how you earn 5:25 later."
        )

    if last_hrv and last_hrv < 45:
        focus_more.append(
            "**HRV suppressed** — no quality intervals yet; stack sleep + easy volume first (Week 1 plan is right)."
        )

    return going_well, focus_more
