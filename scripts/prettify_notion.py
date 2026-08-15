#!/usr/bin/env python3
"""Prettify the existing Workout Coach page: fix markdown, set icon.

The Notion API stores rich_text, not markdown, so the first bootstrap left
literal ``**bold**`` markers on the page. This rewrites each text block in
place (no reordering, no deletes) with proper bold/code annotations, and sets
a running emoji as the page icon.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "servers"))


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


load_env_file(ROOT / ".env")

from notion_client import (  # noqa: E402
    list_block_children,
    md_rich_text,
    notion_request,
    workout_coach_page_id,
)

# Block types that carry an editable rich_text array.
TEXT_TYPES = {
    "paragraph",
    "heading_1",
    "heading_2",
    "heading_3",
    "bulleted_list_item",
    "numbered_list_item",
    "callout",
    "quote",
    "toggle",
    "to_do",
}


def _plain(rich: list[dict]) -> str:
    return "".join(part.get("plain_text", "") for part in rich if isinstance(part, dict))


def prettify_block(block: dict) -> bool:
    btype = block.get("type")
    if btype not in TEXT_TYPES:
        return False
    body = block.get(btype, {})
    rich = body.get("rich_text", [])
    text = _plain(rich)
    if "**" not in text and "`" not in text:
        return False
    notion_request(
        "PATCH",
        f"/blocks/{block['id']}",
        {btype: {"rich_text": md_rich_text(text)}},
    )
    return True


def main() -> int:
    if not os.environ.get("NOTION_TOKEN", "").strip():
        print("ERROR: NOTION_TOKEN not set in .env", file=sys.stderr)
        return 1

    page_id = workout_coach_page_id()
    print(f"Prettifying Workout Coach page: {page_id}")

    try:
        notion_request("PATCH", f"/pages/{page_id}", {"icon": {"type": "emoji", "emoji": "🫒"}})
        print("Set page icon 🫒")
    except Exception as e:  # noqa: BLE001
        print(f"Could not set page icon: {e}")

    fixed = 0
    for block in list_block_children(page_id):
        try:
            if prettify_block(block):
                fixed += 1
                print(f"  fixed {block.get('type')}: {_plain(block[block['type']]['rich_text'])[:60]}")
        except Exception as e:  # noqa: BLE001
            print(f"  skip {block.get('id')}: {e}")

    print(f"\nDone. Rewrote {fixed} block(s) with proper formatting.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
