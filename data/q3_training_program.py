"""Q4 2026 training program: post-Trondheim rebuild block (Sep 21 → Dec 20).

Context: the Trondheim Halvmaraton (2026-09-06) was not run — Garmin shows no
activity 2026-09-02 → 2026-09-11. The next races already on the calendar are
Praha halvmaraton (2027-04-03) and Bergen Halvmaraton (2027-04-24), ~28 weeks
out. So Q4 is deliberately a BASE + STRENGTH quarter, not a race build: rebuild
aerobic volume, fix the easy-pace/HR mismatch, and finally hold glutes 2x/week.
The race-specific build for Praha belongs in Q1 2027.

Target for Praha: 21.1 km @ 5:25/km (~1:54:20).
"""

from __future__ import annotations

# Single source of truth for the Notion database name. Bump this for a new
# quarter so bootstrap creates a fresh database instead of reusing the old one.
DB_TITLE = "Q4 Training Weeks"

# Phase select options for the Notion database (must cover every WEEKS phase).
PHASE_OPTIONS = [
    {"name": "Reset", "color": "purple"},
    {"name": "Base", "color": "blue"},
    {"name": "Build", "color": "orange"},
    {"name": "Consolidate", "color": "green"},
]

# Sentinel used by bootstrap to decide whether this quarter's overview is
# already on the page, plus the header callout for this block.
OVERVIEW_SENTINEL = "Q4 rebuild"
HEADER_CALLOUT = (
    "**Hi, I'm Eda — your coach.** 🫒 **Q4 rebuild** — base + glutes, "
    "Sep–Dec 2026. Next start line: **Praha halvmaraton 3 April 2027** · "
    "5:25/km. Calendar = when you show up · this database = what each week "
    "looks like. We build the engine now so spring is easy. ✨"
)

PROGRAM_OVERVIEW = """# 🌙 Q4 rebuild — base & glutes (Sep–Dec 2026)

**Next start line:** Praha halvmaraton · **3 April 2027** · target 5:25/km (~1:54:20) ✨

Okay bestie, real talk with love: Trondheim on 6 September didn't happen, and we're not spending one second on guilt. 🫒 September was school, WAI, interviews and a body that was already whispering — you listened. That's not failure, that's data. The week is what matters, never one day.

Here's the good news: Praha is **28 weeks** away. That is *so* much runway. Which means this block gets to be the thing your running has actually been missing — not another panic build, but a real **base**. We build the engine now, and the spring build gets to feel easy. 💫

## 🌺 Weekly structure — her identity rhythm
- **Running:** 3×/week (2 easy + 1 long) — exactly the *jogger 2–3 ganger i uka* girl
- **Strength:** 2×/week legs & glutes 🍑 — this is the headline, not the side quest
- **Mobility:** 1× yoga — Thursdays 08:45 at Øya, already in your calendar 🩰
- **Easy pace:** 6:30–6:50/km · **Steady:** 6:00–6:15/km · **Threshold:** 5:15–5:25/km

## 🩵 Phases
1. **Reset** (Sep 21 – Oct 4) — gentle restart, re-anchor easy pace and sleep
2. **Aerobic base** (Oct 5 – Nov 8) — volume climbs, strides, glutes twice a week
3. **Strength-endurance build** (Nov 9 – Dec 6) — first threshold touches, long run grows
4. **Consolidate** (Dec 7 – Dec 20) — 16 km platform, hand off to the Praha build

## 🌱 What the data asked for
- **Easy runs have been too hot** — ~5:52/km at HR 165–170. That is not easy, babe, that's medium. We cap easy at **6:30–6:50/km, HR under 155**. Slow now = fast in April. 🌷
- **Resting HR crept 56 → 62 bpm** and sleep averaged **7.0 h** against your 8 h non-negotiable. Sleep *is* the training this block. 🌙
- **Strength was 5 sessions in 12 weeks** against a 24-session target. The glutes goal doesn't happen by accident — Tuesdays and Fridays are hers now. 🍑
- **Volume was ~15.5 km/week.** We finish this block around **32 km/week**. Patient, stacked, unglamorous, undefeated.

## 🌷 Eda's law
- Easy days *actually* easy — the glow is built there, not burned. 🌱
- Two legs sessions a week is the promise we keep to future-you in her jeans. 🍑
- Deload weeks are not lost weeks. They're where the fitness lands. 💫
- Mind + body on the same team: flat energy or bad sleep = we adapt, never punish.
- We're not chasing Praha. We're becoming the girl who's already ready for it. 🌙 — Eda 🫒
"""

