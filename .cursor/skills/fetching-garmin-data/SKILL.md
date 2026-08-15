---
name: fetching-garmin-data
description: >-
  Reliable way to read Garmin Connect data (activities, sleep, HRV, resting HR,
  VO2/race predictor, strength) without the recurring login "hang". Use whenever
  you need Garmin data for coaching, a progress report, or the weekly
  observation, or when a Garmin call stalls, times out, or returns a 429 / auth
  error.
---

# Fetching Garmin data

Garmin data drives every coaching decision, so it has to be *reliable*, not
"re-run until it works". Athlete goal, paces, guardrails, and the **Eda** persona
live in `AGENTS.md` — read it first; this skill is only about getting the data
out of Garmin cleanly.

## Why it used to hang (root cause)

This repo pins a forked `garminconnect` 0.3.6 whose login runs a 5-strategy SSO
chain (`.venv/.../garminconnect/client.py`). The portal strategies deliberately
`sleep(10-20s)` per TLS impersonation as an anti-Cloudflare tactic. When several
processes logged in at once (jobs + MCP server + ad-hoc shells), Garmin
rate-limited them (429) and every process fell into that sleep-heavy chain for
minutes — the "hang". Re-running eventually caught a clean cached-token load,
which *looked* like "brute force fixed it".

The fix already lives in the code — this skill is how you *use* it correctly.

## The one rule: one warm login, shared by everyone

- **All Garmin access goes through the shared client.** MCP tools already do; in
  scripts import `api` from `servers/garmin_mcp.py`, or `get_client()` from
  `servers/garmin_auth.py`. Never hand-roll a `Garmin()` + `login()` loop.
- **Never run two Garmin processes at once.** `garmin_auth` holds a
  cross-process lock (`data/.garmin.lock`) so concurrent logins can't stampede
  into 429s — but you should still avoid launching parallel Garmin shells (that
  was the main self-inflicted cause). One request at a time.
- **A keep-warm job refreshes the token every 6 h** so coaching-time calls never
  hit the cold SSO chain. It only touches `garmin_auth` (not the heavy MCP
  import stack), so it stays fast.

## Before a big pull: warm the session

If you're about to pull a lot (e.g. `fitness_trends`, the weekly observation),
warm/confirm auth first — instant when already warm:

```bash
cd "<repo>" && ./.venv/bin/python scripts/garmin_login.py
```

Prints a one-line health status (token valid + hours to expiry). Exit 0 =
authenticated. If it fails, see the error playbook below — do **not** loop it.

## Prefer batched tools over many calls

- Use the **`fitness_trends`** MCP tool (or `garmin_trends.collect_trends`) for
  HRV / resting HR / sleep / VO2 / race predictor / easy-run HR. It gathers the
  14-day window in parallel — one call instead of ~40 sequential ones.
- For a single day/metric use the specific tool (`hrv`, `sleep`, `daily_stats`,
  `recent_activities`, `recent_strength_sessions`, `vo2max`,
  `weekly_running_summary`).
- Don't fan out your own per-day loops over `hrv`/`sleep`/`daily_stats`; that
  re-creates the slow path `fitness_trends` already solved.

## Error playbook (do not brute-force)

| Symptom | Meaning | Action |
|---|---|---|
| `TimeoutError: Garmin login exceeded Ns` | Login stalled (rate limit or SSO). | Wait ~1 min, run `garmin_login.py` **once**. Don't loop. |
| `GarminConnectTooManyRequestsError` / 429 | IP rate limited. | Stop. Wait several minutes. Ensure only one Garmin process runs. |
| Auth / "Invalid Username or Password" | Bad creds or dead refresh token. | Check `.env` `GARMIN_EMAIL`/`GARMIN_PASSWORD`; run `garmin_login.py` once (no MFA → re-auths unattended). |
| Empty list (e.g. `vo2max` some days) | Metric simply not recorded that day. | Not a failure. Fall back to race predictor / another day. |
| Whole call freezes for minutes | Someone launched parallel Garmin work, or cold token. | Kill extras, warm once with `garmin_login.py`, retry. |

Tuning knobs (env, optional): `GARMIN_LOGIN_TIMEOUT` (default 90 s fail-fast),
`GARMIN_SKIP_STRATEGIES` (comma list, e.g. `portal+cffi,portal+requests` to drop
the slowest strategies).

## Guardrails

- Read-only: this skill never writes to the calendar or books classes.
- Treat credentials and health data as private; never print tokens/passwords.
