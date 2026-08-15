#!/usr/bin/env python3
"""Personify the Workout Coach page as Eda: icon, intro callout, headings, mantra.

Idempotent — safe to re-run. Does not touch the training-week database, only the
page icon and the overview blocks. Rewrites the intro callout in Eda's voice,
bedazzles the section headings with Andrea's own emoji palette, and inserts a
manifestation mantra callout right after the intro.
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

PAGE_ICON = "🫒"

INTRO_CALLOUT = (
    "**Hi, I'm Eda — your coach.** 🫒 **Trondheim Halvmaraton** · 5:25/km · "
    "Q3 build (Jul–Aug 2026). Calendar = when you show up · this database = "
    "what each week looks like. Trust the plan, feel your body, we call it in "
    "together. ✨"
)

MANTRA_MARKER = "Eda's mantra"
MANTRA_TEXT = (
    "**Eda's mantra:** You're not chasing this race — you're becoming the girl "
    "who finishes it. Easy days easy, hard days brave, mind and body on the "
    "same team. I believe in you, so I never feel sorry for you. 🌙💫 — Eda 🫒"
)

# heading text (lowercased, no leading emoji) -> emoji to prepend
HEADING_EMOJI = {
    "trondheim halvmaraton": "🏃‍♀️",
    "weekly structure": "🌺",
    "phases": "🩵",
    "eda's law": "🌷",
}

FIRST_EMOJI_CHARS = set("🫒🌺🐠🩵🌷🦪🍉🪩🩰🏄🌱✨💫🌙🏃💪🍑🧘")


def _plain(rich: list[dict]) -> str:
    return "".join(p.get("plain_text", "") for p in rich if isinstance(p, dict))


def _starts_with_emoji(text: str) -> bool:
    return bool(text) and text[0] in FIRST_EMOJI_CHARS


def main() -> int:
    if not os.environ.get("NOTION_TOKEN", "").strip():
        print("ERROR: NOTION_TOKEN not set in .env", file=sys.stderr)
        return 1

    page_id = workout_coach_page_id()
    print(f"Personifying Workout Coach as Eda: {page_id}")

    try:
        notion_request("PATCH", f"/pages/{page_id}", {"icon": {"type": "emoji", "emoji": PAGE_ICON}})
        print(f"Set page icon {PAGE_ICON}")
    except Exception as e:  # noqa: BLE001
        print(f"Could not set page icon: {e}")

    blocks = list_block_children(page_id)

    # Skip if the mantra already exists anywhere on the page.
    has_mantra = any(
        MANTRA_MARKER in _plain(b.get(b.get("type"), {}).get("rich_text", []))
        for b in blocks
        if isinstance(b.get(b.get("type")), dict)
    )

    intro_callout_id = None
    for b in blocks:
        btype = b.get("type")
        body = b.get(btype, {})
        if not isinstance(body, dict):
            continue
        text = _plain(body.get("rich_text", []))

        # Intro callout — rewrite in Eda's voice.
        if btype == "callout" and "Trondheim Halvmaraton" in text and MANTRA_MARKER not in text:
            intro_callout_id = b["id"]
            notion_request(
                "PATCH",
                f"/blocks/{b['id']}",
                {
                    "callout": {
                        "rich_text": md_rich_text(INTRO_CALLOUT),
                        "icon": {"type": "emoji", "emoji": "🫒"},
                        "color": "pink_background",
                    }
                },
            )
            print("  rewrote intro callout")
            continue

        # Bedazzle headings.
        if btype in ("heading_1", "heading_2", "heading_3"):
            key = text.strip().lower()
            emoji = None
            for needle, e in HEADING_EMOJI.items():
                if key.startswith(needle):
                    emoji = e
                    break
            if emoji and not _starts_with_emoji(text.strip()):
                notion_request(
                    "PATCH",
                    f"/blocks/{b['id']}",
                    {btype: {"rich_text": md_rich_text(f"{emoji} {text.strip()}")}},
                )
                print(f"  bedazzled {btype}: {emoji} {text.strip()[:40]}")

    # Insert the mantra callout right after the intro callout.
    if not has_mantra:
        mantra_block = {
            "object": "block",
            "type": "callout",
            "callout": {
                "rich_text": md_rich_text(MANTRA_TEXT),
                "icon": {"type": "emoji", "emoji": "🌙"},
                "color": "purple_background",
            },
        }
        body: dict = {"children": [mantra_block]}
        if intro_callout_id:
            body["after"] = intro_callout_id
        notion_request("PATCH", f"/blocks/{page_id}/children", body)
        print("  added Eda's mantra callout")
    else:
        print("  mantra already present — skipping")

    print("\nDone. Eda has moved in. 🫒")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
