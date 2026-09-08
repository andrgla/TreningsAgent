#!/usr/bin/env bash
# PreToolUse/Bash guard: never start a second Garmin process.
#
# Enforces the one rule from .cursor/skills/fetching-garmin-data/SKILL.md.
# Concurrent Garmin logins get rate-limited (429) and every process falls into
# the 5-strategy SSO chain that sleeps 10-20s per attempt — the "hang". The
# flock in servers/garmin_auth.py only covers login itself, not a long pull, so
# this checks for a live Garmin process instead (a launchd job mid-run is the
# usual collision).
set -uo pipefail

cmd="$(jq -r '.tool_input.command // ""')"

# Only guard commands that actually reach Garmin.
case "$cmd" in
  *garmin_login.py*|*run_coach_agent.py*|*post_weekly_observation.py*|*run_scheduled_job.sh*|*garmin_mcp*|*garmin_trends*) ;;
  *) exit 0 ;;
esac

# The pattern lives in this file, not in the checking shell's argv, so pgrep
# cannot match the guard itself.
running="$(pgrep -fl '(garmin_login|run_coach_agent|post_weekly_observation|run_scheduled_job)' 2>/dev/null | head -3)"
[[ -z "$running" ]] && exit 0

jq -n --arg r "$running" '{
  hookSpecificOutput: {
    hookEventName: "PreToolUse",
    permissionDecision: "deny",
    permissionDecisionReason: (
      "A Garmin process is already running. Starting a second one is what causes the 429 login hang — see .cursor/skills/fetching-garmin-data/SKILL.md. Wait for it to finish, then retry ONCE. Do not loop.\n\nAlready running:\n" + $r
    )
  }
}'
