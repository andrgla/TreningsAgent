#!/usr/bin/env bash
# Run a TreningsAgent scheduled job with venv, .env, and logging.
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO"

JOB="${1:-}"
if [[ -z "$JOB" ]]; then
  echo "Usage: $0 <job-name>" >&2
  echo "Jobs: weekly-observation, garmin-refresh, coach-weekly, coach-quarterly" >&2
  exit 1
fi

if [[ -f "$REPO/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$REPO/.env"
  set +a
fi

PYTHON="$REPO/.venv/bin/python"
if [[ ! -x "$PYTHON" ]]; then
  echo "Missing venv at $PYTHON — run: python3 -m venv .venv && pip install -r requirements.txt" >&2
  exit 1
fi

LOG_DIR="$REPO/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/${JOB}.log"

{
  echo "=== ${JOB} @ $(date '+%Y-%m-%d %H:%M:%S %Z') ==="
  # cap each job so a stalled Garmin call can't stack launchd runs
  run_capped() {
    local secs="$1"; shift
    if command -v gtimeout >/dev/null 2>&1; then
      exec gtimeout "$secs" "$@"
    else
      exec perl -e 'alarm shift @ARGV; exec @ARGV or die "exec failed: $!\n"' "$secs" "$@"
    fi
  }

  case "$JOB" in
    weekly-observation)
      run_capped 300 "$PYTHON" scripts/post_weekly_observation.py --refresh
      ;;
    garmin-refresh)
      # Keep the Garmin token warm so other jobs never hit the cold SSO chain.
      run_capped 150 "$PYTHON" scripts/garmin_login.py
      ;;
    coach-weekly)
      # Headless coach generates next week's Trening calendar sessions.
      run_capped 900 "$PYTHON" scripts/run_coach_agent.py weekly
      ;;
    coach-quarterly)
      # Self-gates: only generates the next block when the program is ending.
      run_capped 1200 "$PYTHON" scripts/run_coach_agent.py quarterly
      ;;
    *)
      echo "Unknown job: $JOB" >&2
      exit 1
      ;;
  esac
} >>"$LOG_FILE" 2>&1
