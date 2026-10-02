// Frame time in phone emulation (SwiftShader, so compare runs, not absolute numbers).
// Run Vite first: npx vite --port 5179. Usage: TMPDIR=<disk dir> node tests/mobile-perf.mjs [url]
import { chromium, devices } from 'playwright';
const url = process.argv[2] ?? 'http://localhost:5179/';
const browser = await chromium.launch({ headless: true, args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
const runs = [
  ['iPhone 15 landscape', { ...devices['iPhone 15 landscape'] }],
  ['Pixel 7 landscape', { ...devices['Pixel 7 landscape'] }],
  ['desktop 1280x800', { viewport: { width: 1280, height: 800 } }],
];
for (const [name, opts] of runs) {
  const ctx = await browser.newContext(opts);
  const page = await ctx.newPage();
  await page.route('https://www.youtube.com/**', (r) => r.abort());
  await page.goto(url);
  await page.waitForFunction(() => window.game, null, { timeout: 120000 });
  await page.evaluate(() => { const g = window.game; g.showPicker?.(); g.start?.(); });
  await page.waitForTimeout(1500);
  const r = await page.evaluate(() => new Promise((done) => {
    const t = []; let last = performance.now();
    const tick = (now) => { t.push(now - last); last = now; if (t.length < 90) requestAnimationFrame(tick); else done(t); };
    requestAnimationFrame(tick);
  }));
  r.sort((a, b) => a - b);
  const info = await page.evaluate(() => ({ dpr: devicePixelRatio, w: innerWidth, h: innerHeight, buf: [document.getElementById('view').width, document.getElementById('view').height], state: window.game.state }));
  console.log(`${name}: median ${r[45].toFixed(1)} ms, p90 ${r[81].toFixed(1)} ms`, JSON.stringify(info));
  await ctx.close();
}
await browser.close();
