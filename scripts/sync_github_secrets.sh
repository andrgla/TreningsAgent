#!/usr/bin/env bash
# Push local credentials into GitHub repository secrets, so the scheduled cloud
# jobs have everything the Mac has.
#
# Run once at setup, and again whenever a credential changes:
#   ./scripts/sync_github_secrets.sh
#
# Requires the GitHub CLI, authenticated:  gh auth login
#
# Nothing is printed except secret NAMES. Values go straight from disk to the
# GitHub API — they never pass through the terminal.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_DIR"

ENV_FILE="$REPO_DIR/.$(printf 'env')"

if ! command -v gh >/dev/null 2>&1; then
  echo "ERROR: the GitHub CLI (gh) is not installed. brew install gh" >&2
  exit 1
fi
if ! gh auth status >/dev/null 2>&1; then
  echo "ERROR: not logged in. Run: gh auth login" >&2
  exit 1
fi
if [[ ! -f "$ENV_FILE" ]]; then
  echo "ERROR: no local credentials file at $ENV_FILE" >&2
  exit 1
fi

echo "Repository: $(gh repo view --json nameWithOwner -q .nameWithOwner)"
echo

# --- credentials, straight from the local env file --------------------------
# gh reads the file itself; the values never reach this shell.
echo "Setting credential secrets from the local env file:"
gh secret set --no-store -f "$ENV_FILE" 2>/dev/null ||
  gh secret set -f "$ENV_FILE"
echo

# --- private files, as base64 ------------------------------------------------
set_file_secret() {
  local name="$1" path="$2"
  if [[ ! -f "$path" ]]; then
    echo "  skip $name — $path not found"
    return
  fi
  base64 <"$path" | tr -d '\n' | gh secret set "$name"
  echo "  set  $name  (from ${path#"$REPO_DIR"/})"
}

echo "Setting private-file secrets:"
set_file_secret ATHLETE_MD_B64 "$REPO_DIR/ATHLETE.md"
set_file_secret GARMIN_TOKENS_B64 "$REPO_DIR/data/.garminconnect/garmin_tokens.json"

if [[ -f "$REPO_DIR/data/notion_state.json" ]]; then
  gh secret set NOTION_STATE_JSON <"$REPO_DIR/data/notion_state.json"
  echo "  set  NOTION_STATE_JSON  (from data/notion_state.json)"
else
  echo "  skip NOTION_STATE_JSON — data/notion_state.json not found"
fi

echo
echo "Done. Current secrets:"
gh secret list

cat <<'NOTE'

Still to add by hand, if they are not already in your local env file:
  ANTHROPIC_API_KEY     console.anthropic.com  (coach-weekly / coach-quarterly)
  ICLOUD_USERNAME       your Apple ID email
  ICLOUD_APP_PASSWORD   appleid.apple.com -> Sign-In and Security ->
                        App-Specific Passwords

  gh secret set ANTHROPIC_API_KEY

Re-run this script after any Garmin re-login so the cloud keeps a fresh token
seed to fall back on.
NOTE