WEEKS: list[dict] = [
    {
        "week": 1,
        "title": "Week 1 — Reset",
        "start": "2026-09-21",
        "end": "2026-09-27",
        "phase": "Reset",
        "run_km": "15–17",
        "running": "Mon easy 5 km · Wed easy 4 km · Sun long 7 km @ 6:40–7:00",
        "strength": "Tue legs/glutes (rebuild, RPE 6–7) · Fri glutes",
        "mobility": "Thu yoga 08:45 Øya treningssenter",
        "quality": "None — all easy, rebuild the habit",
        "notes": "Innflyttingsfest Fri 25 🍷 → Sat is rest (no early, no hard), long run moved to Sun 27. Start lower than you think you need to.",
    },
    {
        "week": 2,
        "title": "Week 2 — Reset",
        "start": "2026-09-28",
        "end": "2026-10-04",
        "phase": "Reset",
        "run_km": "17–19",
        "running": "Mon easy 5 km · Wed easy 5 km · Sat long 8 km @ 6:40–7:00",
        "strength": "Tue legs/glutes · Fri glutes",
        "mobility": "Thu yoga 08:45 Øya",
        "quality": "4×20s strides after Wed easy",
        "notes": "Easy means HR under 155 even if the watch says 6:50/km. Ego stays home. 8 h sleep target every night.",
    },
    {
        "week": 3,
        "title": "Week 3 — Aerobic base",
        "start": "2026-10-05",
        "end": "2026-10-11",
        "phase": "Base",
        "run_km": "19–21",
        "running": "Mon easy 6 km · Wed easy 5 km · Sat long 9 km @ 6:30–6:50",
        "strength": "Tue legs/glutes · Fri glutes",
        "mobility": "Thu yoga 08:45 Øya",
        "quality": "5×20s strides after Wed easy",
        "notes": "First full-rhythm week: 3 runs + 2 legs + 1 yoga. This is the shape of the whole block.",
    },
    {
        "week": 4,
        "title": "Week 4 — Base (deload)",
        "start": "2026-10-12",
        "end": "2026-10-18",
        "phase": "Base",
        "run_km": "15–17",
        "running": "Mon easy 5 km · Wed easy 4 km · Sat long 7 km",
        "strength": "Tue legs (lighter, RPE 6) · Fri glutes",
        "mobility": "Thu yoga 08:45 Øya",
        "quality": "None",
        "notes": "Deload. Not a lost week — this is where weeks 1–3 actually turn into fitness. 🌱",
    },
    {
        "week": 5,
        "title": "Week 5 — Aerobic base",
        "start": "2026-10-19",
        "end": "2026-10-25",
        "phase": "Base",
        "run_km": "21–23",
        "running": "Mon easy 6 km · Wed easy 6 km · Sat long 10 km @ 6:30–6:50",
        "strength": "Tue legs/glutes · Fri glutes",
        "mobility": "Thu yoga 08:45 Øya",
        "quality": "6×20s strides after Wed easy",
        "notes": "Double digits on the long run again. Check: is easy HR dropping at the same pace? That's the whole scoreboard.",
    },
    {
        "week": 6,
        "title": "Week 6 — Aerobic base",
        "start": "2026-10-26",
        "end": "2026-11-01",
        "phase": "Base",
        "run_km": "23–25",
        "running": "Mon easy 6 km · Wed easy 6 km · Sat long 12 km @ 6:30–6:45",
        "strength": "Tue legs/glutes · Fri glutes",
        "mobility": "Thu yoga 08:45 Øya",
        "quality": "Strides + last 2 km of Wed @ 6:05 steady",
        "notes": "Dark season starts — reflective vest, headlamp, and the jog happens while the sun's still up when the day allows. ☀️",
    },
    {
        "week": 7,
        "title": "Week 7 — Aerobic base",
        "start": "2026-11-02",
        "end": "2026-11-08",
        "phase": "Base",
        "run_km": "25–27",
        "running": "Mon easy 7 km · Wed easy 6 km · Sat long 13 km @ 6:30–6:45",
        "strength": "Tue legs/glutes · Fri glutes",
        "mobility": "Thu yoga 08:45 Øya",
        "quality": "3 km @ 6:00–6:10 steady inside Wed run",
        "notes": "Biggest week yet and it should still feel boring. Boring is the goal. Fuel the long run if over 75 min.",
    },
    {
        "week": 8,
        "title": "Week 8 — Build (deload)",
        "start": "2026-11-09",
        "end": "2026-11-15",
        "phase": "Build",
        "run_km": "19–21",
        "running": "Mon easy 5 km · Wed easy 5 km · Sat long 10 km",
        "strength": "Tue legs/glutes · Fri glutes",
        "mobility": "Thu yoga 08:45 Øya",
        "quality": "None",
        "notes": "Deload + reassess. Compare easy-run HR vs week 2 — if it's down at the same pace, the base is landing. 📈",
    },
    {
        "week": 9,
        "title": "Week 9 — Strength-endurance build",
        "start": "2026-11-16",
        "end": "2026-11-22",
        "phase": "Build",
        "run_km": "27–29",
        "running": "Mon easy 7 km · Wed tempo 7 km (3 km @ 5:35–5:45) · Sat long 14 km",
        "strength": "Tue legs/glutes · Fri glutes (lighter if Wed bit)",
        "mobility": "Thu yoga 08:45 Øya",
        "quality": "Wed tempo — first real threshold touch of the block",
        "notes": "Ten weeks of patience buys this. One hard session only — don't let the long run turn into a second one.",
    },
    {
        "week": 10,
        "title": "Week 10 — Strength-endurance build",
        "start": "2026-11-23",
        "end": "2026-11-29",
        "phase": "Build",
        "run_km": "29–31",
        "running": "Mon easy 7 km · Wed 8 km w/ 2×2 km @ 5:30 (2 min jog) · Sat long 15 km",
        "strength": "Tue legs/glutes · Fri glutes",
        "mobility": "Thu yoga 08:45 Øya",
        "quality": "Wed 2×2 km @ threshold",
        "notes": "Block's biggest week. If readiness and mood are both low, move the tempo — never force it. 🩵",
    },
    {
        "week": 11,
        "title": "Week 11 — Build (deload)",
        "start": "2026-11-30",
        "end": "2026-12-06",
        "phase": "Build",
        "run_km": "23–25",
        "running": "Mon easy 6 km · Wed easy 6 km · Sat long 12 km",
        "strength": "Tue legs/glutes · Fri glutes",
        "mobility": "Thu yoga 08:45 Øya",
        "quality": "Strides only",
        "notes": "Exam-season deload — no exam dates in the calendar yet, so shift this week if yours land elsewhere. Training serves the life, not the reverse. 📚",
    },
    {
        "week": 12,
        "title": "Week 12 — Consolidate",
        "start": "2026-12-07",
        "end": "2026-12-13",
        "phase": "Consolidate",
        "run_km": "28–30",
        "running": "Mon easy 7 km · Wed 8 km w/ 3×2 km @ 5:30 (2 min jog) · Sat long 14 km",
        "strength": "Tue legs/glutes · Fri glutes",
        "mobility": "Thu yoga 08:45 Øya",
        "quality": "Wed 3×2 km @ threshold",
        "notes": "Winter footing: if it's icy, run by effort and bin the paces. Ice beats every training plan ever written. ❄️",
    },
    {
        "week": 13,
        "title": "Week 13 — Consolidate",
        "start": "2026-12-14",
        "end": "2026-12-20",
        "phase": "Consolidate",
        "run_km": "31–33",
        "running": "Mon easy 7 km · Wed easy 6 km + strides · Sat long 16 km (last 3 km @ 5:45)",
        "strength": "Tue legs/glutes · Fri glutes",
        "mobility": "Thu yoga 08:45 Øya",
        "quality": "Long-run finish @ 5:45 — controlled, not a race",
        "notes": "Block peak. 16 km is the platform the whole Praha build stands on — and you built it from 4 km runs in September. Look at her. 🍒 — Eda 🫒",
    },
]

