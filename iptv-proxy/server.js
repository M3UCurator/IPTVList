const express = require('express');
const axios = require('axios');

const app = express();

const PORT = process.env.PORT || 3000;

app.use((req, res, next) => {
    res.header('Access-Control-Allow-Origin', '*');
    res.header('Access-Control-Allow-Headers', '*');
    res.header('Access-Control-Allow-Methods', 'GET,HEAD,OPTIONS');
    next();
});

function rewriteM3U8(manifest, host) {

    return manifest
        .split('\n')
        .map(line => {

            if (
                !line ||
                line.startsWith('#')
            ) {
                return line;
            }

            return `${host}/proxy?url=${encodeURIComponent(line)}`;
        })
        .join('\n');
}

app.get('/proxy', async (req, res) => {

    const target = req.query.url;

    if (!target) {
        return res.status(400).json({
            error: 'Missing url parameter'
        });
    }

    try {

        const response = await axios({
            url: target,
            method: 'GET',
            responseType: 'arraybuffer',
            timeout: 30000,
            headers: {
                'User-Agent':
                    'Mozilla/5.0 IPTVProxy/1.0'
            }
        });

        const contentType =
            response.headers['content-type'] || '';

        if (
            target.includes('.m3u8') ||
            contentType.includes('mpegurl')
        ) {

            const manifest =
                Buffer.from(response.data).toString();

            const proxyHost =
                `${req.protocol}://${req.get('host')}`;

            const rewritten =
                rewriteM3U8(manifest, proxyHost);

            res.setHeader(
                'Content-Type',
                'application/vnd.apple.mpegurl'
            );

            return res.send(rewritten);
        }

        res.setHeader(
            'Content-Type',
            contentType
        );

        return res.send(response.data);

    } catch (err) {

        return res.status(500).json({
            error: err.message
        });
    }
});

app.get('/', (req, res) => {

    res.json({
        service: 'Generic IPTV Proxy',
        usage:
            '/proxy?url=https://example.com/master.m3u8'
    });
});

app.listen(PORT, () => {
    console.log(`Proxy listening on ${PORT}`);
});