"""
Referrer Extractor for M3U8 Stream Links

This module extracts referrer information from M3U8 playlist files and stream URLs.
It can identify and extract Referer headers, User-Agent strings, and other HTTP headers
needed for streaming content.
"""

import re
import json
import argparse
from urllib.parse import urlparse, parse_qs
from typing import Dict, List, Optional, Tuple, Any

# For fetching remote M3U8 files we try requests first, then fall back to urllib
try:
    import requests  # type: ignore
    _HAS_REQUESTS = True
except Exception:
    import urllib.request
    import urllib.error
    _HAS_REQUESTS = False


class ReferrerExtractor:
    """Extract referrer and header information from M3U8 streams."""
    
    def __init__(self):
        """Initialize the extractor with common patterns."""
        self.header_patterns = {
            'referer': r'#EXT-X-STREAM-INF:.*?[Rr]eferer[=:]?(?:"([^"]+)")?',
            'user_agent': r'[Uu]ser-[Aa]gent[=:]?(?:"([^"]+)")?',
            'headers': r'#EXTINF:.*?headers="([^"]+)"',
        }
    
    def extract_from_url(self, url: str) -> Dict[str, Any]:
        """
        Extract referrer from URL query parameters or fragments.
        
        Args:
            url: Stream URL to extract referrer from
            
        Returns:
            Dictionary with extracted referrer information
        """
        parsed = urlparse(url)
        result = {
            'url': url,
            'referer': '',
            'user_agent': '',
            'headers': {}
        }
        
        # Check query parameters
        params = parse_qs(parsed.query)
        
        for key in ['referer', 'ref', 'referrer']:
            if key in params:
                result['referer'] = params[key][0]
                break
        
        # Check for user-agent
        for key in ['user_agent', 'ua']:
            if key in params:
                result['user_agent'] = params[key][0]
                break
        
        return result
    
    def extract_from_m3u_line(self, line: str) -> Dict[str, str]:
        """
        Extract referrer from M3U8 playlist line.
        
        Args:
            line: Single line from M3U8 playlist
            
        Returns:
            Dictionary with extracted information
        """
        result = {
            'referer': '',
            'user_agent': '',
            'http_headers': ''
        }
        
        # Extract referer
        referer_match = re.search(r'[Rr]eferer[=:]"([^\"]+)"', line)
        if referer_match:
            result['referer'] = referer_match.group(1)
        
        # Extract user-agent
        ua_match = re.search(r'[Uu]ser-[Aa]gent[=:]"([^\"]+)"', line)
        if ua_match:
            result['user_agent'] = ua_match.group(1)
        
        # Extract HTTP headers
        headers_match = re.search(r'[Hh]eaders="([^\"]+)"', line)
        if headers_match:
            result['http_headers'] = headers_match.group(1)
        
        return result
    
    def extract_from_m3u_file(self, filepath: str) -> List[Dict[str, Any]]:
        """
        Extract referrer information from entire M3U8 file.
        
        Args:
            filepath: Path to M3U8 file
            
        Returns:
            List of dictionaries with stream info and referrer data
        """
        streams = []
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            current_info = {}
            
            for line in lines:
                line = line.strip()
                
                if line.startswith('#EXTINF:'):
                    # New stream entry
                    current_info = self.extract_from_m3u_line(line)
                    current_info['extinf'] = line
                    
                elif line.startswith('#EXT-X-STREAM-INF:'):
                    # Stream info line
                    headers_info = self.extract_from_m3u_line(line)
                    current_info.update(headers_info)
                    
                elif line and not line.startswith('#'):
                    # URL line
                    if current_info:
                        current_info['url'] = line
                        current_info.update(self.extract_from_url(line))
                        streams.append(current_info)
                        current_info = {}
        
        except FileNotFoundError:
            print(f"File not found: {filepath}")
            return []
        
        return streams
    
    def build_headers(self, referer: str = '', 
                     user_agent: str = 'Mozilla/5.0') -> Dict[str, str]:
        """
        Build HTTP headers dictionary for requests.
        
        Args:
            referer: Referer URL
            user_agent: User-Agent string
            
        Returns:
            Dictionary of HTTP headers
        """
        headers = {
            'User-Agent': user_agent
        }
        
        if referer:
            headers['Referer'] = referer
        
        return headers
    
    def extract_domain_from_url(self, url: str) -> str:
        """
        Extract domain from URL (useful as fallback referer).
        
        Args:
            url: URL to extract domain from
            
        Returns:
            Domain URL
        """
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}"
    
    def analyze_stream_links(self, file_path: str) -> Dict[str, Any]:
        """
        Analyze M3U8 file and generate referrer requirements report.
        
        Args:
            file_path: Path to M3U8 file
            
        Returns:
            Analysis report with referrer requirements
        """
        streams = self.extract_from_m3u_file(file_path)
        
        report = {
            'total_streams': len(streams),
            'streams_with_referer': 0,
            'streams_with_user_agent': 0,
            'unique_referrers': set(),
            'unique_domains': set(),
            'streams': []
        }
        
        for stream in streams:
            if stream.get('referer'):
                report['streams_with_referer'] += 1
                report['unique_referrers'].add(stream['referer'])
            
            if stream.get('user_agent'):
                report['streams_with_user_agent'] += 1
            
            if stream.get('url'):
                domain = self.extract_domain_from_url(stream['url'])
                report['unique_domains'].add(domain)
            
            report['streams'].append(stream)
        
        # Convert sets to lists for JSON serialization
        report['unique_referrers'] = list(report['unique_referrers'])
        report['unique_domains'] = list(report['unique_domains'])
        
        return report


