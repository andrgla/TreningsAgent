#!/usr/bin/env python3
"""Keep the Garmin session warm (and check its health).

Run on a schedule (see scripts/install_scheduled_jobs.sh) so the di_token never
goes cold; then the weekly-observation job and interactive coaching always hit a
warm token instead of the slow SSO login chain.

Imports only ``garmin_auth`` (not ``garmin_mcp``), so it stays lean and fast and
never pulls the heavy MCP/anyio import stack.

Exit code 0 = authenticated, 1 = failure.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "servers"))

from garmin_auth import refresh  # noqa: E402


def main() -> int:
    try:
        status = refresh(verbose=True)
    except Exception as e:  # noqa: BLE001
        print(f"Garmin auth FAILED — {e}", file=sys.stderr)
        return 1
    return 0 if status.get("di_token_valid") else 1


if __name__ == "__main__":
    raise SystemExit(main())
