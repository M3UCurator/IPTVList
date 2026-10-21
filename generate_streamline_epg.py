#!/usr/bin/env python3
"""Consolidate multiple XMLTV EPG sources into a single StreamLine EPG archive."""

from __future__ import annotations

import gzip
import sys
from pathlib import Path
from typing import Iterable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET

SOURCES = [
    "https://epgshare01.online/epgshare01/epg_ripper_ZA1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_US2.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_UK1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_US_SPORTS1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_US_LOCALS1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_CA2.xml.gz",
]

OUTPUT_PATH = Path("StreamLine_epg.xml.gz")
REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "application/xml, application/gzip, */*;q=0.8",
    "Accept-Encoding": "gzip, deflate",
}


def fetch_xml_bytes(url: str) -> bytes:
    """Download and decode a remote .xml or .xml.gz file."""
    request = Request(url, headers=REQUEST_HEADERS)
    with urlopen(request, timeout=60) as response:
        payload = response.read()

    if url.lower().endswith(".gz"):
        try:
            return gzip.decompress(payload)
        except OSError:
            return payload

    return payload


def merge_xmltv(files: Iterable[str]) -> bytes:
    """Merge multiple XMLTV sources into one root <tv> element."""
    merged_root = ET.Element(
        "tv",
        {
            "generator-info-name": "StreamLine EPG Consolidator",
            "generator-info-url": "https://github.com/M3UCurator/IPTVList",
            "source-url": ", ".join(files),
        },
    )

    program_keys = set()
    channel_keys = set()

    for url in files:
        try:
            raw = fetch_xml_bytes(url)
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            print(f"Skipping {url}: {exc}", file=sys.stderr)
            continue

        try:
            doc = ET.fromstring(raw)
        except ET.ParseError as exc:
            print(f"Skipping {url}: invalid XML ({exc})", file=sys.stderr)
            continue

        for channel in doc.findall("./channel"):
            cid = (channel.get("id") or "").strip()
            if not cid or cid in channel_keys:
                continue
            channel_keys.add(cid)
            merged_root.append(channel)

        for programme in doc.findall("./programme"):
            channel = programme.get("channel", "")
            start = programme.get("start", "")
            stop = programme.get("stop", "")
            title = (programme.findtext("title") or "").strip()
            key = (channel, start, stop, title)
            if key in program_keys:
                continue
            program_keys.add(key)
            merged_root.append(programme)

    if len(merged_root) == 0:
        raise RuntimeError("No valid XMLTV data could be loaded from any source.")

    return b"<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n" + ET.tostring(merged_root, encoding="utf-8")


def main() -> None:
    xml_bytes = merge_xmltv(SOURCES)
    OUTPUT_PATH.write_bytes(gzip.compress(xml_bytes, compresslevel=9))
    print(f"Wrote {OUTPUT_PATH} ({OUTPUT_PATH.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
