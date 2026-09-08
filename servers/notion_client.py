"""Notion REST API helpers for Workout Coach training program."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

NOTION_VERSION = "2022-06-28"
ROOT = Path(__file__).resolve().parents[1]
STATE_PATH = ROOT / "data" / "notion_state.json"


def _token() -> str:
    token = os.environ.get("NOTION_TOKEN", "").strip()
    if not token:
        raise RuntimeError(
            "NOTION_TOKEN is not set. Create a Notion integration, share the "
            "Workout Coach page with it, and add the token to .env."
        )
    return token


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {_token()}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }


def workout_coach_page_id() -> str:
    page_id = os.environ.get("NOTION_WORKOUT_COACH_PAGE_ID", "").strip()
    if not page_id:
        raise RuntimeError(
            "NOTION_WORKOUT_COACH_PAGE_ID is not set. Put your Workout Coach "
            "Notion page id in .env (see .env.example)."
        )
    return page_id


def md_rich_text(text: str) -> list[dict]:
    """Convert a small subset of markdown to Notion rich_text.

    Supports **bold** and `code`. The Notion API does not parse markdown, so
    literal ``**`` / backticks would otherwise show up in the page.
    """
    text = (text or "")[:2000]
    segments: list[dict] = []
    i = 0
    n = len(text)
    buf = ""

    def flush(extra: dict | None = None) -> None:
        nonlocal buf
        if buf:
            seg: dict = {"type": "text", "text": {"content": buf}}
            if extra:
                seg["annotations"] = extra
            segments.append(seg)
            buf = ""

    while i < n:
        if text.startswith("**", i):
            end = text.find("**", i + 2)
            if end != -1:
                flush()
                inner = text[i + 2 : end]
                if inner:
                    segments.append(
                        {
                            "type": "text",
                            "text": {"content": inner},
                            "annotations": {"bold": True},
                        }
                    )
                i = end + 2
                continue
        if text[i] == "`":
            end = text.find("`", i + 1)
            if end != -1:
                flush()
                inner = text[i + 1 : end]
                if inner:
                    segments.append(
                        {
                            "type": "text",
                            "text": {"content": inner},
                            "annotations": {"code": True},
                        }
                    )
                i = end + 1
                continue
        buf += text[i]
        i += 1

    flush()
    return segments or [{"type": "text", "text": {"content": ""}}]


def load_state() -> dict[str, Any]:
    if not STATE_PATH.exists():
        return {}
    return json.loads(STATE_PATH.read_text(encoding="utf-8"))


def save_state(state: dict[str, Any]) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def notion_request(method: str, path: str, body: dict | None = None) -> dict:
    url = f"https://api.notion.com/v1{path}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, headers=_headers(), method=method)
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")
        raise RuntimeError(
            f"Notion API {method} {path} failed ({e.code}): {detail}"
        ) from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"Notion API {method} {path} failed: {e.reason}") from e


def get_page(page_id: str) -> dict:
    return notion_request("GET", f"/pages/{page_id}")


def list_block_children(block_id: str) -> list[dict]:
    children: list[dict] = []
    cursor: str | None = None
    while True:
        path = f"/blocks/{block_id}/children?page_size=100"
        if cursor:
            path += f"&start_cursor={cursor}"
        payload = notion_request("GET", path)
        children.extend(payload.get("results", []))
        if not payload.get("has_more"):
            break
        cursor = payload.get("next_cursor")
    return children


def find_child_database(page_id: str, title_contains: str) -> dict | None:
    needle = title_contains.lower()
    for block in list_block_children(page_id):
        if block.get("type") != "child_database":
            continue
        title = _plain_text(block.get("child_database", {}).get("title", ""))
        if needle in title.lower():
            return block
    return None


def query_database(database_id: str, *, filter_body: dict | None = None) -> list[dict]:
    pages: list[dict] = []
    cursor: str | None = None
    while True:
        body: dict[str, Any] = {"page_size": 100}
        if filter_body:
            body["filter"] = filter_body
        if cursor:
            body["start_cursor"] = cursor
        payload = notion_request("POST", f"/databases/{database_id}/query", body)
        pages.extend(payload.get("results", []))
        if not payload.get("has_more"):
            break
        cursor = payload.get("next_cursor")
    return pages


def _plain_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "".join(part.get("plain_text", "") for part in value if isinstance(part, dict))
    if isinstance(value, dict) and value.get("type") == "title":
        return _plain_text(value.get("title", []))
    return ""


def page_title(page: dict) -> str:
    props = page.get("properties", {})
    for prop in props.values():
        if prop.get("type") == "title":
            return _plain_text(prop.get("title", []))
    return ""


def page_field(page: dict, name: str) -> str:
    prop = page.get("properties", {}).get(name, {})
    ptype = prop.get("type")
    if ptype == "rich_text":
        return _plain_text(prop.get("rich_text", []))
    if ptype == "select":
        sel = prop.get("select")
        return sel.get("name", "") if sel else ""
    if ptype == "date":
        date_val = prop.get("date") or {}
        start = date_val.get("start", "")
        end = date_val.get("end", "")
        return f"{start} → {end}" if end else start
    if ptype == "number":
        num = prop.get("number")
        return "" if num is None else str(num)
    return ""


def week_row_to_dict(page: dict) -> dict[str, str]:
    return {
        "id": page.get("id", ""),
        "week": page_title(page),
        "phase": page_field(page, "Phase"),
        "start": page_field(page, "Start"),
        "end": page_field(page, "End"),
        "run_km": page_field(page, "Run km"),
        "running": page_field(page, "Running"),
        "strength": page_field(page, "Strength"),
        "mobility": page_field(page, "Mobility"),
        "quality": page_field(page, "Quality"),
        "notes": page_field(page, "Notes"),
        "status": page_field(page, "Status"),
    }
