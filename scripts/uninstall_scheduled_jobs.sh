#!/usr/bin/env bash
# Remove TreningsAgent launchd agents.
set -euo pipefail

AGENT_DIR="$HOME/Library/LaunchAgents"
UID_NUM="$(id -u)"
DOMAIN="gui/$UID_NUM"

for label in \
  com.treningsagent.weekly-observation \
  com.treningsagent.garmin-refresh \
  com.treningsagent.coach-weekly \
  com.treningsagent.coach-quarterly; do
  plist="$AGENT_DIR/${label}.plist"
  if [[ -f "$plist" ]]; then
    launchctl bootout "$DOMAIN" "$plist" 2>/dev/null || true
    rm -f "$plist"
    echo "Removed $label"
  fi
done

echo "Done."
