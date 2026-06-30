const fs = require('fs');
const http = require('http');
const https = require('https');
const path = require('path');
const { pipeline } = require('stream');
const zlib = require('zlib');

const port = Number(process.env.WEBAPP_GATEWAY_PORT || 8443);
const staticDir = process.env.WEBAPP_STATIC_DIR || path.resolve(__dirname, '../frontend/dist');
const apiTarget = process.env.WEBAPP_API_TARGET || 'http://127.0.0.1:8000';
const certPath = process.env.WEBAPP_TLS_CERT || '/etc/letsencrypt/live/app.pasekaproduction.ru/fullchain.pem';
const keyPath = process.env.WEBAPP_TLS_KEY || '/etc/letsencrypt/live/app.pasekaproduction.ru/privkey.pem';

const mimeTypes = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'application/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.gif': 'image/gif',
  '.webp': 'image/webp',
  '.ico': 'image/x-icon',
  '.woff': 'font/woff',
  '.woff2': 'font/woff2',
};

function sendError(res, statusCode, message) {
  res.writeHead(statusCode, {
    'content-type': 'text/plain; charset=utf-8',
    'cache-control': 'no-store',
    connection: 'close',
  });
  res.end(message);
}

function requestInfo(req) {
  const parsedUrl = new URL(req.url || '/', 'https://app.pasekaproduction.ru');
  return {
    type: 'access',
    method: req.method,
    path: parsedUrl.pathname,
    queryKeys: Array.from(parsedUrl.searchParams.keys()),
    ip: req.socket.remoteAddress,
    userAgent: req.headers['user-agent'],
  };
}

function logAccess(req, res, startedAt) {
  const entry = {
    ...requestInfo(req),
    status: res.statusCode,
    ms: Date.now() - startedAt,
  };
  console.log(JSON.stringify(entry));
}

function receiveBody(req, maxBytes = 65536) {
  return new Promise((resolve, reject) => {
    let body = '';
    req.setEncoding('utf8');
    req.on('data', (chunk) => {
      body += chunk;
      if (body.length > maxBytes) {
        reject(new Error('body too large'));
        req.destroy();
      }
    });
    req.on('end', () => resolve(body));
    req.on('error', reject);
  });
}

async function receiveClientError(req, res) {
  try {
    const body = await receiveBody(req);
    const payload = JSON.parse(body || '{}');
    console.error(JSON.stringify({
      type: 'client_error',
      name: String(payload.name || '').slice(0, 120),
      message: String(payload.message || '').slice(0, 1000),
      stack: String(payload.stack || '').slice(0, 4000),
      source: String(payload.source || '').slice(0, 500),
      line: payload.line || null,
      column: payload.column || null,
      path: String(payload.path || '').slice(0, 500),
      userAgent: String(payload.userAgent || '').slice(0, 500),
    }));
    res.writeHead(204, { 'cache-control': 'no-store', connection: 'close' });
    res.end();
  } catch (error) {
    console.error('client error report failed:', error);
    sendError(res, 400, 'Bad request');
  }
}

function shouldGzip(req, filePath) {
  const acceptEncoding = req.headers['accept-encoding'] || '';
  const ext = path.extname(filePath).toLowerCase();
  return /\bgzip\b/.test(acceptEncoding) && ['.html', '.js', '.css', '.json', '.svg'].includes(ext);
}

function resolveStaticFile(requestPath) {
  const decodedPath = decodeURIComponent(requestPath.split('?')[0]);
  const cleanPath = path.normalize(decodedPath).replace(/^(\.\.[/\\])+/, '');
  const requestedFile = path.join(staticDir, cleanPath);
  const resolvedFile = path.resolve(requestedFile);
  const resolvedStaticDir = path.resolve(staticDir);

  if (!resolvedFile.startsWith(resolvedStaticDir)) {
    return null;
  }

  if (fs.existsSync(resolvedFile) && fs.statSync(resolvedFile).isFile()) {
    return resolvedFile;
  }

  return path.join(staticDir, 'index.html');
}

function serveStatic(req, res) {
  const filePath = resolveStaticFile(new URL(req.url, 'https://app.pasekaproduction.ru').pathname);
  if (!filePath || !fs.existsSync(filePath)) {
    sendError(res, 404, 'Not found');
    return;
  }

  const ext = path.extname(filePath).toLowerCase();
  const isIndex = path.basename(filePath) === 'index.html';
  const headers = {
    'content-type': mimeTypes[ext] || 'application/octet-stream',
    'cache-control': isIndex ? 'no-store, no-cache, must-revalidate' : 'public, max-age=604800, immutable',
    connection: 'close',
  };

  const stream = fs.createReadStream(filePath);
  if (shouldGzip(req, filePath)) {
    headers['content-encoding'] = 'gzip';
    headers.vary = 'Accept-Encoding';
    res.writeHead(200, headers);
    pipeline(stream, zlib.createGzip({ level: 6 }), res, (error) => {
      if (error) console.error('static gzip pipeline failed:', error);
    });
    return;
  }

  res.writeHead(200, headers);
  pipeline(stream, res, (error) => {
    if (error) console.error('static pipeline failed:', error);
  });
}

function proxyApi(req, res) {
  const target = new URL(req.url, apiTarget);
  const headers = {
    ...req.headers,
    host: target.host,
    'x-forwarded-proto': 'https',
    'x-forwarded-host': req.headers.host || 'app.pasekaproduction.ru',
  };

  const proxyReq = http.request(
    {
      protocol: target.protocol,
      hostname: target.hostname,
      port: target.port,
      method: req.method,
      path: target.pathname + target.search,
      headers,
    },
    (proxyRes) => {
      res.writeHead(proxyRes.statusCode || 502, {
        ...proxyRes.headers,
        connection: 'close',
      });
      pipeline(proxyRes, res, (error) => {
        if (error) console.error('api response pipeline failed:', error);
      });
    }
  );

  proxyReq.on('error', (error) => {
    console.error('api proxy failed:', error);
    if (!res.headersSent) {
      sendError(res, 502, 'API gateway error');
    } else {
      res.destroy(error);
    }
  });

  pipeline(req, proxyReq, (error) => {
    if (error) proxyReq.destroy(error);
  });
}

const server = https.createServer(
  {
    key: fs.readFileSync(keyPath),
    cert: fs.readFileSync(certPath),
  },
  (req, res) => {
    const startedAt = Date.now();
    res.shouldKeepAlive = false;
    res.on('finish', () => logAccess(req, res, startedAt));

    if (!req.url) {
      sendError(res, 400, 'Bad request');
      return;
    }

    if (req.url.startsWith('/_webapp_error')) {
      receiveClientError(req, res);
      return;
    }

    if (req.url.startsWith('/api/')) {
      proxyApi(req, res);
      return;
    }

    serveStatic(req, res);
  }
);

server.keepAliveTimeout = 1000;
server.headersTimeout = 5000;
server.requestTimeout = 15000;
server.setTimeout(15000, (socket) => {
  socket.destroy();
});

server.listen(port, '0.0.0.0', () => {
  console.log(`YourBody WebApp gateway listening on ${port}`);
});
