"""Q3 2026 training program: Trondheim Halvmaraton build (Jul 5 → Aug 31).

Race target: 21.1 km @ 5:25/km (~1:54:20), race ~early September 2026.
"""

from __future__ import annotations

PROGRAM_OVERVIEW = """# 🏃‍♀️ Trondheim Halvmaraton — Q3 glow-up (Jul–Aug 2026)

**Race:** ~early September 2026 · **Target:** 5:25/km · **Finish:** ~1:54:20 ✨

Okay bestie — this is the block where we stop hoping and start *becoming*. We build the engine, protect the body, and let the mind catch up to the girl who already ran this. 🫒

## 🌺 Weekly structure
- **Running:** 3–4 sessions (1 quality, 1 long, 1–2 easy)
- **Strength:** 2×/week legs/glutes (log on watch → Garmin strength) 🍑
- **Mobility:** 1× yoga or pilates 🩰
- **Easy pace:** 6:15–6:45/km · **Threshold:** 5:05–5:15/km · **Race pace:** 5:25/km

## 🩵 Phases
1. **Base build** (Jul 7–20) — volume, easy aerobic
2. **Race-specific build** (Jul 21 – Aug 10) — threshold + race-pace work
3. **Peak** (Aug 11–24) — longest long runs, sharpen
4. **Taper prep** (Aug 25–31) — reduce volume, keep short quality

## 🌷 Eda's law
- Easy days *actually* easy — the glow is built there, not burned. 🌱
- One hard session at a time. We're patient because we're confident. 💫
- Mind + body on the same team: flat energy or bad sleep = we adapt, never punish.
- We're not chasing the race. We're becoming the runner who finishes it. 🌙 — Eda 🫒
"""

WEEKS: list[dict] = [
    {
        "week": 1,
        "title": "Week 1 — Base build",
        "start": "2026-07-07",
        "end": "2026-07-13",
        "phase": "Base",
        "run_km": "32–36",
        "running": "Tue easy 8 km · Thu easy 7 km · Sat long 12 km @ 6:20–6:40",
        "strength": "Mon legs/glutes · Fri upper + core (lighter)",
        "mobility": "Sun yoga or pilates 45 min",
        "quality": "None — all easy aerobic",
        "notes": "Establish rhythm. Keep HR conversational on easy days.",
    },
    {
        "week": 2,
        "title": "Week 2 — Base build",
        "start": "2026-07-14",
        "end": "2026-07-20",
        "phase": "Base",
        "run_km": "34–38",
        "running": "Mon easy 8 km · Wed easy 6 km · Sun long 14 km @ 6:15–6:35",
        "strength": "Tue legs/glutes · Sat short activation (30 min) before long if fresh",
        "mobility": "Fri pilates 45 min",
        "quality": "Optional strides: 4×20s after Wed easy",
        "notes": "+10% volume cap vs week 1. Sleep >7h before long run.",
    },
    {
        "week": 3,
        "title": "Week 3 — Race-specific build",
        "start": "2026-07-21",
        "end": "2026-07-27",
        "phase": "Build",
        "run_km": "36–40",
        "running": "Tue easy 8 km · Thu threshold 5×1 km @ 5:10 · Sun long 15 km w/ last 3 km @ 5:35",
        "strength": "Mon legs · Fri glute focus",
        "mobility": "Wed yoga 45 min",
        "quality": "Thu threshold — full recoveries 90s jog",
        "notes": "First structured quality. Skip quality if readiness low.",
    },
    {
        "week": 4,
        "title": "Week 4 — Race-specific build",
        "start": "2026-07-28",
        "end": "2026-08-03",
        "phase": "Build",
        "run_km": "38–42",
        "running": "Mon easy 7 km · Wed easy 8 km · Sat long 16 km @ 6:15–6:30",
        "strength": "Tue legs · Thu upper/core",
        "mobility": "Sun pilates",
        "quality": "Sat long: final 4 km steady @ 5:30–5:35 (race pace touch)",
        "notes": "Long run is the key session. Fuel if >75 min.",
    },
    {
        "week": 5,
        "title": "Week 5 — Build / peak intro",
        "start": "2026-08-04",
        "end": "2026-08-10",
        "phase": "Build",
        "run_km": "40–44",
        "running": "Tue easy 8 km · Thu 2×2 km @ 5:15 w/ 3 min jog · Sun long 17 km easy",
        "strength": "Mon legs · Fri glutes + hamstrings",
        "mobility": "Wed yoga",
        "quality": "Thu — controlled, not flat-out",
        "notes": "Peak weekly volume window. Monitor Garmin training load.",
    },
    {
        "week": 6,
        "title": "Week 6 — Peak",
        "start": "2026-08-11",
        "end": "2026-08-17",
        "phase": "Peak",
        "run_km": "40–42",
        "running": "Mon easy 8 km · Wed 5 km @ 5:25 race pace · Sat long 18 km @ 6:10–6:25",
        "strength": "Tue legs (moderate volume) · no heavy day before long",
        "mobility": "Fri pilates",
        "quality": "Wed race-pace rehearsal — even splits",
        "notes": "Longest long run block. Trust the base.",
    },
    {
        "week": 7,
        "title": "Week 7 — Peak",
        "start": "2026-08-18",
        "end": "2026-08-24",
        "phase": "Peak",
        "run_km": "36–40",
        "running": "Tue easy 7 km · Thu 6×800 m @ 5:00 · Sun long 16 km easy",
        "strength": "Mon legs · Thu only if recovered post-intervals",
        "mobility": "Sat yoga",
        "quality": "Thu VO2-ish — full recovery 2 min",
        "notes": "Last big quality before taper. Protect sleep.",
    },
    {
        "week": 8,
        "title": "Week 8 — Taper prep",
        "start": "2026-08-25",
        "end": "2026-08-31",
        "phase": "Taper prep",
        "run_km": "28–32",
        "running": "Mon easy 6 km · Wed 4 km w/ 2 km @ 5:25 · Sat easy 10 km",
        "strength": "Tue light legs · stop heavy loading",
        "mobility": "Thu pilates · Sun easy walk + stretch",
        "quality": "Wed short race-pace — sharp, not tiring",
        "notes": "Enter September fresh. Race ~1–2 weeks after this block.",
    },
]

