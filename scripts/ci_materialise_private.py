#!/usr/bin/env python3
"""Recreate the gitignored private files a scheduled cloud run needs.

The repo is public, so three files it depends on are deliberately untracked:

  ATHLETE.md                        personal health adaptations
  data/notion_state.json            Notion page + database ids
  data/.garminconnect/…             cached Garmin OAuth tokens

Each arrives as a repository secret and is written to disk here. Everything is
optional: a missing secret is reported and skipped, so a partial setup still
runs the jobs it can.

The Garmin token seed matters more than it looks. A cold SSO login from a cloud
IP is what trips Garmin's rate limiting and Cloudflare challenges — seeding a
token minted on a trusted machine means CI only ever *refreshes* a live session
rather than logging in with a password.

Reads (all base64 except NOTION_STATE_JSON, which is plain JSON):
  ATHLETE_MD_B64, NOTION_STATE_JSON, GARMIN_TOKENS_B64

Never prints a secret's contents — only its name, size, and destination.
"""

from __future__ import annotations

import base64
import binascii
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _write(path: Path, data: bytes, *, mode: int | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    if mode is not None:
        path.chmod(mode)
    print(f"  wrote {path.relative_to(ROOT)} ({len(data)} bytes)")


def _from_b64(var: str, dest: Path, *, mode: int | None = None) -> bool:
    raw = (os.environ.get(var) or "").strip()
    if not raw:
        print(f"  {var} not set — skipping {dest.relative_to(ROOT)}")
        return False
    try:
        decoded = base64.b64decode(raw, validate=True)
    except (binascii.Error, ValueError):
        print(f"  ERROR: {var} is not valid base64", file=sys.stderr)
        return False
    _write(dest, decoded, mode=mode)
    return True


def main() -> int:
    print("Materialising private files:")

    _from_b64("ATHLETE_MD_B64", ROOT / "ATHLETE.md")

    state = (os.environ.get("NOTION_STATE_JSON") or "").strip()
    if state:
        try:
            json.loads(state)
        except json.JSONDecodeError as e:
            print(f"  ERROR: NOTION_STATE_JSON is not valid JSON ({e})", file=sys.stderr)
            return 1
        _write(ROOT / "data" / "notion_state.json", state.encode("utf-8"))
    else:
        print("  NOTION_STATE_JSON not set — skipping data/notion_state.json")

    # Only seed the token store when the cache restored nothing; an existing
    # cached token is newer than a secret that was captured once by hand.
    tokens = ROOT / "data" / ".garminconnect" / "garmin_tokens.json"
    if tokens.exists():
        print("  Garmin token store restored from cache — not reseeding")
    else:
        _from_b64("GARMIN_TOKENS_B64", tokens, mode=0o600)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
