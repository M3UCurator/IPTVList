#!/usr/bin/env python3
"""
Scrape live streams for channels listed in channels.json.

This script uses simple web scraping heuristics (no APIs) to find live YouTube
videos related to each channel entry. It attempts a YouTube search for the
channel handle and display name, then inspects video pages for live/broadcast
indicators. If a channel page (e.g., X/Twitter) contains links to YouTube
live videos, those are followed as well.

Output: output.json (flat array of records)

Note: scraping is brittle. This script tries to be polite (User-Agent header
and small delays), but may still fail or be rate-limited by target sites.
"""

import requests
from bs4 import BeautifulSoup
import json
import time
import urllib.parse
from datetime import datetime
import re
import sys

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; M3UCuratorBot/1.0; +https://github.com/M3UCurator/IPTVList)"
}

YOUTUBE_SEARCH_URL = "https://www.youtube.com/results?search_query={}"

MAX_RESULTS_PER_QUERY = 8
REQUEST_DELAY = 1.0  # seconds between requests to be polite


def load_channels(path="channels.json"):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_output(results, path="output.json"):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)


def find_youtube_video_ids_from_search(query):
    url = YOUTUBE_SEARCH_URL.format(urllib.parse.quote_plus(query))
    resp = requests.get(url, headers=HEADERS, timeout=15)
    time.sleep(REQUEST_DELAY)
    if resp.status_code != 200:
        return []
    html = resp.text
    # quick regex to find /watch?v=VIDEOID patterns
    ids = re.findall(r"/watch\?v=([\w-]{11})", html)
    # preserve order and unique
    seen = set()
    out = []
    for vid in ids:
        if vid not in seen:
            seen.add(vid)
            out.append(vid)
            if len(out) >= MAX_RESULTS_PER_QUERY:
                break
    return out


def is_youtube_video_live(video_id):
    url = f"https://www.youtube.com/watch?v={video_id}"
    resp = requests.get(url, headers=HEADERS, timeout=15)
    time.sleep(REQUEST_DELAY)
    if resp.status_code != 200:
        return None
    html = resp.text

    # Heuristics: look for live indicators in the page HTML
    # 1) JSON keys used by YouTube's page for live streams
    if '"isLiveBroadcast":true' in html or '"isLive":true' in html:
        is_live = True
    else:
        # 2) look for a "LIVE" badge or wording
        if re.search(r"\bLIVE( NOW)?\b", html, re.IGNORECASE):
            is_live = True
        else:
            is_live = False

    # extract metadata
    title = None
    thumbnail = None
    # meta og tags
    m = re.search(r'<meta property="og:title" content="([^"]+)"', html)
    if m:
        title = html_unescape(m.group(1))
    m = re.search(r'<meta property="og:image" content="([^"]+)"', html)
    if m:
        thumbnail = html_unescape(m.group(1))

    # try to extract start timestamp if present in initial data
    start_ts = None
    m = re.search(r'"startTimestamp":"([^"]+)"', html)
    if m:
        start_ts = m.group(1)

    # viewers: search for "watching now" or "concurrent" patterns
    viewers = None
    m = re.search(r'([\d,\.]+)\s+watching now', html, re.IGNORECASE)
    if m:
        viewers = int(m.group(1).replace(',', '').split('.')[0])

    return {
        "video_url": url,
        "is_live": is_live,
        "title": title,
        "thumbnail": thumbnail,
        "startedAt": start_ts,
        "viewers": viewers,
    }


