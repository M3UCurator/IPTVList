#!/usr/bin/env python3
"""Build a playlist-specific XMLTV guide from epgshare's combined feed."""

from __future__ import annotations

import gzip
import io
import re
import shutil
import sys
import tempfile
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET

PLAYLIST_URL = (
    "https://raw.githubusercontent.com/M3UCurator/IPTVList/refs/heads/main/StreamLine.m3u"
)
EPG_URL = "https://epgshare01.online/epgshare01/epg_ripper_ALL_SOURCES1.xml.gz"
LOOKUP_PATH = Path("Lookup.txt")
OUTPUT_PATH = Path("EPG.xml.gz")
HEADERS = {"User-Agent": "M3UCurator-IPTVList-EPG/1.0"}
TVG_ID_RE = re.compile(r'''(?:^|\s)tvg-id\s*=\s*["']([^"']*)["']''', re.IGNORECASE)


def fetch_playlist_ids() -> list[str]:
    request = Request(PLAYLIST_URL, headers=HEADERS)
    with urlopen(request, timeout=60) as response:
        text = response.read().decode("utf-8-sig", errors="replace")

    ids: set[str] = set()
    for line in text.splitlines():
        if not line.lstrip().startswith("#EXTINF:"):
            continue
        match = TVG_ID_RE.search(line)
        if match and match.group(1).strip():
            ids.add(match.group(1).strip())
    return sorted(ids, key=str.casefold)


def open_xml_stream(download: io.BufferedRandom):
    """Return a readable stream for gzip-compressed or plain XML downloads."""
    download.seek(0)
    if download.read(2) == b"\x1f\x8b":
        download.seek(0)
        return gzip.GzipFile(fileobj=download, mode="rb")
    download.seek(0)
    return download


def build_epg(channel_ids: set[str]) -> bytes:
    request = Request(EPG_URL, headers=HEADERS)
    with tempfile.TemporaryFile(mode="w+b") as download:
        try:
            with urlopen(request, timeout=180) as response:
                shutil.copyfileobj(response, download)
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            raise RuntimeError(f"Could not download EPG source: {exc}") from exc

        xml_stream = open_xml_stream(download)
        root_attributes: dict[str, str] = {}
        channels: list[ET.Element] = []
        programmes: list[ET.Element] = []
        matched_channel_ids: set[str] = set()
        matched_programmes = 0
        root_seen = False

        try:
            for event, element in ET.iterparse(xml_stream, events=("start", "end")):
                if event == "start" and not root_seen:
                    root_attributes = dict(element.attrib)
                    root_seen = True
                    continue
                if event != "end":
                    continue

                tag = element.tag.rsplit("}", 1)[-1] if isinstance(element.tag, str) else ""
                if tag == "channel":
                    channel_id = (element.get("id") or "").strip()
                    if channel_id in channel_ids:
                        channels.append(ET.fromstring(ET.tostring(element, encoding="utf-8")))
                        matched_channel_ids.add(channel_id)
                elif tag == "programme":
                    channel_id = (element.get("channel") or "").strip()
                    if channel_id in channel_ids:
                        programmes.append(ET.fromstring(ET.tostring(element, encoding="utf-8")))
                        matched_programmes += 1
                element.clear()
        except ET.ParseError as exc:
            raise RuntimeError(f"EPG source is not valid XML: {exc}") from exc
        finally:
            if xml_stream is not download:
                xml_stream.close()

    if not root_seen:
        raise RuntimeError("EPG source is empty")
    if not programmes:
        raise RuntimeError(
            f"No programmes matched the {len(channel_ids)} playlist tvg-id(s); refusing to write an empty guide"
        )

    output_root = ET.Element("tv", root_attributes)
    output_root.set("generator-info-name", "M3UCurator IPTVList EPG Lookup")
    output_root.set("generator-info-url", "https://github.com/M3UCurator/IPTVList")
    for channel in channels:
        output_root.append(channel)
    for programme in programmes:
        output_root.append(programme)

    print(
        f"Matched {len(matched_channel_ids)} channel definitions and "
        f"{matched_programmes} programmes for {len(channel_ids)} playlist tvg-id(s)."
    )
    missing = sorted(channel_ids - matched_channel_ids, key=str.casefold)
    if missing:
        print(f"No channel definition found for {len(missing)} tvg-id(s); checked programmes by ID.")
    return b'<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(
        output_root, encoding="utf-8"
    )


def main() -> None:
    try:
        ids = fetch_playlist_ids()
        if not ids:
            raise RuntimeError("No non-empty tvg-id values were found in StreamLine.m3u")

        epg_xml = build_epg(set(ids))
        LOOKUP_PATH.write_text("\n".join(ids) + "\n", encoding="utf-8")
        OUTPUT_PATH.write_bytes(gzip.compress(epg_xml, compresslevel=9, mtime=0))
        print(f"Wrote {LOOKUP_PATH} ({len(ids)} unique tvg-id(s))")
        print(f"Wrote {OUTPUT_PATH} ({OUTPUT_PATH.stat().st_size} bytes)")
    except (HTTPError, URLError, TimeoutError, OSError, RuntimeError) as exc:
        print(f"EPG generation failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
