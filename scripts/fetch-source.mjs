#!/usr/bin/env node
/**
 * Fetch a public source document that refuses scripted access.
 *
 * `gao.gov`, `files.gao.gov`, `esd.whs.mil` and `media.defense.gov` all return HTTP 403 to
 * curl, wget and any plain HTTP client, regardless of headers. They serve the same files
 * without complaint to a real browser. Every GAO sidecar in `sources/` records this, and
 * each one was fetched by hand as a result.
 *
 * This script does it repeatably: it drives the Chromium that Playwright already installed
 * for the UI suite, loads the document's own landing page so the request carries a real
 * origin and whatever cookies the site sets, then issues the download from inside that page
 * context and writes the bytes out.
 *
 *   node scripts/fetch-source.mjs <url> <out> [--referer <page>]
 *
 * It verifies the result is what it claims to be: a file whose name ends `.pdf` must begin
 * with `%PDF-`, or the script exits non-zero rather than saving an error page under a
 * trustworthy filename. That check exists because the failure mode here is silent — a 403
 * HTML body saved as `gao-22-106055.pdf` looks fine in a directory listing and is worthless.
 */

import { spawn } from 'node:child_process';
import { writeFileSync, existsSync, mkdtempSync, rmSync, readdirSync, mkdirSync } from 'node:fs';
import { resolve, dirname, join } from 'node:path';
import { tmpdir, homedir } from 'node:os';

function findChrome() {
  if (process.env.CHROME && existsSync(process.env.CHROME)) return process.env.CHROME;
  const cache = join(homedir(), '.cache', 'ms-playwright');
  if (existsSync(cache)) {
    const builds = readdirSync(cache)
      .filter((d) => d.startsWith('chromium-'))
      .sort((a, b) => Number(b.split('-')[1]) - Number(a.split('-')[1]));
    for (const b of builds) {
      for (const rel of ['chrome-linux64/chrome', 'chrome-linux/chrome']) {
        const p = join(cache, b, rel);
        if (existsSync(p)) return p;
      }
    }
  }
  for (const p of ['/usr/bin/google-chrome', '/usr/bin/chromium', '/usr/bin/chromium-browser']) {
    if (existsSync(p)) return p;
  }
  throw new Error('no Chromium found; set $CHROME');
}

const argv = process.argv.slice(2);
const positional = [];
let referer = null;
for (let i = 0; i < argv.length; i++) {
  if (argv[i] === '--referer') referer = argv[++i];
  else positional.push(argv[i]);
}
if (positional.length !== 2) throw new Error('usage: fetch-source.mjs <url> <out> [--referer <page>]');
const [url, outPath] = positional;

const profile = mkdtempSync(join(tmpdir(), 'fetchsrc-'));
const chrome = spawn(findChrome(), [
  '--headless=new', '--disable-gpu', '--no-sandbox', '--remote-debugging-port=0',
  `--user-data-dir=${profile}`, 'about:blank',
], { stdio: ['ignore', 'pipe', 'pipe'] });

let stderr = '';
const port = await new Promise((res, rej) => {
  const t = setTimeout(() => rej(new Error('Chromium did not report a debugging port')), 30000);
  chrome.stderr.on('data', (d) => {
    stderr += d.toString();
    const m = stderr.match(/ws:\/\/127\.0\.0\.1:(\d+)\//);
    if (m) { clearTimeout(t); res(Number(m[1])); }
  });
});

const { webSocketDebuggerUrl } = await (await fetch(`http://127.0.0.1:${port}/json/new?about:blank`, { method: 'PUT' })).json();
const ws = new WebSocket(webSocketDebuggerUrl);
await new Promise((r) => ws.addEventListener('open', r));

let id = 0;
const pending = new Map();
ws.addEventListener('message', (e) => {
  const msg = JSON.parse(e.data);
  if (msg.id && pending.has(msg.id)) { pending.get(msg.id)(msg); pending.delete(msg.id); }
});
const send = (method, params = {}) => new Promise((res, rej) => {
  const n = ++id;
  pending.set(n, (m) => (m.error ? rej(new Error(`${method}: ${m.error.message}`)) : res(m.result)));
  ws.send(JSON.stringify({ id: n, method, params }));
});

const landing = referer || new URL(url).origin;
await send('Page.enable');
await send('Page.navigate', { url: landing });
await new Promise((r) => setTimeout(r, 4000));

const expr = `
  (async () => {
    const r = await fetch(${JSON.stringify(url)}, { credentials: 'include' });
    if (!r.ok) return { error: r.status + ' ' + r.statusText };
    const b = new Uint8Array(await r.arrayBuffer());
    let s = ''; const C = 0x8000;
    for (let i = 0; i < b.length; i += C) s += String.fromCharCode.apply(null, b.subarray(i, i + C));
    return { b64: btoa(s), len: b.length };
  })()
`;
const { result, exceptionDetails } = await send('Runtime.evaluate', { expression: expr, awaitPromise: true, returnByValue: true });
chrome.kill();
rmSync(profile, { recursive: true, force: true });

// A cross-origin fetch throws inside the page rather than returning a status, so the
// exception has to be surfaced or the failure reads as "undefined". The fix on the caller's
// side is a --referer on the same origin as the file, which is the default when omitted.
if (exceptionDetails) {
  const d = exceptionDetails.exception?.description || exceptionDetails.text || 'unknown';
  console.error(`fetch-source: ${url} -> the page threw: ${d.split('\n')[0]}`);
  process.exit(1);
}
if (!result.value || result.value.error) {
  console.error(`fetch-source: ${url} -> ${result.value ? result.value.error : 'no response'}`);
  process.exit(1);
}
const buf = Buffer.from(result.value.b64, 'base64');
if (outPath.endsWith('.pdf') && buf.subarray(0, 5).toString('latin1') !== '%PDF-') {
  console.error(
    `fetch-source: ${url} returned ${buf.length} bytes that are not a PDF ` +
    `(starts ${JSON.stringify(buf.subarray(0, 40).toString('latin1'))}). Refusing to write ` +
    `${outPath}, because an error page saved under that name would look like a real source.`
  );
  process.exit(2);
}
mkdirSync(dirname(resolve(outPath)), { recursive: true });
writeFileSync(outPath, buf);
console.log(`${url} -> ${outPath} (${buf.length} bytes)`);
