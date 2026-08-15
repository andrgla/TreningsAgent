---
name: training-coach-loop
description: >-
  Runs the recurring coaching loop for the half-marathon athlete: generate a
  quarterly training program in Notion, run a monthly review that writes a tiny
  plan-vs-actual report to Notion and adjusts the plan, and generate a week of
  sessions on the Trening calendar from Garmin readiness/load and calendar
  availability. Use when the user asks to plan the week or quarter, run the
  monthly review/report, generate or adjust a training plan, start a new
  training block, or "load my status".
---

# Training coach loop

Repeatable procedures for coaching toward the goal race. Athlete goal, target
paces, full guardrails, and the **Eda** coach persona live in `AGENTS.md` —
read it first and do not duplicate its specifics here. Personal recovery
constraints (hangover severity, cycle notes) live in `ATHLETE.md` when present;
if missing, use the generic Health rules in `AGENTS.md`. Write all
athlete-facing copy (Notion overview, monthly review, calendar notes) in Eda's
voice and sign off **— Eda 🫒**; keep paces/dates/reps exact.

## Data sources

- **notion** MCP: `get_current_training_week`, `list_training_weeks`,
  `get_program_overview` — the quarter program.
- **garmin** MCP (read): `training_readiness`, `sleep`, `hrv`, `daily_stats`,
  `recent_activities`, `weekly_running_summary`, `training_status`, `vo2max`,
  `recent_strength_sessions`, `weekly_strength_summary`, `fitness_trends`. For
  reliable reads (avoiding the login "hang"), follow the **fetching-garmin-data**
  skill (`.cursor/skills/fetching-garmin-data/`).
- **calendar** MCP: `get_events` / `get_today_events` for availability.
- **sio-gym** MCP: `list_classes` for yoga/pilates or spin.
- Program source of truth: `data/q3_training_program.py` (`PROGRAM_OVERVIEW`,
  `WEEKS`, `CALENDAR_WEEK`, `DB_TITLE`).
- Scripts: `scripts/bootstrap_notion.py`, `scripts/prettify_notion.py`,
  `scripts/push_calendar_plan.py`.

**Calendar writes run from the user's Terminal.** macOS grants Calendar access
per process; this agent's shell is denied. Prepare the change, then give the
user the exact command to run.

**Automated (headless) runs.** The `coach-weekly` and `coach-quarterly` launchd
jobs run this loop unattended via `scripts/run_coach_agent.py` (Cursor SDK). That
scheduled runner is pre-authorised (see the automation carve-out in `AGENTS.md`)
to write the Trening calendar / Notion without asking. Needs `cursor-sdk` +
`CURSOR_API_KEY`. Interactive sessions still confirm before any write.

## Weekly generation (primary loop)

Copy and track:

```
- [ ] 1. Notion: current week structure
- [ ] 2. Garmin: recovery + load + strength
- [ ] 3. Calendar: availability + drinking days
- [ ] 4. Build the week to paces
- [ ] 5. Push to Trening (user confirms)
```

1. **Notion** — `get_current_training_week` for phase, weekly running/strength/
   mobility targets, and key sessions.
2. **Garmin** — `training_readiness`, `sleep`, `hrv`, `daily_stats` (recovery);
   `recent_activities`, `weekly_running_summary`, `training_status` (load);
   `recent_strength_sessions` (legs 2x/week; note days since last). Respect the
   ~10%/week volume cap. Read `ATHLETE.md` if present for cycle/recovery notes;
   otherwise use generic Health rules in `AGENTS.md`. If readiness and how she
   feels are both low, do not place a quality session.
3. **Calendar** — `get_events` for the target week; place sessions in free slots,
   avoid conflicts (timezone Europe/Oslo). **Infer drinking/party days from the
   events** (see below) rather than asking. Honour `ATHLETE.md` hangover
   severity when present. The **morning after** any drinking day:
   - No early session — schedule late afternoon/evening, or rest.
   - No hard/quality or long session — keep it easy or a rest/mobility day.
   - Move the quality/long session to a non-affected day.

   Only ask (`AskQuestion`) if a social event is genuinely ambiguous.
4. **Build** — one quality session per 2-3 easy; long run; legs 2x + glute
   focus; one yoga/pilates. Honour the drinking-day rule above. Use goal paces
   from `AGENTS.md`. Edit `CALENDAR_WEEK` in `data/q3_training_program.py` to the
   target week's dates and sessions (naive local ISO like
   `2026-07-14T17:00:00`; the script attaches the Oslo offset). Keep titles
   stable so dedup works.
5. **Push** — after the user confirms, they run:

   ```bash
   cd "<repo>" && ./.venv/bin/python scripts/push_calendar_plan.py --confirm
   ```

   Dedup-safe (skips existing, removes duplicates of plan sessions). Use
   `--confirm --reset` to wipe and rebuild the week. If a class is booked,
   remind: cancel >=3h ahead to avoid a no-show ban.

### Detecting drinking/party days from the calendar

Scan the week's event titles/notes (any calendar, not just Trening) for signals
of a night involving alcohol. Treat the event's day as a drinking day and
protect the next morning.

- **Explicit tag (preferred):** a wine-glass/beer/party emoji (🍷🍺🥂🎉) or a
  bracketed marker like `[drikke]` / `[fest]` in the title. Encourage her to add
  one of these when a plan involves drinking — it removes all guesswork.
