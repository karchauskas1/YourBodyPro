const { test, before, after } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const http = require('node:http');
const https = require('node:https');
const { execFileSync, spawn } = require('node:child_process');

let directory, upstream, child, port;

before(async () => {
  directory = fs.mkdtempSync(path.join(os.tmpdir(), 'yourbody-gateway-test-'));
  fs.writeFileSync(path.join(directory, 'index.html'), '<h1>Test application</h1>');
  execFileSync('openssl', ['req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-keyout', path.join(directory, 'key.pem'), '-out', path.join(directory, 'cert.pem'), '-days', '1', '-subj', '/CN=localhost'], { stdio: 'ignore' });
  upstream = http.createServer((req, res) => {
    const respond = () => { res.setHeader('content-type', 'application/json'); res.end(JSON.stringify({ ok: true, path: req.url })); };
    if (req.url === '/api/slow') setTimeout(respond, 16000);
    else respond();
  });
  await new Promise(resolve => upstream.listen(0, '127.0.0.1', resolve));
  child = spawn(process.execPath, [path.join(__dirname, 'server.js')], {
    env: { ...process.env, WEBAPP_GATEWAY_PORT: '0', WEBAPP_STATIC_DIR: directory,
      WEBAPP_API_TARGET: `http://127.0.0.1:${upstream.address().port}`,
      WEBAPP_TLS_KEY: path.join(directory, 'key.pem'), WEBAPP_TLS_CERT: path.join(directory, 'cert.pem') },
    stdio: ['ignore', 'pipe', 'pipe'],
  });
  await new Promise((resolve, reject) => {
    const timeout = setTimeout(() => reject(new Error('Gateway did not start')), 10000);
    child.once('exit', code => { clearTimeout(timeout); reject(new Error('Gateway exited: ' + code)); });
    child.stdout.on('data', data => {
      const match = data.toString().match(/listening on (\d+)/);
      if (match) { port = Number(match[1]); clearTimeout(timeout); resolve(); }
    });
  });
});

after(async () => {
  if (child && child.exitCode === null) {
    await new Promise(resolve => { child.once('exit', resolve); child.kill(); });
  }
  if (upstream) await new Promise(resolve => upstream.close(resolve));
  if (directory) fs.rmSync(directory, { recursive: true, force: true });
});

function request(requestPath) {
  return new Promise((resolve, reject) => {
    const req = https.get({ hostname: '127.0.0.1', port, path: requestPath, rejectUnauthorized: false, agent: false }, res => {
      let body = '';
      res.setEncoding('utf8'); res.on('data', chunk => body += chunk);
      res.on('end', () => resolve({ status: res.statusCode, headers: res.headers, body }));
    });
    req.on('error', reject);
    req.setTimeout(25000, () => req.destroy(new Error('Gateway test timeout')));
  });
}

test('serves application routes without caching old HTML', async () => {
  const response = await request('/food/add');
  assert.equal(response.status, 200);
  assert.match(response.body, /Test application/);
  assert.match(response.headers['cache-control'], /no-store/);
});

test('invalid URL encoding is rejected and does not crash the gateway', async () => {
  assert.equal((await request('/%E0%A4%A')).status, 400);
  assert.equal((await request('/api/health')).status, 200);
});

test('an AI response taking longer than 15 seconds reaches the browser', { timeout: 25000 }, async () => {
  const response = await request('/api/slow');
  assert.equal(response.status, 200);
  assert.equal(JSON.parse(response.body).ok, true);
});
