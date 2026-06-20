export const dynamic = 'force-dynamic';

import { NextRequest, NextResponse } from 'next/server';

const BASE_URL = process.env.NEXT_PUBLIC_SITE_URL || 'http://localhost:3000';
const CLOUDFLARE_WORKER_URL = process.env.NEXT_PUBLIC_CLOUDFLARE_WORKER_URL || '';

const isHttps = (s: string) => s.startsWith('https://') || s.startsWith('//');
const isHttp = (s: string) => s.startsWith('http://');
const isPlaylist = (s: string) => /\.m3u8?\b/i.test(s.split('?')[0]);

const proxyWrap = (u: string) => `/api/proxy?url=${encodeURIComponent(u)}`;
const segmentWrap = (u: string) =>
  CLOUDFLARE_WORKER_URL
    ? `${CLOUDFLARE_WORKER_URL}?url=${encodeURIComponent(u)}`
    : proxyWrap(u);

async function fetchWithTimeout(url: string, timeout = 30000) {
  const controller = new AbortController();
  const id = setTimeout(() => controller.abort(), timeout);
  try {
    const res = await fetch(url, {
      method: 'GET',
      headers: {
        'User-Agent': 'Mozilla/5.0 IPTVProxy/1.0',
        // Accept anything
      },
      signal: controller.signal,
    });
    clearTimeout(id);
    return res;
  } catch (err) {
    clearTimeout(id);
    throw err;
  }
}

export async function GET(request: NextRequest) {
  const urlParam = new URL(request.url).searchParams.get('url');
  if (!urlParam) {
    return NextResponse.json({ error: 'Missing url parameter' }, { status: 400 });
  }

  const target = urlParam;

  try {
    const response = await fetchWithTimeout(target, 30000);

    if (!response.ok) {
      return NextResponse.json({ error: `Upstream returned ${response.status}` }, { status: 502 });
    }

    const contentType = response.headers.get('content-type') || '';

    // treat playlists specially
    if (target.includes('.m3u8') || /mpegurl/i.test(contentType)) {
      const manifest = await response.text();
      const baseForRelative = target;

      const rewritten = manifest
        .split('\n')
        .map((line) => {
          const trimmed = line.trim();

          // comment/metadata lines may contain URI="..."
          if (trimmed.startsWith('#')) {
            return line.replace(/URI="([^"]+)"/g, (_, uri) => {
              try {
                // resolve relative URIs against the playlist base
                const abs = new URL(uri, baseForRelative).href;

                if (isPlaylist(abs)) return `URI="${proxyWrap(abs)}"`;
                if (isHttps(abs)) return `URI="${abs}"`;
                if (isHttp(abs)) return `URI="${segmentWrap(abs)}"`;
                return `URI="${abs}"`;
              } catch (e) {
                // fallback when URL resolution fails
                if (isHttps(uri)) return `URI="${uri}"`;
                if (isHttp(uri)) return `URI="${segmentWrap(uri)}"`;
                return `URI="${segmentWrap(uri)}"`;
              }
            });
          }

          // non-comment lines are usually URIs to segments or sub-playlists
          if (isHttps(trimmed)) return line; // keep https links as-is

          if (isHttp(trimmed)) {
            const indent = line.match(/^\s*/)?.[0] || '';
            return `${indent}${segmentWrap(trimmed)}`;
          }

          try {
            const absoluteUrl = new URL(trimmed, baseForRelative).href;
            const indent = line.match(/^\s*/)?.[0] || '';

            if (isPlaylist(absoluteUrl)) return `${indent}${proxyWrap(absoluteUrl)}`;
            if (isHttps(absoluteUrl)) return `${indent}${absoluteUrl}`;
            if (isHttp(absoluteUrl)) return `${indent}${segmentWrap(absoluteUrl)}`;

            return `${indent}${absoluteUrl}`;
          } catch (e) {
            return line;
          }
        })
        .join('\n');

      return new Response(rewritten, {
        status: 200,
        headers: { 'Content-Type': 'application/vnd.apple.mpegurl' },
      });
    }

    // for non-playlist responses, stream the bytes back
    const arrayBuffer = await response.arrayBuffer();
    const body = new Uint8Array(arrayBuffer);

    return new Response(body, {
      status: 200,
      headers: { 'Content-Type': contentType || 'application/octet-stream' },
    });
  } catch (err: any) {
    const message = err?.name === 'AbortError' ? 'Timeout fetching upstream' : err?.message || String(err);
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
