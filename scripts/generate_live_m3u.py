#!/usr/bin/env python3
"""
scripts/generate_live_m3u.py

Resolve current live YouTube streams for channels listed in ../channels.json
and write a generated_live.m3u file at the repository root.

This script is intentionally dependency-light: it uses requests and BeautifulSoup.

Usage:
  python3 scripts/generate_live_m3u.py

Exit codes:
  0 - success
  1 - error

"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
CHANNELS_FILE = ROOT / "channels.json"
OUTPUT_FILE = ROOT / "generated_live.m3u"

VIDEOID_RE = re.compile(r"watch\?v=([a-zA-Z0-9_-]{11})")
JSON_VIDEOID_RE = re.compile(r'"videoId"\s*:\s*"([a-zA-Z0-9_-]{11})"')

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Accept-Language": "en-US,en;q=0.9",
}


def load_channels(path: Path) -> List[Dict]:
    if not path.exists():
        print(f"Channels file not found: {path}")
        return []
    with path.open("r", encoding="utf8") as f:
        return json.load(f)


def escape_attr(s: str) -> str:
    return s.replace('"', '\\"')


def generate_m3u_entry(name: str, url: str, group: Optional[str] = None) -> str:
    group_attr = escape_attr(group) if group else ""
    group_part = f' group-title="{group_attr}"' if group_attr else ""
    tvg_name = escape_attr(name)
    return f'#EXTINF:-1 tvg-name="{tvg_name}"{group_part},{name}\n{url}'


def parse_video_id_from_url(url: str) -> Optional[str]:
    if not url:
        return None
    m = VIDEOID_RE.search(url)
    return m.group(1) if m else None


def resolve_live_for_channel(channel_path: str) -> Optional[str]:
    """Return the watch URL for a live stream, or None if not live/detectable."""
    live_url = f"https://www.youtube.com/{channel_path}/live"
    try:
        resp = requests.get(live_url, headers=HEADERS, allow_redirects=True, timeout=15)
    except Exception as e:
        print(f"Error fetching {live_url}: {e}")
        return None

    # 1) check final URL after redirects
    final_url = getattr(resp, "url", None) or ""
    video_id = parse_video_id_from_url(final_url)
    if video_id:
        return f"https://www.youtube.com/watch?v={video_id}"

    # 2) parse HTML: og:video:url or canonical link
    html = resp.text or ""
    try:
        soup = BeautifulSoup(html, "html.parser")
        og = soup.find("meta", property="og:video:url")
        if og and og.get("content"):
            video_id = parse_video_id_from_url(og.get("content"))
            if video_id:
                return f"https://www.youtube.com/watch?v={video_id}"
        canonical = soup.find("link", rel="canonical")
        if canonical and canonical.get("href"):
            video_id = parse_video_id_from_url(canonical.get("href"))
            if video_id:
                return f"https://www.youtube.com/watch?v={video_id}"
    except Exception:
        # non-fatal
        pass

    # 3) search for JSON videoId tokens in page
    m = JSON_VIDEOID_RE.search(html)
    if m:
        return f"https://www.youtube.com/watch?v={m.group(1)}"

    return None


def build_playlist(channels: List[Dict]) -> List[str]:
    entries = []
    for ch in channels:
        name = ch.get("name") or ch.get("title") or ch.get("channel")
        channel_path = ch.get("channel")
        group = ch.get("group")
        if not channel_path:
            print(f"Skipping channel without 'channel' path: {ch}")
            continue
        print(f"Checking {name} ({channel_path})...")
        stream_url = resolve_live_for_channel(channel_path)
        if stream_url:
            print(f"  LIVE -> {stream_url}")
            entries.append(generate_m3u_entry(name, stream_url, group))
        else:
            print("  not live")
    return entries


def write_playlist(entries: List[str], out_path: Path) -> None:
    if not entries:
        print("No live streams found; not writing playlist.")
        return
    header = "#EXTM3U"
    content = header + "\n\n" + "\n\n".join(entries) + "\n"
    out_path.write_text(content, encoding="utf8")
    print(f"Wrote {len(entries)} entries to {out_path}")


def main() -> int:
    channels = load_channels(CHANNELS_FILE)
    if not channels:
        print("No channels configured. Create channels.json in the repo root.")
        return 1
    entries = build_playlist(channels)
    write_playlist(entries, OUTPUT_FILE)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