# Week 4 — Race-specific build (Mon 28 Jul – Sun 3 Aug)
# Rebuild volume after soft weeks (~15–16 km); aim ~37 km toward 38–42 band.
# Evening weekday slots: calendar unavailable for drinking-day scan.
CALENDAR_WEEK: list[dict] = [
    {
        "date": "2026-07-28",
        "title": "🏃 Easy run 7 km",
        "start": "2026-07-28T17:30:00",
        "end": "2026-07-28T18:20:00",
        "notes": "Easy 6:30–6:45/km · keep HR honest (not ~157) · Week 4 build · — Eda 🫒",
    },
    {
        "date": "2026-07-29",
        "title": "🦵 Legs + glutes (strength)",
        "start": "2026-07-29T17:00:00",
        "end": "2026-07-29T18:15:00",
        "notes": "Hevy on watch · hip thrust, RDL, split squat, glute bridge · RPE 7–8 · glow girl legs",
    },
    {
        "date": "2026-07-30",
        "title": "🏃 Easy run 8 km",
        "start": "2026-07-30T17:30:00",
        "end": "2026-07-30T18:25:00",
        "notes": "Easy 6:30–6:45/km · conversational · optional 4×20s strides last 2 km",
    },
    {
        "date": "2026-07-31",
        "title": "🦵 Glute focus (strength)",
        "start": "2026-07-31T17:00:00",
        "end": "2026-07-31T18:00:00",
        "notes": "Second legs hit · abduction, kickbacks, bridges · RPE 7 · log in Hevy",
    },
    {
        "date": "2026-08-01",
        "title": "🏃 Easy run 6 km",
        "start": "2026-08-01T17:30:00",
        "end": "2026-08-01T18:15:00",
        "notes": "Shakeout easy 6:30–6:45/km · protect legs for Saturday long",
    },
    {
        "date": "2026-08-02",
        "title": "🏃 Long run 16 km (race-pace finish)",
        "start": "2026-08-02T09:00:00",
        "end": "2026-08-02T10:50:00",
        "notes": "Key session · 12 km @ 6:15–6:30 then last 4 km @ 5:30–5:35 · fuel if >75 min · 8 h sleep night before",
    },
    {
        "date": "2026-08-03",
        "title": "🧘 Pilates",
        "start": "2026-08-03T11:00:00",
        "end": "2026-08-03T12:00:00",
        "notes": "SiO or home · hips + core · keep running legs springy · cancel ≥3h if booked",
    },
]
