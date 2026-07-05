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


def _fetch_url_text(url: str, timeout: int = 10, extra_headers: Optional[Dict[str, str]] = None) -> Optional[str]:
    """Fetch a remote URL and return its text content.

    Tries requests if available, otherwise uses urllib.
    Returns None on failure.
    """
    try:
        if _HAS_REQUESTS:
            resp = requests.get(url, timeout=timeout, headers=extra_headers)
            resp.raise_for_status()
            # requests automatically decodes based on headers
            return resp.text
        else:
            if extra_headers is None:
                req = urllib.request.Request(url)
            else:
                req = urllib.request.Request(url, headers=extra_headers)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
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


def _parse_header_string(header_str: str) -> Dict[str, str]:
    """Parse a raw header string into a dict.

    Supports header strings separated by newlines or "\r\n". Each header line
    should be in the form "Key: Value". Lines without a colon are ignored.
    """
    headers: Dict[str, str] = {}
    if not header_str:
        return headers

    for raw_line in header_str.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if ':' in line:
            k, v = line.split(':', 1)
            headers[k.strip()] = v.strip()
    return headers


def _parse_cli_headers(header_list: Optional[List[str]]) -> Dict[str, str]:
    """Parse CLI --header/-H entries into a dict.

    Accepts entries in formats like "Key: Value" or "Key=Value". Repeated
    flags merge, later entries override earlier ones.
    """
    headers: Dict[str, str] = {}
    if not header_list:
        return headers
    for item in header_list:
        if not item:
            continue
        if ':' in item:
            k, v = item.split(':', 1)
        elif '=' in item:
            k, v = item.split('=', 1)
        else:
            # treat whole string as header name with empty value
            k, v = item, ''
        headers[k.strip()] = v.strip()
    return headers


def _request_url(url: str, headers: Dict[str, str], timeout: int = 10) -> Dict[str, Any]:
    """Request a URL with headers and return a small result summary.

    Uses requests if available, otherwise urllib. Returns a dict with either
    status_code and content_type on success or an 'error' key on failure.
    """
    try:
        if _HAS_REQUESTS:
            resp = requests.get(url, headers=headers, timeout=timeout)
            return {
                'status_code': resp.status_code,
                'content_type': resp.headers.get('content-type'),
                'headers': dict(resp.headers)
            }
        else:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                ct = resp.headers.get('content-type') if hasattr(resp, 'headers') else None
                status = getattr(resp, 'status', None)
                return {
                    'status_code': status,
                    'content_type': ct,
                    'headers': dict(resp.getheaders()) if hasattr(resp, 'getheaders') else {}
                }
    except Exception as e:
        return {'error': str(e)}


def main(argv: Optional[List[str]] = None) -> None:
    """CLI entrypoint. Supported flags:

    --file PATH       : Analyze an M3U8 file and print a report
    --url  URL        : Extract referrer/user-agent from a single URL (no fetch)
    --fetch-url URL   : Fetch remote M3U8 URL, parse its contents and analyze streams
    --parse-headers   : Parse raw http_headers strings into dicts and merge into headers
    --request         : Request the parsed stream URLs using the built headers
    --header / -H     : Custom header(s) to include in fetch/request calls (repeatable)
    --json            : Output machine-readable JSON
    --timeout SECS    : Timeout in seconds for network requests (default 10)
    """
    parser = argparse.ArgumentParser(description='ReferrerExtractor CLI')
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--file', '-f', help='Path to M3U8 file to analyze')
    group.add_argument('--url', '-u', help='Single stream URL to extract referrer from (no fetch)')
    group.add_argument('--fetch-url', '-x', help='Fetch remote M3U8 URL and analyze its contents')
    parser.add_argument('--parse-headers', '-p', action='store_true', help='Parse raw http_headers strings into dicts')
    parser.add_argument('--request', '-r', action='store_true', help='Request parsed stream URLs using built headers')
    parser.add_argument('--header', '-H', action='append', help='Custom header to include in fetch/request (format "Key: Value" or "Key=Value"). Repeatable.')
    parser.add_argument('--json', '-j', action='store_true', help='Output JSON')
    parser.add_argument('--timeout', '-t', type=int, default=10, help='Network timeout in seconds (default 10)')
    args = parser.parse_args(argv)

    extractor = ReferrerExtractor()

    # Parse CLI headers once
    cli_headers = _parse_cli_headers(getattr(args, 'header', None))

    def _maybe_request_streams(streams: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        for s in streams:
            url = s.get('url')
            if not url:
                continue

            # Build headers: start with CLI headers, then parsed headers, then add referer/user-agent
            combined_headers: Dict[str, str] = {}
            combined_headers.update(cli_headers)

            # parse http_headers if requested
            if args.parse_headers and s.get('http_headers'):
                parsed = _parse_header_string(s.get('http_headers'))
                combined_headers.update(parsed)

            # prefer explicit referer in stream, otherwise use domain
            referer = s.get('referer') or extractor.extract_domain_from_url(url)
            user_agent = s.get('user_agent') or combined_headers.get('User-Agent') or 'Mozilla/5.0'

            # ensure keys are proper-case for requests/urllib
            if 'User-Agent' not in combined_headers:
                combined_headers['User-Agent'] = user_agent
            if referer and 'Referer' not in combined_headers:
                combined_headers['Referer'] = referer

            res = _request_url(url, combined_headers, timeout=args.timeout)
            entry = {'url': url, 'request_result': res}
            results.append(entry)
        return results

    if args.file:
        report = extractor.analyze_stream_links(args.file)

        # Optionally parse header strings
        if args.parse_headers:
            for s in report.get('streams', []):
                if s.get('http_headers'):
                    s['parsed_headers'] = _parse_header_string(s.get('http_headers'))

        if args.request:
            req_results = _maybe_request_streams(report.get('streams', []))
            report['request_results'] = req_results

        if args.json:
            _print_json(report)
        else:
            _print_summary(report)
            if args.request:
                print('\nRequest results:')
                for r in report.get('request_results', [])[:10]:
                    url = r.get('url')
                    rr = r.get('request_result', {})
                    if 'error' in rr:
                        print(f"- {url} -> ERROR: {rr['error']}")
                    else:
                        print(f"- {url} -> {rr.get('status_code')} {rr.get('content_type')}")
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
        text = _fetch_url_text(args.fetch_url, timeout=args.timeout, extra_headers=cli_headers if cli_headers else None)
        if text is None:
            print("Failed to fetch or decode remote URL")
            return
        streams = _analyze_m3u_text(text, extractor)

        # Optionally parse header strings
        if args.parse_headers:
            for s in streams:
                if s.get('http_headers'):
                    s['parsed_headers'] = _parse_header_string(s.get('http_headers'))

        report = {
            'total_streams': len(streams),
            'streams': streams
        }

        if args.request:
            req_results = _maybe_request_streams(streams)
            report['request_results'] = req_results

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
            if args.request:
                print('\nRequest results:')
                for r in report.get('request_results', [])[:10]:
                    url = r.get('url')
                    rr = r.get('request_result', {})
                    if 'error' in rr:
                        print(f"- {url} -> ERROR: {rr['error']}")
                    else:
                        print(f"- {url} -> {rr.get('status_code')} {rr.get('content_type')}")
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
