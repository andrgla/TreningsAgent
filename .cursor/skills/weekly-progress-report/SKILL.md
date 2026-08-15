---
name: weekly-progress-report
description: >-
  Produce a concise, tables-first progress report on how training is going,
  judged at the WEEK level (day-flexible): a session counts if it was done any
  day that week, even if moved from its planned day. Use when the user asks "how
  am I doing", "how's it going", "am I on track", "weekly check-in / report /
  recap", "how was my week", or "progress".
---

# Weekly progress report

A quick, read-only check-in on how the current (or a given) week is going.
Athlete goal, target paces, guardrails, and the **Eda** coach persona live in
`AGENTS.md` — read it first; don't duplicate its specifics here. This is lighter
than the `training-coach-loop` monthly review (which writes to Notion) — this one
is on-demand. By default report to **chat**; when the user wants it saved, append
to **My recent observations** on the Workout Coach Notion page (below the
Trondheim program, above Q3 Training Weeks) via `scripts/post_weekly_observation.py`
or the same block structure inline.

**Scheduled (macOS):** `scripts/install_scheduled_jobs.sh` installs a launchd
agent that refreshes the Notion observation **Mon 07:30, Wed 12:00, Sun 20:00**
(local time). Logs: `logs/weekly-observation.log`. Test:
`scripts/run_scheduled_job.sh weekly-observation`.

Report as **Eda** (see `AGENTS.md`): warm, direct, never pitying. The tables stay
clean and factual; Eda's voice lives in the one-line verdict, an optional "Next
up", and the sign-off **— Eda 🫒**. A missed session gets reframed forward, not
scolded.

## Core principle: judge the week, not the day

Adherence is measured over the whole week, **not** per planned day.

- A session done on a **different day** than planned still counts as **done**
  (e.g. legs done today instead of yesterday; yoga moved to a more convenient
  day but still done that week → ✅).
- Only call something a **miss** if it was not done at all that week, or the
  week's volume/target fell short.
- Sessions not done yet but with days left in the week are **on track**, not
  misses.
- Week window: **Mon–Sun, Europe/Oslo.** Default to the current week to date;
  count anything already logged plus what's still planned for the remaining days.

## Data sources (read only)

**Always pull Garmin actuals before reporting.** Never invent or assume session counts.
If Garmin login fails, say so and stop — do not post placeholder numbers. For
reliable Garmin reads (and if a call hangs / 429s), follow the
**fetching-garmin-data** skill (`.cursor/skills/fetching-garmin-data/`): warm one
shared login, never run parallel Garmin processes, prefer batched `fitness_trends`.

- **notion** — `get_current_training_week`: the week's targets (run km, runs,
  quality/long, strength ×, mobility ×).
- **garmin** — `weekly_running_summary`, `recent_activities` (runs/km done);
  `recent_strength_sessions` (legs cadence); **`fitness_trends`** (14 d: HRV,
  resting HR, sleep, race predictor, easy-run HR vs pace, readiness). Interpret
  trends — don't just list sessions.
- **calendar** — `get_events` for the week: what was planned/booked and on which
  day, so you can show moved-day sessions. **sio-gym** `my_bookings` for any
  booked class this week.

## Steps

```
- [ ] 1. Targets — Notion current week
- [ ] 2. Actuals — Garmin sessions (week-level adherence)
- [ ] 3. Trends — `fitness_trends` (HRV, RHR, sleep, race predictor, easy HR)
- [ ] 4. Match at week level; mark done / on track / missed
- [ ] 5. Report tables below (concise, insight-led)
```

Match logic per category: target met any day this week → ✅ **Done**; not done
yet but days remain → 🟡 **On track**; behind with little room left → ⚠️ **At
risk**; week over or unachievable → ❌ **Missed**. When a session was done on a
different day than planned, keep it ✅ and add "moved from <day>" in the note.

## Report format (tables, not wordy)

Lead with a one-line verdict in Eda's voice (e.g. "You're ahead of yourself this
week, bestie — one leg day left and we're golden ✨"). Then these tables. Keep
prose to that verdict line plus, at most, a short "Next up" line and the
**— Eda 🫒** sign-off.

### Week at a glance

| Category | Target | Done so far | Status |
|---|---|---|---|
| Running km | 30 | 22 | 🟡 8 km left (today's 8 km) |
| Runs | 4 | 3 | 🟡 1 left |
| Quality / long | 1 | 1 | ✅ |
| Legs | 2 | 1 | 🟡 1 left (today) |
| Yoga / mobility | 1 | 1 | ✅ moved to Wed |

### Sessions this week

| Day | Planned | Actual | Note |
|---|---|---|---|
| Mon | Legs | — | moved to Tue |
| Tue | Easy 6 km | Easy 6.1 km + Legs | legs pulled from Mon |
| Wed | Yoga | Yoga | booked SiO |
| Thu | Threshold | Threshold 5:08/km | ✅ |
| Fri | Rest | Rest | |
| Sat | Long 12 km | — | planned |
| Sun | Easy 8 km + Legs | — | planned (today) |

Only include the "Sessions this week" table if it adds clarity (moved days,
swaps). For a clean week, the glance table alone is enough.

### Fitness signals (14 d)

Insight over inventory — interpret what the trends mean for HM training.

| Signal | Latest | Trend | ↕ | Read |
|---|---|---|---|---|
| HRV (overnight) | 59 ms | ~56 vs 50 ms | ↑ | Recovering well |
| Resting HR | 55 bpm | ~58 vs 56 bpm | ↓ | Fatigue easing |
| Sleep | 5.3 h | ~6.9 h avg | ↓ | Under 8 h target |
| Race predictor (HM) | 2:01:41 | ~5:46/km | → | Gap to 5:25 normal in base |
| Easy-run stress | HR 159 | 6:04/km | ↑ | Easy days too hot |

**Going well / Focus more** bullets should come from **trends** (HRV, sleep, RHR,
race predictor, easy HR vs pace) — not a recap of every logged session. Max 3–4
bullets each.

## Guardrails

- Read-only skill: **never** create/modify calendar events or book/cancel
  classes here. If the user wants to fix a gap, hand off to `training-coach-loop`
  and confirm before any write.
- Treat health data as private; never print tokens/passwords.