def _print_json(obj: Any) -> None:
    print(json.dumps(obj, indent=2, ensure_ascii=False))


def _print_summary(report: Dict[str, Any]) -> None:
    print("Analysis Report")
    print("--------------")
    print(f"Total streams: {report.get('total_streams')}")
    print(f"Streams with referer: {report.get('streams_with_referer')}")
    print(f"Streams with user-agent: {report.get('streams_with_user_agent')}")
    print("Unique referrers:")
    for r in report.get('unique_referrers', [])[:10]:
        print(f"  - {r}")
    print("Unique domains:")
    for d in report.get('unique_domains', [])[:10]:
        print(f"  - {d}")
    print("\nFirst 5 streams:")
    for s in report.get('streams', [])[:5]:
        print(f"- URL: {s.get('url')}")
        if s.get('referer'):
            print(f"  Referer: {s.get('referer')}")
        if s.get('user_agent'):
            print(f"  User-Agent: {s.get('user_agent')}")


def _fetch_url_text(url: str, timeout: int = 10) -> Optional[str]:
    """Fetch a remote URL and return its text content.

    Tries requests if available, otherwise uses urllib.
    Returns None on failure.
    """
    try:
        if _HAS_REQUESTS:
            resp = requests.get(url, timeout=timeout)
            resp.raise_for_status()
            # requests automatically decodes based on headers
            return resp.text
        else:
            with urllib.request.urlopen(url, timeout=timeout) as resp:
                bytes_data = resp.read()
                # Try to decode using utf-8, fall back to latin-1
                try:
                    return bytes_data.decode('utf-8')
                except UnicodeDecodeError:
                    return bytes_data.decode('latin-1')
    except Exception as e:
        print(f"Failed to fetch URL {url}: {e}")
        return None


def _analyze_m3u_text(text: str, extractor: ReferrerExtractor) -> List[Dict[str, Any]]:
    lines = text.splitlines()
    streams: List[Dict[str, Any]] = []
    current_info: Dict[str, Any] = {}

    for line in lines:
        line = line.strip()
        if line.startswith('#EXTINF:'):
            current_info = extractor.extract_from_m3u_line(line)
            current_info['extinf'] = line
        elif line.startswith('#EXT-X-STREAM-INF:'):
            headers_info = extractor.extract_from_m3u_line(line)
            current_info.update(headers_info)
        elif line and not line.startswith('#'):
            if current_info:
                current_info['url'] = line
                current_info.update(extractor.extract_from_url(line))
                streams.append(current_info)
                current_info = {}

    return streams