def html_unescape(s: str) -> str:
    return (s.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"').replace("&#39;", "'"))


def try_find_youtube_for_channel(handle_or_name):
    # Try a few queries: handle, name, handle + " live"
    queries = [handle_or_name, f"{handle_or_name} live", f"{handle_or_name} live stream"]
    checked = set()
    for q in queries:
        if q in checked:
            continue
        checked.add(q)
        try:
            ids = find_youtube_video_ids_from_search(q)
        except Exception:
            ids = []
        for vid in ids:
            try:
                info = is_youtube_video_live(vid)
            except Exception:
                info = None
            if info and info.get("is_live"):
                info["videoId"] = vid
                return info
    return None


def find_external_youtube_links_from_page(url):
    # Fetch a generic page (e.g., X/Twitter profile) and look for YouTube links
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        time.sleep(REQUEST_DELAY)
        if resp.status_code != 200:
            return []
        soup = BeautifulSoup(resp.text, "html.parser")
        links = [a.get('href') for a in soup.find_all('a', href=True)]
        yt_ids = []
        for l in links:
            if 'youtube.com/watch' in l or 'youtu.be/' in l:
                m = re.search(r"v=([\w-]{11})", l)
                if m:
                    yt_ids.append(m.group(1))
                else:
                    m = re.search(r"youtu\.be/([\w-]{11})", l)
                    if m:
                        yt_ids.append(m.group(1))
        return list(dict.fromkeys(yt_ids))
    except Exception:
        return []


def normalize_handle_to_x_url(handle):
    h = handle.strip()
    if h.startswith("@"):
        h = h[1:]
    return f"https://x.com/{h}"


def build_record(name, group, source, source_id, live, videoId, url, title, thumbnail, startedAt, viewers):
    return {
        "name": name,
        "group": group,
        "source": source,
        "source_id": source_id,
        "live": bool(live),
        "videoId": videoId,
        "url": url,
        "title": title,
        "thumbnail": thumbnail,
        "startedAt": startedAt,
        "viewers": viewers,
        "fetchedAt": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
    }


def main():
    try:
        channels = load_channels()
    except Exception as e:
        print(f"Failed to load channels.json: {e}", file=sys.stderr)
        sys.exit(1)

    results = []

    for ch in channels:
        name = ch.get("name")
        group = ch.get("group")
        handle = ch.get("channel") or ch.get("handle") or name
        source = None
        source_id = None
        found = False

        # Prefer YouTube search heuristics first (most live streams are on YouTube)
        print(f"Searching YouTube for: {handle} / {name}")
        info = try_find_youtube_for_channel(handle)
        if not info and name:
            info = try_find_youtube_for_channel(name)

        if info and info.get("is_live"):
            rec = build_record(
                name=name,
                group=group,
                source="youtube",
                source_id=None,
                live=True,
                videoId=info.get("videoId"),
                url=info.get("video_url"),
                title=info.get("title"),
                thumbnail=info.get("thumbnail"),
                startedAt=info.get("startedAt"),
                viewers=info.get("viewers"),
            )
            results.append(rec)
            found = True
            print(f"Found live YouTube for {name}: {info.get('videoId')}")
            continue

        # If not found, try scraping the handle page (e.g., x.com/@handle) for YouTube links
        page_url = normalize_handle_to_x_url(handle)
        print(f"Inspecting handle page for external links: {page_url}")
        try:
            yt_ids = find_external_youtube_links_from_page(page_url)
        except Exception:
            yt_ids = []
        for vid in yt_ids:
            try:
                info = is_youtube_video_live(vid)
            except Exception:
                info = None
            if info and info.get("is_live"):
                rec = build_record(
                    name=name,
                    group=group,
                    source="youtube",
                    source_id=None,
                    live=True,
                    videoId=vid,
                    url=info.get("video_url"),
                    title=info.get("title"),
                    thumbnail=info.get("thumbnail"),
                    startedAt=info.get("startedAt"),
                    viewers=info.get("viewers"),
                )
                results.append(rec)
                found = True
                print(f"Found live YouTube from page links for {name}: {vid}")
                break

        if not found:
            # add non-live placeholder entry so the output includes all channels
            rec = build_record(
                name=name,
                group=group,
                source=None,
                source_id=None,
                live=False,
                videoId=None,
                url=None,
                title=None,
                thumbnail=None,
                startedAt=None,
                viewers=None,
            )
            results.append(rec)
            print(f"No live stream found for {name}")

    write_output(results)
    print(f"Wrote {len(results)} records to output.json")


if __name__ == "__main__":
    main()
