const fs = require('fs').promises;
const path = require('path');
const axios = require('axios');

const SOURCES_FILE = process.env.SOURCES_FILE || path.join(__dirname, 'sources.txt');
const OUTPUT_FILE = process.env.OUTPUT_FILE || path.join(__dirname, 'index.json');
const PROXY_BASE = process.env.PROXY_BASE || 'http://localhost:3000/proxy?url=';

function parseSources(text) {
  return text
    .split(/\r?\n/)
    .map(l => l.trim())
    .filter(l => l && !l.startsWith('#'))
    .map(l => {
      // allow lines like: name|http://example.com/master.m3u8 or just a url
      const parts = l.split('|');
      if (parts.length >= 2) {
        return { name: parts[0].trim(), url: parts[1].trim() };
      }
      return { name: l, url: l };
    });
}

function parseM3U8(manifest) {
  const lines = manifest.split(/\r?\n/);
  const variants = [];

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].trim();
    if (line.startsWith('#EXT-X-STREAM-INF')) {
      const attrs = line.substring('#EXT-X-STREAM-INF:'.length);
      // next non-empty non-comment line is the uri
      let j = i + 1;
      let uri = null;
      while (j < lines.length) {
        const l = lines[j].trim();
        if (l === '') { j++; continue; }
        if (!l.startsWith('#')) { uri = l; break; }
        j++;
      }
      variants.push({ attributes: attrs, uri });
    }
  }

  return { lines, variants };
}

async function fetchThroughProxy(url) {
  const proxied = PROXY_BASE + encodeURIComponent(url);
  try {
    const res = await axios.get(proxied, { responseType: 'text', timeout: 30000 });
    return { ok: true, data: res.data, contentType: res.headers['content-type'] || '' };
  } catch (err) {
    return { ok: false, error: err.message };
  }
}

(async () => {
  try {
    const txt = await fs.readFile(SOURCES_FILE, 'utf8');
    const sources = parseSources(txt);

    const out = { generated_at: new Date().toISOString(), sources: [] };

    for (const s of sources) {
      console.log('Processing', s.url);
      const r = await fetchThroughProxy(s.url);
      if (!r.ok) {
        console.warn('Failed to fetch', s.url, r.error);
        out.sources.push({ name: s.name, source_url: s.url, error: r.error });
        continue;
      }

      const manifest = r.data;
      const parsed = parseM3U8(manifest);

      out.sources.push({
        name: s.name,
        source_url: s.url,
        content_type: r.contentType,
        manifest_rewritten: manifest,
        parsed
      });
    }

    await fs.writeFile(OUTPUT_FILE, JSON.stringify(out, null, 2), 'utf8');
    console.log('Wrote', OUTPUT_FILE);
    process.exit(0);
  } catch (err) {
    console.error('Fatal error', err);
    process.exit(2);
  }
})();
