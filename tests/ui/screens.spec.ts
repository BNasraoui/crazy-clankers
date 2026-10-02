import { test, expect, type Page } from '@playwright/test';

// Every screen at every size (playwright.config.ts projects):
//  1. layout checks: the things you need to read or press are fully on screen, and the HUD
//     doesn't sit under the touch buttons (exact, never flaky);
//  2. a snapshot of the interface with the 3D view hidden, compared with the approved image.
// Math.random is seeded, so passengers, names and positions are the same on every run.

const SEED = `(() => {
  let a = 1234567;
  Math.random = () => { a = (a + 0x6d2b79f5) | 0; let t = Math.imul(a ^ (a >>> 15), 1 | a); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
  try { localStorage.clear(); } catch { /* fine */ }
})();`;

// Hide the 3D view and anything that changes by itself, so snapshots only compare the interface.
const STILL = `
  #view { visibility: hidden !important; }
  html, body { background: #4a5568 !important; }
  *, *::before, *::after { animation: none !important; transition: none !important; caret-color: transparent !important; }
  #radio-dashboard, #radio-collapsed, #radio-toast, #radio-wheel, #popups, #moment, #stamp, #lookpanel { visibility: hidden !important; }`;

type G = Record<string, any>;

async function boot(page: Page) {
  await page.addInitScript(SEED);
  await page.goto('/');
  await page.waitForFunction(() => (window as unknown as G).game, null, { timeout: 150_000 });
  await page.evaluate(() => (window as unknown as G).game.renderer.setAnimationLoop(null)); // freeze the world
  await page.addStyleTag({ content: STILL });
  await page.evaluate(() => document.fonts.ready);
}

// Elements (visible ones only) that stick out past the screen edges.
async function offscreen(page: Page, selectors: string[]) {
  return page.evaluate((sels) => {
    const out: string[] = [];
    for (const sel of sels) for (const e of document.querySelectorAll(sel)) {
      if (!(e as HTMLElement).checkVisibility?.({ visibilityProperty: true, opacityProperty: true })) continue;
      const r = e.getBoundingClientRect();
      if (r.width === 0 || r.height === 0) continue;
      if (r.left < -2 || r.top < -2 || r.right > innerWidth + 2 || r.bottom > innerHeight + 2)
        out.push(`${sel} at ${Math.round(r.left)},${Math.round(r.top)} to ${Math.round(r.right)},${Math.round(r.bottom)}`);
    }
    return out;
  }, selectors);
}

// Pairs of visible elements whose boxes overlap.
async function overlaps(page: Page, a: string, b: string) {
  return page.evaluate(([a, b]) => {
    const vis = (s: string) => [...document.querySelectorAll(s)].filter((e) => (e as HTMLElement).checkVisibility?.({ visibilityProperty: true }));
    const out: string[] = [];
    for (const x of vis(a)) for (const y of vis(b)) {
      const p = x.getBoundingClientRect(), q = y.getBoundingClientRect();
      if (p.left < q.right - 2 && q.left < p.right - 2 && p.top < q.bottom - 2 && q.top < p.bottom - 2) out.push(`${a} over ${b}`);
    }
    return out;
  }, [a, b]);
}

const shot = (page: Page, name: string) => expect(page).toHaveScreenshot(`${name}.png`, { fullPage: false });

test('title', async ({ page }) => {
  await boot(page);
  expect(await offscreen(page, ['.press-start', '.logo-block', '.corner-prompts', '.radio-menu-button'])).toEqual([]);
  await shot(page, 'title');
});

for (const cab of [0, 3]) {
  test(`picker, cab ${cab}`, async ({ page }) => {
    await boot(page);
    await page.evaluate((c) => { const g = (window as unknown as G).game; g.chooseCab(c); g.showPicker(); }, cab);
    expect(await offscreen(page, ['.picker-panel h2', '.cab-row', '.confirm', '.prompt-strip', '.corner-back'])).toEqual([]);
    // Nothing squeezed: the stat bars (when shown) and the cab list fit without hiding anything.
    const squeeze = await page.evaluate(() => {
      const list = document.querySelector('.cab-list')!, stats = document.querySelector('.stats') as HTMLElement;
      return { list: list.scrollHeight - list.clientHeight, stats: getComputedStyle(stats).display === 'none' ? 0 : stats.scrollHeight - stats.clientHeight };
    });
    expect(squeeze.list, 'cab list hides a cab').toBeLessThanOrEqual(8);
    expect(squeeze.stats, 'stat bars squeezed').toBeLessThanOrEqual(4);
    await shot(page, `picker-${cab}`);
  });
}

test('driving with a passenger', async ({ page }) => {
  await boot(page);
  await page.evaluate(() => { const g = (window as unknown as G).game; g.start(); g.pickup(g.waiting[0]); g.updateHud(); });
  expect(await offscreen(page, ['#clock', '#want', '#fare', '#cash', '#rating', '#touch .tb'])).toEqual([]);
  for (const hud of ['#rating', '#cash', '#want', '#clock', '#fare']) expect(await overlaps(page, hud, '#touch .tb')).toEqual([]);
  expect(await overlaps(page, '#want', '#fare')).toEqual([]);
  await shot(page, 'driving');
});

test('pause', async ({ page }) => {
  await boot(page);
  await page.evaluate(() => { const g = (window as unknown as G).game; g.start(); g.setState('paused'); });
  expect(await offscreen(page, ['#overlay h2', '#overlay .press', '#overlay .tap-btn', '#overlay .radio-menu-button'])).toEqual([]);
  await shot(page, 'pause');
});

test('results', async ({ page }) => {
  await boot(page);
  await page.evaluate(() => { const g = (window as unknown as G).game; g.start(); g.gameOver('TIME UP'); });
  expect(await offscreen(page, ['#overlay h2', '#overlay .stats', '#overlay .press', '#overlay .tap-btn'])).toEqual([]);
  await shot(page, 'results');
});
