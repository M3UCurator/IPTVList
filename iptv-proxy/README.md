# IPTV Proxy

A generic IPTV proxy server that rewrites and proxies M3U8 streams.

## Features

- Proxies HLS/M3U8 streams with URL rewriting
- CORS enabled for cross-origin requests
- Supports both M3U8 manifests and binary media content
- Configurable port via environment variable

## Setup

```bash
mkdir iptv-proxy
cd iptv-proxy
npm init -y
npm install express axios
```

## Running

Start the proxy server:

```bash
node server.js
```

Or specify a custom port:

```bash
PORT=8080 node server.js
```

The server will listen on `http://localhost:3000` (or your custom PORT).

## Usage

### Basic Request

```
GET http://localhost:3000/
```

Returns service information.

### Proxy a Stream

```
GET http://localhost:3000/proxy?url=https://example.com/master.m3u8
```

The proxy will:
1. Fetch the M3U8 manifest from the provided URL
2. Rewrite all stream URLs to use the proxy
3. Return the rewritten manifest

### Example

Original manifest:
```
#EXTM3U
#EXT-X-VERSION:3
#EXTINF:-1, Stream 1
https://example.com/stream1.ts
#EXTINF:-1, Stream 2
https://example.com/stream2.ts
```

Rewritten manifest returned by proxy:
```
#EXTM3U
#EXT-X-VERSION:3
#EXTINF:-1, Stream 1
http://localhost:3000/proxy?url=https%3A%2F%2Fexample.com%2Fstream1.ts
#EXTINF:-1, Stream 2
http://localhost:3000/proxy?url=https%3A%2F%2Fexample.com%2Fstream2.ts
```

## Environment Variables

- `PORT` - The port to listen on (default: 3000)

## Dependencies

- `express` - Web framework
- `axios` - HTTP client for fetching streams