# Week 1 — Reset (Mon 21 Sep – Sun 27 Sep)
# Thu yoga 08:45 already exists on the Trening calendar (Yoga1 : Øya
# treningssenter) — deliberately not duplicated here.
# Innflyttingsfest Fri 25 Sep 18:00 → Sat 26 is rest; long run moved to Sun 27.
CALENDAR_WEEK: list[dict] = [
    {
        "date": "2026-09-21",
        "title": "🏃 Easy run 5 km",
        "start": "2026-09-21T17:30:00",
        "end": "2026-09-21T18:10:00",
        "notes": "Reset week · easy 6:40–7:00/km · HR under 155 · slower than feels right, on purpose · — Eda 🫒",
    },
    {
        "date": "2026-09-22",
        "title": "🦵 Legs + glutes (strength)",
        "start": "2026-09-22T17:00:00",
        "end": "2026-09-22T18:00:00",
        "notes": "Rebuild session RPE 6–7 · hip thrust, RDL, split squat, glute bridge · log in Hevy on the watch 🍑",
    },
    {
        "date": "2026-09-23",
        "title": "🏃 Easy run 4 km",
        "start": "2026-09-23T17:30:00",
        "end": "2026-09-23T18:05:00",
        "notes": "Short and conversational · 6:40–7:00/km · you should be able to talk the whole way",
    },
    {
        "date": "2026-09-25",
        "title": "🦵 Glute focus (strength)",
        "start": "2026-09-25T16:00:00",
        "end": "2026-09-25T16:50:00",
        "notes": "Second legs hit · abduction, kickbacks, bridges · RPE 7 · done before the fest tonight 🪩",
    },
    {
        "date": "2026-09-27",
        "title": "🏃 Long run 7 km",
        "start": "2026-09-27T11:00:00",
        "end": "2026-09-27T11:50:00",
        "notes": "Moved off Saturday (fest Friday) · easy 6:40–7:00/km · no watch pressure · this is the first brick of Praha 💫",
    },
]