- **Norwegian keywords:** fest, vors, vorspiel, nachspiel, nach, fyll, fylla,
  utepils, pils, øl, vin, bar, pub, byen, "på byen", bytur, release, bursdag,
  julebord, sommerfest, kalas, date.
- **English keywords:** party, drinks, bar, pub, club, night out, birthday,
  wedding, happy hour, wine, beer.
- Late-evening start (roughly 20:00+) on a social event raises confidence.

If a match is clearly not drinking (e.g. "barnebursdag" / kids' party, a work
meeting), do not treat it as a drinking day.

## Quarterly generation

Use at the start of a new training block.

1. **Baseline** — `vo2max`, `weekly_running_summary`, `training_status`, recent
   `recent_activities`. Confirm goal race, date, and target pace with the user.
   Anchor the block to the goals ladder (see `AGENTS.md` → Eda's north star):
   the "who is she" vision → annual → quarterly goals. Read those from Notion if
   shared, and frame the quarter as a step toward becoming her.
2. **Design phases** — base -> build -> peak -> taper, ~10%/week progression,
   taper in the final ~10 days. Map week-by-week running/strength/mobility.
3. **Write the program** — edit `data/q3_training_program.py`:
   - `PROGRAM_OVERVIEW` (use `**bold**` / backticks; the parser converts them)
   - `WEEKS` (one dict per week: title, start, end, phase, run_km, running,
     strength, mobility, quality, notes)
   - For a brand-new quarter, set a new `DB_TITLE` (e.g. `Q4 Training Weeks`) so
     a fresh database is created rather than reusing the current one.
4. **Publish** — user runs:

   ```bash
   cd "<repo>" && ./.venv/bin/python scripts/bootstrap_notion.py \
     && ./.venv/bin/python scripts/prettify_notion.py
   ```

   `bootstrap` skips populate if the target database already has rows; a new
   quarter needs the new `DB_TITLE`.

## Monthly review and adjustment

Run at the end of each month (or start of the next). Produces a tiny
plan-vs-actual report in Notion, then adjusts the coming weeks.

Copy and track:

```
- [ ] 1. Gather the month's actuals (Garmin)
- [ ] 2. Compare to the planned month (Notion)
- [ ] 3. Write the report to Notion
- [ ] 4. Adjust WEEKS + re-publish
- [ ] 5. Regenerate affected calendar weeks
```

1. **Actuals** — for the month just ended:
   - `weekly_running_summary` across the month + `recent_activities`: count
     runs, sum km, note quality/long sessions actually done.
   - `recent_strength_sessions` / `weekly_strength_summary`: sessions vs the
     legs-2x/week target.
   - Count yoga/pilates activities for the mobility target.
   - `vo2max` and `training_status` for the fitness trend.
2. **Compare** — pull the month's weeks via `list_training_weeks`; sum planned
   `run_km` and list planned quality/long/strength/mobility. Note hits vs misses.
3. **Report** — append this to the Workout Coach page. Build the blocks with
   `md_rich_text` (bold/code) and append via
   `notion_request("PATCH", f"/blocks/{page_id}/children", {"children": [...]})`.
   The Notion API is reachable from this agent's shell (no Terminal needed).
   Under a `heading_2` `Monthly reviews` (create once if absent), add a
   `heading_3` for the month and a short paragraph/bullets:

   ```
   ## 🌺 <Month Year> review
   **Adherence:** <runs>/<planned> runs · <km>/<planned> km · strength <n>/<target> · mobility <n>/1
   **Wins:** <1-2 things that went to plan> ✨
   **Growth edges:** <what slipped — reframed forward, never scolding>
   **Fitness:** <VO2max / pace / training-status trend> 📈
   **Next month:** <the adjustment being made> — Eda 🫒
   ```

   Keep it to ~5 lines, in Eda's voice: warm, direct, believing, never pitying.
4. **Adjust** — edit the affected entries in `WEEKS` (and `PROGRAM_OVERVIEW` if
   phases/dates change) in `data/q3_training_program.py`; re-run
   `bootstrap_notion.py` + `prettify_notion.py`.
5. **Regenerate** — rebuild the affected upcoming weeks on the calendar via the
   weekly loop above.

## Quarterly adjustment

For a mid-quarter change bigger than a monthly tweak (race moves, injury,
new goal): edit `WEEKS`/`PROGRAM_OVERVIEW`, re-run bootstrap + prettify, then
regenerate the affected calendar weeks.

## Notion formatting

The Notion API stores rich-text, not markdown. Use `md_rich_text` in
`servers/notion_client.py` (handles `**bold**` and `` `code` ``) when writing
page text, and `scripts/prettify_notion.py` to fix any block already showing
literal `**` and to set the page icon.

## Guardrails

Mirror `AGENTS.md`:

- Never create/modify/delete a calendar event or book/cancel a class without
  explicit confirmation.
- Calendar writes target **Trening** only (server-enforced).
- SiO booking is disabled unless `SIO_ALLOW_BOOKING=true`; if off, say so rather
  than failing silently.
- Remind to cancel a class >=3h before start to avoid a no-show ban.
- Treat credentials and health data as private; never print tokens/passwords.
