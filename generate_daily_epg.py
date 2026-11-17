#!/usr/bin/env python3
"""Build a Lookup.txt-filtered XMLTV guide from the upstream XMLTV feed."""

from __future__ import annotations

import gzip
import html
import shutil
import sys
import tempfile
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET

EPG_URL = "https://epgshare01.online/epgshare01/epg_ripper_ALL_SOURCES1.xml.gz"
LOOKUP_PATH = Path("Lookup.txt")
OUTPUT_PATH = Path("DailyEPG.xml.gz")
HEADERS = {"User-Agent": "M3UCurator-IPTVList-DailyEPG/1.0"}


def load_channel_ids() -> set[str]:
    if not LOOKUP_PATH.is_file():
        raise RuntimeError(f"Lookup file not found: {LOOKUP_PATH}")

    channel_ids = {
        html.unescape(line.strip())
        for line in LOOKUP_PATH.read_text(encoding="utf-8-sig").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }
    if not channel_ids:
        raise RuntimeError(f"No channel IDs found in {LOOKUP_PATH}")
    return channel_ids


def build_epg(channel_ids: set[str]) -> bytes:
    request = Request(EPG_URL, headers=HEADERS)
    with tempfile.TemporaryFile(mode="w+b") as download:
        try:
            with urlopen(request, timeout=180) as response:
                shutil.copyfileobj(response, download)
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            raise RuntimeError(f"Could not download EPG source: {exc}") from exc

        download.seek(0)
        source = gzip.GzipFile(fileobj=download, mode="rb")
        root_attributes: dict[str, str] = {}
        channels: list[ET.Element] = []
        programmes: list[ET.Element] = []
        matched_channel_ids: set[str] = set()
        root_seen = False

        try:
            for event, element in ET.iterparse(source, events=("start", "end")):
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
                element.clear()
        except (ET.ParseError, OSError) as exc:
            raise RuntimeError(f"EPG source is not valid readable XML: {exc}") from exc
        finally:
            source.close()

    if not root_seen:
        raise RuntimeError("EPG source is empty")
    if not programmes:
        raise RuntimeError(
            f"No programmes matched the {len(channel_ids)} channel IDs in {LOOKUP_PATH}; "
            "refusing to write an empty guide"
        )

    output_root = ET.Element("tv", root_attributes)
    output_root.set("generator-info-name", "M3UCurator IPTVList Daily EPG")
    output_root.set("generator-info-url", "https://github.com/M3UCurator/IPTVList")

    for channel in channels:
        output_root.append(channel)
    for programme in programmes:
        output_root.append(programme)

    missing = sorted(channel_ids - matched_channel_ids, key=str.casefold)
    print(
        f"Matched {len(matched_channel_ids)} channel definitions and "
        f"{len(programmes)} programmes for {len(channel_ids)} lookup IDs."
    )
    if missing:
        print(f"No channel definition found for {len(missing)} lookup ID(s).")

    return b'<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(output_root, encoding="utf-8")


def main() -> None:
    try:
        channel_ids = load_channel_ids()
        epg_xml = build_epg(channel_ids)
        OUTPUT_PATH.write_bytes(gzip.compress(epg_xml, compresslevel=9, mtime=0))
        print(f"Wrote {OUTPUT_PATH} ({OUTPUT_PATH.stat().st_size} bytes)")
    except (HTTPError, URLError, TimeoutError, OSError, RuntimeError) as exc:
        print(f"Daily EPG generation failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
