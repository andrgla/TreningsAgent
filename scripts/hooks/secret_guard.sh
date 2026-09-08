#!/usr/bin/env bash
# PreToolUse/Bash guard: never dump credentials into the transcript.
#
# Every skill in .cursor/skills/ ends with "never print tokens/passwords".
# This makes that enforced rather than requested: it denies readers pointed at
# .env or the cached Garmin/SiO tokens. Scripts that *source* .env or read it
# from Python are untouched — only commands that would print it are blocked.
set -uo pipefail

cmd="$(jq -r '.tool_input.command // ""')"

# .env (but not .env.example / .envrc), plus the cached token stores.
# ".venv/bin/python" contains no ".env" substring, so it never matches.
secret_re='(\.env([^.A-Za-z0-9]|$))|garmin_tokens\.json|sio_auth\.json'
reader_re='(^|[|;&(`[:space:]])(cat|head|tail|less|more|bat|strings|nl|od|xxd|grep|egrep|rg|awk|sed|cut)([[:space:]]|$)'

printf '%s' "$cmd" | grep -Eq "$secret_re" || exit 0
printf '%s' "$cmd" | grep -Eq "$reader_re" || exit 0

jq -n '{
  hookSpecificOutput: {
    hookEventName: "PreToolUse",
    permissionDecision: "deny",
    permissionDecisionReason: (
      "Blocked: this would print credentials (.env, garmin_tokens.json or sio_auth.json) into the transcript. Read the value from inside a script instead, or ask the user directly. The key names are documented in .env.example."
    )
  }
}'
