"""Minimal client for the SiO Athletica booking system (iBooking platform).

Reverse-engineered from https://sio.ibooking.no/webapp/timeplan/ .

Read endpoints work with a public "client token" that the web app embeds.
Booking/cancelling requires logging in with your SiO mobile number + password,
which yields a personal auth token that is cached on disk.

API base: https://sio.ibooking.no/webapp/api/
    GET  Schedule/getStudios?token=<token>&lang=no
    GET  Schedule/getSchedule?token=<token>&studios=<sid,sid>&lang=no
    GET  Config/getConfigs?token=<token>&sid=<sid>&lang=no
    POST User/login            {username, password, token=<clientToken>}
    GET  User/getBookings?token=<authToken>&lang=no
    POST Schedule/addBooking   {classId, token=<authToken>, childCareAbove, childCareBelow}
    POST Schedule/cancelBooking{classId, token=<authToken>}
    POST User/validateToken    {token=<authToken>}
"""

from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path

import httpx

BASE = "https://sio.ibooking.no"
API = f"{BASE}/webapp/api/"
TIMEPLAN_URL = f"{BASE}/webapp/timeplan/"

# SiO Athletica centres (studio ids), discovered via Schedule/getStudios.
STUDIOS: dict[str, int] = {
    "blindern": 715,
    "centrum": 718,
    "domus": 721,
    "nydalen": 724,
    "vulkan": 727,
    "kringsja": 893,
}

_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

_AUTH_PATH = Path(
    os.environ.get(
        "SIO_TOKEN_STORE",
        str(Path.home() / ".treningsagent" / "sio_auth.json"),
    )
)


class IBookingError(RuntimeError):
    pass


class SioClient:
    def __init__(self, username: str | None = None, password: str | None = None):
        self.username = username or os.environ.get("SIO_USERNAME")
        self.password = password or os.environ.get("SIO_PASSWORD")
        self._client_token: str | None = None
        self._auth_token: str | None = None
        self._http = httpx.Client(
            timeout=25.0,
            headers={"User-Agent": _UA, "Accept": "application/json, text/javascript, */*"},
            follow_redirects=True,
        )
        self._load_auth()

    # ---------- tokens ----------
    def client_token(self) -> str:
        """Public token embedded in the timeplan web app (used for reads)."""
        if self._client_token:
            return self._client_token
        html = self._http.get(TIMEPLAN_URL).text
        m = re.search(r'clientToken\s*=\s*"([a-f0-9]+)"', html)
        if not m:
            raise IBookingError("Could not extract client token from SiO booking page")
        self._client_token = m.group(1)
        return self._client_token

    def _load_auth(self) -> None:
        try:
            data = json.loads(_AUTH_PATH.read_text())
            self._auth_token = data.get("authToken")
        except Exception:
            self._auth_token = None

    def _save_auth(self, auth: dict) -> None:
        _AUTH_PATH.parent.mkdir(parents=True, exist_ok=True)
        _AUTH_PATH.write_text(json.dumps(auth))
        try:
            os.chmod(_AUTH_PATH, 0o600)
        except OSError:
            pass

    # ---------- auth ----------
    def is_logged_in(self) -> bool:
        if not self._auth_token:
            return False
        r = self._http.post(
            f"{BASE}/webapp/api/User/validateToken", data={"token": self._auth_token}
        )
        try:
            body = r.json()
        except Exception:
            return False
        return not body.get("error") and body.get("info") != "client-readonly"

    def login(self) -> None:
        if not self.username or not self.password:
            raise IBookingError(
                "SIO_USERNAME (mobile number) and SIO_PASSWORD must be set to book/cancel."
            )
        if self.is_logged_in():
            return
        r = self._http.post(
            f"{API}User/login",
            data={
                "username": self.username,
                "password": self.password,
                "token": self.client_token(),
            },
        )
        try:
            body = r.json()
        except Exception:
            raise IBookingError(f"Login failed (HTTP {r.status_code})")
        if body.get("error"):
            raise IBookingError(f"Login failed: {body.get('error')}")
        token = body.get("authToken") or (body.get("auth") or {}).get("authToken")
        if not token:
            raise IBookingError("Login succeeded but no auth token was returned")
        self._auth_token = token
        body["authToken"] = token
        self._save_auth(body)

    def _auth(self) -> str:
        if not self.is_logged_in():
            self.login()
        assert self._auth_token
        return self._auth_token

    # ---------- reads ----------
    def _get(self, path: str, params: dict) -> dict | list:
        params.setdefault("lang", "no")
        r = self._http.get(f"{API}{path}", params=params)
        r.raise_for_status()
        return r.json()

    def get_studios(self) -> list[dict]:
        data = self._get("Schedule/getStudios", {"token": self.client_token()})
        return data.get("studios", []) if isinstance(data, dict) else []

    def get_schedule(self, studio_ids: list[int]) -> list[dict]:
        data = self._get(
            "Schedule/getSchedule",
            {"token": self.client_token(), "studios": ",".join(map(str, studio_ids))},
        )
        return data.get("days", []) if isinstance(data, dict) else []

    def get_config(self, sid: int) -> dict:
        data = self._get("Config/getConfigs", {"token": self.client_token(), "sid": sid})
        return data.get("configs", {}) if isinstance(data, dict) else {}

    def get_bookings(self) -> list[dict]:
        token = self._auth()
        data = self._get("User/getBookings", {"token": token})
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return data.get("bookings", []) or []
        return []

    # ---------- writes ----------
    def add_booking(self, class_id: int) -> dict:
        token = self._auth()
        r = self._http.post(
            f"{API}Schedule/addBooking",
            data={
                "classId": class_id,
                "token": token,
                "childCareAbove": 0,
                "childCareBelow": 0,
            },
        )
        return self._write_result(r)

    def cancel_booking(self, class_id: int) -> dict:
        token = self._auth()
        r = self._http.post(
            f"{API}Schedule/cancelBooking",
            data={"classId": class_id, "token": token},
        )
        return self._write_result(r)

    @staticmethod
    def _write_result(r: httpx.Response) -> dict:
        try:
            body = r.json()
        except Exception:
            raise IBookingError(f"Unexpected response (HTTP {r.status_code}): {r.text[:200]}")
        if isinstance(body, dict) and body.get("error"):
            raise IBookingError(str(body["error"]))
        return body if isinstance(body, dict) else {"result": body}


def resolve_studio(name_or_id: str | int) -> int:
    """Accept a centre name ('blindern', 'Athletica Vulkan') or a numeric sid."""
    if isinstance(name_or_id, int):
        return name_or_id
    s = str(name_or_id).strip().lower()
    if s.isdigit():
        return int(s)
    s = s.replace("athletica", "").replace("å", "a").replace("ø", "o").strip()
    for key, sid in STUDIOS.items():
        if key in s or s in key:
            return sid
    raise IBookingError(
        f"Unknown SiO centre '{name_or_id}'. Known: {', '.join(STUDIOS)}"
    )
