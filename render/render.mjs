#!/usr/bin/env node
// Frame renderer: opens <project>/comp/index.html in headless Chromium and seeks it frame by frame.
// Usage:
//   node render.mjs --project DIR --frames OUT_DIR [--fps 30] [--scale 1] [--workers 3] [--from 0] [--to 99]
//   node render.mjs --project DIR --still 0,3.5 --frames OUT_DIR           (PNG stills)
//   node render.mjs --project DIR --qa 0.5,3.2                               (layout report as JSON on stdout)
//   node render.mjs --project DIR --cover OUT.png --w 1080 --h 1920 --variant hero
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, '..');
const require = createRequire(import.meta.url);
let chromium;
try { ({ chromium } = require('playwright')); } catch (e) {
  try { ({ chromium } = require(path.join(HERE, 'node_modules', 'playwright'))); } catch (e2) {
    console.error('[!!] Playwright is not installed.\n     fix: run `avs setup` (it runs npm install in the render folder and installs Chromium)');
    process.exit(2);
  }
}

const args = Object.fromEntries(process.argv.slice(2).reduce((a, v, i, all) => {
  if (v.startsWith('--')) a.push([v.slice(2), all[i + 1] && !all[i + 1].startsWith('--') ? all[i + 1] : true]);
  return a;
}, []));
const PROJECT = path.resolve(args.project || '.');
const MIME = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.mjs': 'text/javascript', '.css': 'text/css', '.json': 'application/json', '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
  '.webp': 'image/webp', '.woff2': 'font/woff2', '.woff': 'font/woff', '.svg': 'image/svg+xml', '.mp4': 'video/mp4', '.webm': 'video/webm' };

function serve() {
  return new Promise((resolve) => {
    const srv = http.createServer((req, res) => {
      let u = decodeURIComponent(req.url.split('?')[0]);
      let file;
      if (u.startsWith('/__kit/')) file = path.join(HERE, u.slice(7));
      else if (u.startsWith('/__fonts/')) file = path.join(ROOT, 'assets', 'fonts', u.slice(9));
      else file = path.join(PROJECT, u);
      const base = u.startsWith('/__kit/') ? HERE : u.startsWith('/__fonts/') ? path.join(ROOT, 'assets', 'fonts') : PROJECT;
      if (!path.resolve(file).startsWith(base)) { res.writeHead(403); return res.end(); }
      fs.readFile(file, (err, buf) => {
        if (err) { res.writeHead(404); return res.end('not found'); }
        res.writeHead(200, { 'Content-Type': MIME[path.extname(file).toLowerCase()] || 'application/octet-stream', 'Cache-Control': 'max-age=3600' });
        res.end(buf);
      });
    });
    srv.listen(0, '127.0.0.1', () => resolve(srv));
  });
}

async function openPage(browser, base, W, H, scale, query = '') {
  const ctx = await browser.newContext({ viewport: { width: W, height: H }, deviceScaleFactor: scale });
  const page = await ctx.newPage();
  page.on('pageerror', (e) => console.error('[page error]', e.message));
  page.on('console', (m) => { if (m.type() === 'error' || m.type() === 'warning') console.error('[page]', m.text()); });
  await page.goto(`${base}/comp/index.html${query}`, { waitUntil: 'load' });
  await page.evaluate(() => window.__ready);
  return page;
}

const LAUNCH = { args: ['--no-sandbox', '--force-color-profile=srgb', '--font-render-hinting=none', '--disable-lcd-text', '--hide-scrollbars', '--disable-gpu-vsync'] };

async function main() {
  const srv = await serve();
  const base = `http://127.0.0.1:${srv.address().port}`;
  const info = JSON.parse(fs.readFileSync(path.join(PROJECT, 'comp', 'resolved.json'), 'utf8')).meta;
  const W = +args.w || info.width, H = +args.h || info.height;
  const fps = +args.fps || info.fps;
  const scale = +args.scale || 1;

  if (args.cover) {
    const browser = await chromium.launch(LAUNCH);
    const page = await openPage(browser, base, W, H, 1, `?mode=cover&w=${W}&h=${H}&variant=${args.variant || 'hero'}`);
    await page.evaluate(() => window.__seek(0));
    await page.screenshot({ path: args.cover, type: 'png', clip: { x: 0, y: 0, width: W, height: H } });
    await browser.close(); srv.close(); return;
  }

  if (args.qa) {
    const browser = await chromium.launch(LAUNCH);
    const page = await openPage(browser, base, W, H, 1);
    const out = [];
    for (const t of String(args.qa).split(',').map(Number)) out.push(await page.evaluate((tt) => window.__qa(tt), t));
    console.log(JSON.stringify(out));
    await browser.close(); srv.close(); return;
  }

  const outDir = path.resolve(args.frames || path.join(PROJECT, 'out', 'frames'));
  fs.mkdirSync(outDir, { recursive: true });

  if (args.still) {
    const browser = await chromium.launch(LAUNCH);
    const page = await openPage(browser, base, W, H, scale);
    for (const t of String(args.still).split(',').map(Number)) {
      await page.evaluate((tt) => window.__seek(tt), t);
      const f = path.join(outDir, `still_${t.toFixed(2).padStart(6, '0')}.png`);
      await page.screenshot({ path: f, type: 'png', clip: { x: 0, y: 0, width: W, height: H } });
      console.log(f);
    }
    await browser.close(); srv.close(); return;
  }

  const t0 = +args.from || 0, t1 = Math.min(+args.to || info.duration, info.duration);
  const first = Math.round(t0 * fps), total = Math.max(1, Math.round((t1 - t0) * fps));
  const workers = Math.max(1, Math.min(+args.workers || Math.floor(os.cpus().length / 2) || 1, 6));
  const jpeg = args.png ? false : true;
  const quality = +args.quality || 94;
  let next = 0, done = 0; const CHUNK = 12; const t_start = Date.now();
  const lock = () => { const s = next; next += CHUNK; return s; };

  async function worker(k) {
    const browser = await chromium.launch(LAUNCH);
    const page = await openPage(browser, base, W, H, scale);
    for (;;) {
      const s = lock(); if (s >= total) break;
      for (let i = s; i < Math.min(s + CHUNK, total); i++) {
        const fr = first + i; const t = fr / fps;
        await page.evaluate((tt) => window.__seek(tt), t);
        const f = path.join(outDir, `f_${String(i + 1).padStart(6, '0')}.${jpeg ? 'jpg' : 'png'}`);
        await page.screenshot({ path: f, type: jpeg ? 'jpeg' : 'png', quality: jpeg ? quality : undefined, clip: { x: 0, y: 0, width: W, height: H } });
        done++;
        if (done % 60 === 0 || done === total) {
          const el = (Date.now() - t_start) / 1000; const eta = Math.round((el / done) * (total - done));
          console.log(`frames ${done}/${total}  (${Math.round((done / total) * 100)}%)  eta ${eta}s`);
        }
      }
    }
    await browser.close();
  }
  await Promise.all(Array.from({ length: workers }, (_, k) => worker(k)));
  console.log(`done ${total} frames`);
  srv.close();
}
main().catch((e) => { console.error('[!!] render failed:', e.message); process.exit(1); });
