"""Shared, warm Garmin login for every process in this repo.

The recurring "Garmin hang" came from each script/process building its own
``Garmin`` client and calling ``login()`` independently. When several logins
raced (jobs + MCP server + ad-hoc shells) Garmin rate-limited them (429) and the
underlying ``garminconnect`` fork fell into its anti-Cloudflare login strategies,
which deliberately ``sleep(10-20s)`` per TLS impersonation — minutes of apparent
hang. Re-running eventually caught a clean token load ("brute force works").

This module makes login happen once and stay warm:

- **Single-flight cross-process lock** (``data/.garmin.lock``) so concurrent
  processes serialise login instead of stampeding into 429s.
- **In-process client reuse** so a process logs in at most once.
- **Fail-fast watchdog**: login runs in a worker thread with a hard timeout, so
  a stall raises a clear error instead of freezing for minutes. Works off the
  main thread, so it is safe inside the MCP server too.
- **Token status helper** + ``refresh()`` for the keep-warm scheduled job.

All callers should go through :func:`get_client`.
"""

from __future__ import annotations

import base64
import json
import os
import threading
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

_TOKENSTORE = os.environ.get(
    "GARMINTOKENS",
    str(ROOT / "data" / ".garminconnect"),
)
_LOCK_PATH = ROOT / "data" / ".garmin.lock"
_LOGIN_TIMEOUT_S = float(os.environ.get("GARMIN_LOGIN_TIMEOUT", "90"))

_api: Any = None
_local_lock = threading.Lock()


def _load_env() -> None:
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


_load_env()


def _token_file() -> Path:
    p = Path(_TOKENSTORE).expanduser()
    if p.is_dir() or not p.name.endswith(".json"):
        p = p / "garmin_tokens.json"
    return p


def _jwt_exp(token: str | None) -> float | None:
    """Best-effort decode of a JWT ``exp`` claim (seconds since epoch)."""
    if not token:
        return None
    try:
        parts = token.split(".")
        if len(parts) < 2:
            return None
        pad = parts[1] + "=" * (-len(parts[1]) % 4)
        payload = json.loads(base64.urlsafe_b64decode(pad).decode())
        exp = payload.get("exp")
        return float(exp) if exp else None
    except Exception:
        return None


def token_status() -> dict[str, Any]:
    """Report cached-token health without touching the network."""
    p = _token_file()
    if not p.exists():
        return {"cached": False, "reason": "no token file"}
    try:
        data = json.loads(p.read_text())
    except Exception as e:  # noqa: BLE001
        return {"cached": False, "reason": f"unreadable: {e}"}
    exp = _jwt_exp(data.get("di_token"))
    now = time.time()
    hours_left = round((exp - now) / 3600, 1) if exp else None
    return {
        "cached": True,
        "has_refresh_token": bool(data.get("di_refresh_token")),
        "di_token_expires_in_h": hours_left,
        "di_token_valid": (exp is not None and exp > now),
        "path": str(p),
    }


class _FileLock:
    """Advisory cross-process lock via ``fcntl.flock`` (POSIX)."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._fh: Any = None

    def __enter__(self) -> "_FileLock":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = open(self.path, "w")  # noqa: SIM115
        try:
            import fcntl

            fcntl.flock(self._fh.fileno(), fcntl.LOCK_EX)
        except Exception:
            # Non-POSIX or flock unavailable: degrade to no cross-process lock
            # (in-process lock still applies).
            pass
        return self

    def __exit__(self, *exc: Any) -> None:
        try:
            import fcntl

            if self._fh is not None:
                fcntl.flock(self._fh.fileno(), fcntl.LOCK_UN)
        except Exception:
            pass
        finally:
            if self._fh is not None:
                self._fh.close()
                self._fh = None


def _skip_strategies() -> set[str]:
    raw = os.environ.get("GARMIN_SKIP_STRATEGIES", "").strip()
    if not raw:
        return set()
    return {s.strip() for s in raw.split(",") if s.strip()}


def _do_login(login_timeout: float) -> Any:
    """Build a Garmin client and log in, with a hard fail-fast timeout.

    Everything network- or import-heavy (importing ``garminconnect``, building
    the client, and ``login``) runs inside a DAEMON worker thread so the whole
    thing is bounded by ``login_timeout`` and the process can exit promptly on
    timeout. signal.alarm only works on the main thread; a thread works anywhere
    (the MCP server calls this off the main thread). A ThreadPoolExecutor is
    unsuitable: its threads are non-daemon and shutdown(wait=True) would block on
    a stalled login, so a timed-out process could linger for minutes. A daemon
    thread dies with the process instead.
    """
    email = os.environ.get("GARMIN_EMAIL", "").strip()
    password = os.environ.get("GARMIN_PASSWORD", "").strip()
    tokenstore = str(Path(_TOKENSTORE).expanduser().resolve())
    Path(tokenstore).parent.mkdir(parents=True, exist_ok=True)
    skip = _skip_strategies()

    result: dict[str, Any] = {}

    def _worker() -> None:
        try:
            from garminconnect import Garmin

            g = Garmin(email=email or None, password=password or None)
            if skip:
                try:
                    g.client.skip_strategies = skip
                except Exception:
                    pass
            g.login(tokenstore)
            result["client"] = g
        except BaseException as exc:  # noqa: BLE001
            result["error"] = exc

    t = threading.Thread(target=_worker, name="garmin-login", daemon=True)
    t.start()
    t.join(timeout=login_timeout)

    if t.is_alive():
        raise TimeoutError(
            f"Garmin login exceeded {login_timeout:.0f}s — likely rate limited "
            "(429) or the SSO chain stalled. Wait a minute and retry; do not "
            "launch parallel Garmin processes."
        )
    if "error" in result:
        raise result["error"]
    return result["client"]


def get_client(*, login_timeout: float | None = None, force: bool = False) -> Any:
    """Return a logged-in Garmin client, reused across the process.

    Serialises login across processes with a file lock and across threads with a
    local lock, and fails fast (raises) instead of hanging if login stalls.
    """
    global _api
    if _api is not None and not force:
        return _api

    timeout = _LOGIN_TIMEOUT_S if login_timeout is None else login_timeout
    with _local_lock:
        if _api is not None and not force:
            return _api
        with _FileLock(_LOCK_PATH):
            _api = _do_login(timeout)
    return _api


def refresh(*, verbose: bool = True) -> dict[str, Any]:
    """Warm up (or renew) the cached token; return a health summary.

    Used by the keep-warm scheduled job and for manual health checks. Fast when
    the token is already valid.
    """
    before = token_status()
    get_client(force=True)
    after = token_status()
    ok = bool(after.get("di_token_valid"))
    if verbose:
        exp = after.get("di_token_expires_in_h")
        exp_s = f"{exp}h" if exp is not None else "unknown"
        print(
            f"Garmin auth {'OK' if ok else 'FAILED'} — "
            f"di_token valid={after.get('di_token_valid')} expires_in={exp_s} "
            f"(was {before.get('di_token_expires_in_h')}h)"
        )
    return after