def main(argv: Optional[List[str]] = None) -> None:
    """CLI entrypoint. Supported flags:

    --file PATH       : Analyze an M3U8 file and print a report
    --url  URL        : Extract referrer/user-agent from a single URL (no fetch)
    --fetch-url URL   : Fetch remote M3U8 URL, parse its contents and analyze streams
    --json            : Output machine-readable JSON
    """
    parser = argparse.ArgumentParser(description='ReferrerExtractor CLI')
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--file', '-f', help='Path to M3U8 file to analyze')
    group.add_argument('--url', '-u', help='Single stream URL to extract referrer from (no fetch)')
    group.add_argument('--fetch-url', '-x', help='Fetch remote M3U8 URL and analyze its contents')
    parser.add_argument('--json', '-j', action='store_true', help='Output JSON')
    args = parser.parse_args(argv)

    extractor = ReferrerExtractor()

    if args.file:
        report = extractor.analyze_stream_links(args.file)
        if args.json:
            _print_json(report)
        else:
            _print_summary(report)
        return

    if args.url:
        info = extractor.extract_from_url(args.url)
        if args.json:
            _print_json(info)
        else:
            print(f"URL: {info.get('url')}")
            if info.get('referer'):
                print(f"Referer: {info.get('referer')}")
            if info.get('user_agent'):
                print(f"User-Agent: {info.get('user_agent')}")
            if info.get('headers'):
                print("Headers:")
                for k, v in info.get('headers', {}).items():
                    print(f"  {k}: {v}")
        return

    if args.fetch_url:
        text = _fetch_url_text(args.fetch_url)
        if text is None:
            print("Failed to fetch or decode remote URL")
            return
        streams = _analyze_m3u_text(text, extractor)
        report = {
            'total_streams': len(streams),
            'streams': streams
        }
        if args.json:
            _print_json(report)
        else:
            print(f"Fetched URL: {args.fetch_url}")
            print(f"Total streams found: {len(streams)}")
            for s in streams[:10]:
                print(f"- {s.get('url')}")
                if s.get('referer'):
                    print(f"  Referer: {s.get('referer')}")
                if s.get('user_agent'):
                    print(f"  User-Agent: {s.get('user_agent')}")
        return

    # No args provided: show examples (previous behavior)
    print("No --file, --url or --fetch-url provided. Running built-in examples...\n")

    # Example 1: Extract from URL
    example_url = "https://example.com/stream.m3u8?referer=https://example.com/player&ua=Mozilla/5.0"
    print("=" * 60)
    print("Example 1: Extract from URL")
    print("=" * 60)
    result = extractor.extract_from_url(example_url)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    
    # Example 2: Extract from M3U8 line
    example_line = '#EXTINF:-1, tvg-chno="1", referer="https://example.com", user-agent="Mozilla/5.0"'
    print("\n" + "=" * 60)
    print("Example 2: Extract from M3U8 Line")
    print("=" * 60)
    result = extractor.extract_from_m3u_line(example_line)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    
    # Example 3: Build headers
    print("\n" + "=" * 60)
    print("Example 3: Build HTTP Headers")
    print("=" * 60)
    headers = extractor.build_headers(
        referer='https://example.com/player',
        user_agent='Mozilla/5.0'
    )
    print(json.dumps(headers, indent=2, ensure_ascii=False))
    
    # Example 4: Extract domain from URL
    print("\n" + "=" * 60)
    print("Example 4: Extract Domain")
    print("=" * 60)
    url = "https://stream.example.com:8080/video/stream.m3u8?token=abc123"
    domain = extractor.extract_domain_from_url(url)
    print(f"URL: {url}")
    print(f"Domain: {domain}")
    
    print("\n" + "=" * 60)
    print("ReferrerExtractor initialized successfully!")
    print("=" * 60)


if __name__ == '__main__':
    main()
