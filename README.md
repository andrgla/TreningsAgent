# TreningsAgent

A personal training assistant that runs on Cursor (or any MCP client) with live
access to:

- **Notion** (read) — Q3 training program on [Workout Coach](https://www.notion.so/Workout-Coach-39427249eb4d806a8686d0ebc552d487)
- **Garmin Connect** (read) — running, **strength sessions**, sleep, HRV, readiness
- **Apple Calendar** (read/write Trening only) — schedule sessions around availability
- **SiO Athletica** gym booking (read + optional booking)

Goal it's set up for: **Trondheim Halvmaraton at 5:25/km pace** (see `AGENTS.md`).

### Example week on Apple Calendar

Training sessions land on the **Trening** calendar around life (study, social, travel):

![Example Trening calendar week](images/example-calendar.png)

## Layout

```
.cursor/mcp.json        MCP server config for Cursor
.mcp.json               MCP server config for Claude Code / the headless coach
CLAUDE.md               Points Claude Code at AGENTS.md
servers/
  ibooking_client.py    SiO/iBooking HTTP client (reverse-engineered)
  sio_gym_mcp.py        MCP server: list/book/cancel SiO classes
  garmin_mcp.py         MCP server: read-only Garmin Connect
  notion_mcp.py         MCP server: Q3 program on Notion Workout Coach page
  notion_client.py      Notion REST helpers
  calendar_mcp.py       MCP server: read all calendars, write Trening only
  calendar_backend.py   Picks the calendar backend (EventKit vs CalDAV)
  apple_bridge.py       macOS EventKit backend (local)
  caldav_backend.py     iCloud CalDAV backend (cloud)
  requirements.txt
data/
  q3_training_program.py  Jul–Aug 2026 half-marathon build (source of truth for bootstrap)
scripts/
  bootstrap_notion.py     Create/populate Notion database (one-time)
  push_calendar_plan.py   Push next 7 days to Trening calendar
  run_coach_agent.py      Headless coach (Claude Agent SDK)
  caldav_doctor.py        Verify the iCloud CalDAV setup
  sync_github_secrets.sh  Upload local credentials to GitHub secrets
.github/workflows/      Scheduled cloud jobs (GitHub Actions)
AGENTS.md               Coaching brief + guardrails (read by the agent)
.env.example            Copy to .env and fill in credentials
```

## Apple Calendar setup (do this first)

The calendar server is **calendar_mcp.py** — native EventKit via apple-bridge.
**Reads all calendars; writes only to Trening** (enforced in the server, not just
in prompts).

1. **Install** (once):

   ```bash
   npm install
   ```

2. **Reload MCP in Cursor**: Settings → Tools & MCP → confirm `calendar` is
   listed. Reload the window if it was already open.

3. **Grant permission to Cursor** (not Terminal):
   - In Cursor chat, ask: *"List my calendars using the calendar MCP."*
   - macOS should prompt: allow **Cursor** to access Calendars → choose
     **Full Access**.
   - If no prompt: **System Settings → Privacy & Security → Calendars** →
     enable **Cursor**.

4. **Optional — dedicated training calendar**: in the Calendar app, create a
   calendar named **Trening** (any colour). The agent will prefer it for new
   workouts.

5. **If access was denied earlier**:

   ```bash
   tccutil reset Calendar com.todesktop.230313mzl4w4u92
   ```

   Then repeat step 3 from Cursor chat (not from Terminal).

**Troubleshooting:** Running `npm run calendar:doctor` in Terminal only grants
access to Terminal, not Cursor. Always trigger the permission from inside
Cursor.

## Other setup

1. **Python deps** (Garmin + SiO):

   ```bash
   python3 -m venv .venv
   ./.venv/bin/python -m pip install -r servers/requirements.txt
   ```

2. **Add credentials**: copy `.env.example` → `.env` (Garmin + SiO + Notion).
   Set `NOTION_WORKOUT_COACH_PAGE_ID` to *your* Workout Coach page id. Calendar
   needs no secrets; writes only go to `TRAINING_CALENDAR_NAME` (default
   **Trening**).

3. **Notion program** (one-time):

   ```bash
   # Create integration at notion.so/my-integrations, share Workout Coach page
   ./.venv/bin/python scripts/bootstrap_notion.py
   ```

   This creates **Q3 Training Weeks** under Workout Coach with 8 weekly rows
   (Jul 7 – Aug 31). Optional: push the first 7 days to Apple Calendar:

   ```bash
   ./.venv/bin/python scripts/push_calendar_plan.py          # preview
   ./.venv/bin/python scripts/push_calendar_plan.py --confirm  # create on Trening
   ```

4. **Reload MCP**: confirm `calendar`, `garmin`, `notion`, and `sio-gym` show green.

5. **Enable gym booking (optional)**: set `SIO_ALLOW_BOOKING=true` in `.env`.

**Lifting:** Log workouts in Hevy on your watch. Garmin records them as strength
activities — the coach uses `recent_strength_sessions` (no Hevy Pro needed).

## Running in the cloud

By default the scheduled jobs run on this Mac via `launchd`, which means they
only fire while the Mac is awake and online. The same four jobs also exist as
GitHub Actions workflows in `.github/workflows/`, so the coach keeps planning
whether or not the laptop is open.

| Job | Schedule (Oslo) | What it does | Needs |
| --- | --- | --- | --- |
| `garmin-refresh` | every 6 h | keeps the Garmin token warm | Garmin |
| `weekly-observation` | Mon 07:30, Wed 12:00, Sun 20:00 | posts a progress note to Notion | Garmin, Notion |
| `coach-weekly` | Sun 18:00 | plans next week onto the Trening calendar | all + Anthropic |
| `coach-quarterly` | daily 09:00 (self-gating) | builds the next block in Notion | all + Anthropic |

**Cron is UTC**, and GitHub has no timezone setting, so these run an hour later
in summer (CEST) than the labels above. That doesn't matter for any of them.

### One-time setup

1. **Move the Trening calendar to iCloud.** The cloud runner is Linux, so it
   cannot use macOS EventKit — it writes over iCloud CalDAV instead, to the
   *same* calendar, so events still sync down to Calendar.app and your iPhone.
   A calendar stored under **On My Mac** is invisible to CalDAV. In Calendar.app,
   check that **Trening** sits under the iCloud account; if not, create it there
   (File → New Calendar → iCloud) and move the events across.

2. **Create an app-specific password** at
   [appleid.apple.com](https://appleid.apple.com) → Sign-In and Security →
   App-Specific Passwords. Your normal Apple ID password will *not* work. Add it
   to `.env`:

   ```
   ICLOUD_USERNAME=your@icloud.com
   ICLOUD_APP_PASSWORD=xxxx-xxxx-xxxx-xxxx
   ```

3. **Verify the calendar path before trusting it to a schedule:**

   ```bash
   ./.venv/bin/python scripts/caldav_doctor.py --write
   ```

   This lists your iCloud calendars, confirms **Trening** is among them, reads
   the current week, and creates + deletes a probe event.

4. **Add an Anthropic API key** to `.env` (`ANTHROPIC_API_KEY`, from
   [console.anthropic.com](https://console.anthropic.com)). The two coach jobs
   run a Claude Code agent headlessly; the other two need no key.

5. **Upload the credentials to GitHub:**

   ```bash
   ./scripts/sync_github_secrets.sh
   ```

   This pushes `.env` plus three gitignored files the runner needs — `ATHLETE.md`,
   `data/notion_state.json`, and your cached Garmin token — into repository
   secrets. Values go straight from disk to the GitHub API; nothing is printed.

6. **Run each workflow once by hand** from the repo's Actions tab
   (*Run workflow*) before relying on the schedule. Start with `garmin-refresh`,
   then `weekly-observation`, then `coach-weekly`.

7. **Stop the local jobs** so nothing runs twice:

   ```bash
   ./scripts/uninstall_scheduled_jobs.sh
   ```

### Why the Garmin token is seeded from a secret

A cold Garmin SSO login from a datacentre IP is what triggers rate limiting and
Cloudflare challenges. The workflows avoid ever doing one: your working local
token is uploaded as `GARMIN_TOKENS_B64`, restored on the first run, and then
kept alive by `garmin-refresh` in a rolling Actions cache. Re-run
`sync_github_secrets.sh` after any local Garmin re-login to refresh the seed.

If Garmin does force a re-login, run `./.venv/bin/python scripts/garmin_login.py`
on the Mac and sync the secrets again.

### Caveats

- **GitHub disables scheduled workflows after 60 days of repository inactivity.**
  The `coach-weekly` job commits its generated plan back to the repo, which
  counts as activity, so this only bites if the coach jobs are removed.
- **A single occurrence of a recurring event can't be deleted over CalDAV** — the
  protocol deletes the whole event resource. The coach only ever deletes the
  non-recurring sessions it created, so this doesn't come up in practice.
- Interactive use on the Mac is unchanged: EventKit is still used there
  automatically. Set `CALENDAR_BACKEND=caldav` to force the cloud path locally.

## Try it

In Cursor chat:

- "What's my current training week in Notion, and what should I do today?"
- "When did I last do strength according to Garmin — am I due for legs?"
- "What does my calendar look like this week? Any free evenings for a run?"
- "List spinning classes at SiO Vulkan this week."
- "Check my Garmin readiness and last week's running volume."
- "Given my calendar and recovery, plan my runs for the next 3 days toward
  5:25/km, and suggest a SiO class I could book."

## Notes / caveats

- **SiO reads** use a public token from the booking web app — no login needed.
  **Booking** requires your mobile login and yields a token cached at
  `~/.treningsagent/sio_auth.json` (chmod 600).
- **Garmin** auth changes often. If login breaks, run
  `./.venv/bin/pip install -U garminconnect`, or switch to a browser-based
  Garmin MCP server.
- Nothing here writes to Garmin. Calendar and gym writes always require your
  confirmation (see `AGENTS.md`).
