#!/usr/bin/env bash
# Install TreningsAgent launchd agents (macOS, user session).
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
RUNNER="$REPO/scripts/run_scheduled_job.sh"
AGENT_DIR="$HOME/Library/LaunchAgents"
UID_NUM="$(id -u)"
DOMAIN="gui/$UID_NUM"

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "Scheduled jobs use macOS launchd. On Linux, use cron with scripts/run_scheduled_job.sh." >&2
  exit 1
fi

chmod +x "$RUNNER"

if [[ ! -x "$REPO/.venv/bin/python" ]]; then
  echo "ERROR: .venv not found. Create it first:" >&2
  echo "  cd \"$REPO\" && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt" >&2
  exit 1
fi

if [[ ! -f "$REPO/.env" ]]; then
  echo "WARNING: .env missing — jobs need GARMIN_* and NOTION_TOKEN." >&2
fi

mkdir -p "$AGENT_DIR" "$REPO/logs"

write_plist() {
  local label="$1"
  local job="$2"
  local plist="$AGENT_DIR/${label}.plist"
  local intervals_xml="$3"

  cat >"$plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>${label}</string>
  <key>ProgramArguments</key>
  <array>
    <string>${RUNNER}</string>
    <string>${job}</string>
  </array>
  <key>WorkingDirectory</key>
  <string>${REPO}</string>
  <key>StandardOutPath</key>
  <string>${REPO}/logs/${job}.log</string>
  <key>StandardErrorPath</key>
  <string>${REPO}/logs/${job}.log</string>
  <key>StartCalendarInterval</key>
  ${intervals_xml}
  <key>RunAtLoad</key>
  <false/>
</dict>
</plist>
EOF
  echo "Wrote $plist"
}

# Mon 07:30, Wed 12:00, Sun 20:00 (local time — set Mac to Europe/Oslo)
WEEKLY_INTERVALS='  <array>
    <dict>
      <key>Weekday</key><integer>1</integer>
      <key>Hour</key><integer>7</integer>
      <key>Minute</key><integer>30</integer>
    </dict>
    <dict>
      <key>Weekday</key><integer>3</integer>
      <key>Hour</key><integer>12</integer>
      <key>Minute</key><integer>0</integer>
    </dict>
    <dict>
      <key>Weekday</key><integer>0</integer>
      <key>Hour</key><integer>20</integer>
      <key>Minute</key><integer>0</integer>
    </dict>
  </array>'

# Keep-warm: every 6 h (di_token lives ~22 h) at 00:15, 06:15, 12:15, 18:15
REFRESH_INTERVALS='  <array>
    <dict>
      <key>Hour</key><integer>0</integer>
      <key>Minute</key><integer>15</integer>
    </dict>
    <dict>
      <key>Hour</key><integer>6</integer>
      <key>Minute</key><integer>15</integer>
    </dict>
    <dict>
      <key>Hour</key><integer>12</integer>
      <key>Minute</key><integer>15</integer>
    </dict>
    <dict>
      <key>Hour</key><integer>18</integer>
      <key>Minute</key><integer>15</integer>
    </dict>
  </array>'

install_agent() {
  local label="$1"
  local job="$2"
  local intervals="$3"
  local plist="$AGENT_DIR/${label}.plist"

  # Reload if already loaded
  if launchctl print "$DOMAIN/$label" &>/dev/null; then
    launchctl bootout "$DOMAIN" "$plist" 2>/dev/null || true
  fi
  write_plist "$label" "$job" "$intervals"
  launchctl bootstrap "$DOMAIN" "$plist"
  launchctl enable "$DOMAIN/$label" 2>/dev/null || true
}

# Headless coach — generate next week's calendar sessions, Sun 18:00
COACH_WEEKLY_INTERVALS='  <array>
    <dict>
      <key>Weekday</key><integer>0</integer>
      <key>Hour</key><integer>18</integer>
      <key>Minute</key><integer>0</integer>
    </dict>
  </array>'

# Headless coach — quarterly generation. Self-gates on program end date, so run
# daily at 09:00 and it exits instantly unless the block is ending within ~8 d.
COACH_QUARTERLY_INTERVALS='  <array>
    <dict>
      <key>Hour</key><integer>9</integer>
      <key>Minute</key><integer>0</integer>
    </dict>
  </array>'

install_agent "com.treningsagent.garmin-refresh" "garmin-refresh" "$REFRESH_INTERVALS"
install_agent "com.treningsagent.weekly-observation" "weekly-observation" "$WEEKLY_INTERVALS"
install_agent "com.treningsagent.coach-weekly" "coach-weekly" "$COACH_WEEKLY_INTERVALS"
install_agent "com.treningsagent.coach-quarterly" "coach-quarterly" "$COACH_QUARTERLY_INTERVALS"

echo ""
echo "Installed scheduled jobs:"
echo "  garmin-refresh     — every 6 h (00:15, 06:15, 12:15, 18:15), keeps token warm"
echo "  weekly-observation — Mon 07:30, Wed 12:00, Sun 20:00 — Notion progress report"
echo "  coach-weekly       — Sun 18:00 — generates next week's Trening calendar sessions"
echo "  coach-quarterly    — daily 09:00 — self-gates; builds next block ~1 wk before it starts"
echo "  logs: $REPO/logs/<job>.log"
echo ""
echo "NOTE: coach-* jobs need cursor-sdk + CURSOR_API_KEY in .env (see .env.example)."
echo "      First calendar write may trigger a one-time macOS Calendar permission prompt."
echo ""
echo "Test now:  $RUNNER garmin-refresh | $RUNNER weekly-observation | $RUNNER coach-weekly"
echo "Uninstall: $REPO/scripts/uninstall_scheduled_jobs.sh"
