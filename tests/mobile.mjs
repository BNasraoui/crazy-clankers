// Phone checks: drives a whole shift by touch in mobile emulation, checks the layout
// for overlaps at phone sizes, the rotate card, and that desktop/pad play is unchanged.
// Run Vite first (npx vite --port 5179). Usage: TMPDIR=<disk dir> node tests/mobile.mjs [url] [shots dir]
import assert from 'node:assert/strict';
import { mkdirSync } from 'node:fs';
import { chromium } from 'playwright';

const url = process.argv[2] ?? 'http://localhost:5179/';
const shots = process.argv[3] ?? `${process.env.TMPDIR ?? '/tmp'}/clankers-mobile`;
mkdirSync(shots, { recursive: true });
const browser = await chromium.launch({ headless: true, args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
const phone = (width, height) => ({ viewport: { width, height }, deviceScaleFactor: 3, isMobile: true, hasTouch: true,
  userAgent: 'Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1' });

async function open(opts) {
  const ctx = await browser.newContext(opts);
  const page = await ctx.newPage();
  page.on('pageerror', (e) => console.error('page error:', e.message));
  await page.route('https://www.youtube.com/**', (r) => r.abort());
  await page.goto(url);
  await page.waitForFunction(() => window.game, null, { timeout: 120000 });
  return { ctx, page };
}
const frames = (page, n) => page.evaluate((n) => new Promise((done) => { let i = 0; const f = () => (++i >= n ? done() : requestAnimationFrame(f)); requestAnimationFrame(f); }), n);
const state = (page) => page.evaluate(() => window.game.state);
const center = async (page, sel) => { const b = await page.locator(sel).first().boundingBox(); assert.ok(b, `${sel} is on screen`); return { x: b.x + b.width / 2, y: b.y + b.height / 2 }; };

// Raw multi-touch through CDP, so several fingers can be down at once.
async function fingers(page) {
  const cdp = await page.context().newCDPSession(page);
  const down = new Map();
  const send = (type) => cdp.send('Input.dispatchTouchEvent', { type, touchPoints: [...down.entries()].map(([id, p]) => ({ id, x: p.x, y: p.y, radiusX: 8, radiusY: 8, force: 1 })) });
  return {
    async down(id, p) { down.set(id, p); await send('touchStart'); },
    async move(id, p) { down.set(id, p); await send('touchMove'); },
    async up(id) {
      const p = down.get(id); down.delete(id);
      // touchEnd lifts the fingers it lists.
      await cdp.send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [{ id, x: p.x, y: p.y }] });
      return p;
    },
  };
}

// Pairs of visible boxes that overlap (ignoring hairline touches).
async function overlaps(page, sels) {
  const boxes = await page.evaluate((sels) => sels.flatMap((s) => [...document.querySelectorAll(s)].map((el) => {
    const r = el.getBoundingClientRect(), cs = getComputedStyle(el);
    const shown = r.width > 0 && el.checkVisibility?.() !== false && cs.visibility !== 'hidden';
    return shown ? { s, l: r.left, t: r.top, r: r.right, b: r.bottom } : null;
  }).filter(Boolean)), sels);
  const bad = [];
  for (let i = 0; i < boxes.length; i++) for (let j = i + 1; j < boxes.length; j++) {
    const a = boxes[i], b = boxes[j];
    const w = Math.min(a.r, b.r) - Math.max(a.l, b.l), h = Math.min(a.b, b.b) - Math.max(a.t, b.t);
    if (w > 2 && h > 2) bad.push(`${a.s} × ${b.s}`);
  }
  const off = boxes.filter((b) => b.s.startsWith('#')).filter((b) => b.l < -1 || b.t < -1 || b.r > innerW(page) + 1 || b.b > innerH(page) + 1).map((b) => `${b.s} off screen`);
  return [...bad, ...off];
}
const innerW = (page) => page.viewportSize().width, innerH = (page) => page.viewportSize().height;
const HUD = ['#clock', '#want', '#cash', '#rating', '#fare', '#quip', '#speed', '#launch', '#combo', '#radio-dashboard', '#radio-toast',
  '#touch .gas', '#touch .brake', '#touch .drift', '#touch .hop', '#touch .pause'];

// Everything that can be on screen while driving, all at once.
async function busyHud(page) {
  await page.evaluate(() => {
    const g = window.game;
    if (!g.ride) { const w = g.waiting[0]; g.pickup(w); }
    g.combo = 4;
    document.querySelector('#combo').textContent = 'x4 COMBO';
    document.querySelector('#launch').hidden = false;
    document.querySelector('#quip').classList.remove('hidden');
    document.querySelector('#quip .text').textContent = 'Could we go faster? I have a board meeting in nine minutes.';
    document.querySelector('#radio-toast').hidden = false;
    document.querySelector('#radio-toast').textContent = '📻 Clankers FM';
  });
  await frames(page, 2);
}

// ---------- a whole shift by touch, iPhone 15 landscape ----------
{
  const { ctx, page } = await open(phone(852, 393));
  const f = await fingers(page);
  assert.equal(await page.evaluate(() => document.documentElement.classList.contains('touch')), true, 'touch mode on a phone');
  await page.screenshot({ path: `${shots}/1-title.png` });
  await page.tap('.press-start', { force: true });
  await frames(page, 3);
  assert.equal(await state(page), 'picker', 'tap to start');
  await page.tap('.cab-row[data-cab="2"]');
  await frames(page, 3);
  assert.equal(await page.evaluate(() => window.game.cabIndex), 2, 'tap a cab row to select it');
  await page.screenshot({ path: `${shots}/2-picker.png` });
  await page.tap('.picker-screen .corner-back', { force: true });
  await frames(page, 3);
  assert.equal(await state(page), 'title', 'back from the picker');
  await page.tap('.press-start', { force: true }); await frames(page, 3);
  assert.equal(await state(page), 'picker', 'tap to start again');
  await page.tap('.confirm', { force: true }); await frames(page, 3);
  assert.equal(await state(page), 'play', 'DRIVE starts the shift');
  assert.equal(await page.locator('#touch .gas').isVisible(), true, 'driving controls shown');

  // Steer: thumb down on the left, drag right.
  await f.down(1, { x: 150, y: 300 });
  await f.move(1, { x: 215, y: 300 });
  await frames(page, 3);
  assert.ok(await page.evaluate(() => window.game.car.steerInput) > 0.9, 'drag right steers right');
  await f.move(1, { x: 120, y: 300 });
  await frames(page, 2);
  const left = await page.evaluate(() => window.game.car.steerInput);
  assert.ok(left < -0.3 && left > -0.7, `analog steer left (${left})`);
  await f.move(1, { x: 154, y: 300 });
  await frames(page, 2);
  assert.equal(await page.evaluate(() => window.game.car.steerInput), 0, 'dead zone');

  // Launch Mode from a standstill: hold DRIFT + GAS (with the steering thumb still down), let go of DRIFT.
  const gas = await center(page, '#touch .gas'), drift = await center(page, '#touch .drift'), hop = await center(page, '#touch .hop'), brake = await center(page, '#touch .brake');
  await f.down(3, drift);
  await f.down(2, gas);
  await frames(page, 30);
  const charge = await page.evaluate(() => window.game.car.launchCharge);
  assert.ok(charge > 0.3, `DRIFT + GAS charges Launch Mode (${charge.toFixed(2)} s)`);
  assert.equal(await page.locator('#touch .drift.down').count(), 1, 'press feedback');
  await page.screenshot({ path: `${shots}/x-launch.png` });
  const before = await page.evaluate(() => window.game.car.speed);
  await f.up(3);
  await frames(page, 2);
  const after = await page.evaluate(() => window.game.car.speed);
  assert.ok(after > before + 8, `releasing DRIFT launches (${before.toFixed(1)} → ${after.toFixed(1)} m/s)`);
  await f.up(1);
  // Keep the gas down.
  await frames(page, 20);
  assert.ok(await page.evaluate(() => window.game.car.speed) > 5, 'GAS keeps driving');
  await f.up(2);
  // Hop
  await frames(page, 20);
  await f.down(4, hop); await f.up(4);
  let airborne = false;
  for (let i = 0; i < 6 && !airborne; i++) { await frames(page, 1); airborne = await page.evaluate(() => !window.game.car.grounded); }
  assert.ok(airborne, 'HOP hops');
  // Brake / reverse
  await frames(page, 40);
  await f.down(5, brake);
  let reversing = false;
  for (let i = 0; i < 20 && !reversing; i++) { await frames(page, 10); reversing = await page.evaluate(() => window.game.car.forward < -0.5); }
  assert.ok(reversing, 'holding BRAKE stops, then reverses');
  await f.up(5);

  // Pickup: park next to a waiting fare.
  await page.evaluate(() => {
    const g = window.game, w = g.waiting[0];
    g.car.pos.set(w.curb.road.x, w.curb.road.y + 0.6, w.curb.road.z); g.car.vel.set(0, 0);
  });
  for (let i = 0; i < 20 && !(await page.evaluate(() => !!window.game.ride)); i++) await frames(page, 2);
  assert.ok(await page.evaluate(() => !!window.game.ride), 'stopping in a ring picks up');
  await frames(page, 25); // let the camera settle after the jump to the kerb
  await page.screenshot({ path: `${shots}/3-driving-passenger.png` });

  // Radio: tap = next station, hold = wheel.
  await page.waitForSelector('#radio-dashboard:not([hidden]) > b', { timeout: 10000 });
  const sticker = await center(page, '#radio-dashboard > b');
  const station = () => page.evaluate(() => document.querySelector('#radio-dashboard > b').textContent);
  const s0 = await station();
  await page.evaluate(() => { const r = window.game.radio; const next = r.nextStation.bind(r); window.__next = 0; r.nextStation = (d) => { window.__next++; next(d); }; });
  // Down and up between two frames: SwiftShader frames are so slow that waiting one would count as a hold.
  await f.down(6, sticker); await f.up(6); await frames(page, 3);
  assert.equal(await page.evaluate(() => window.__next), 1, 'tapping the sticker = next station');
  assert.equal(await page.locator('#radio-wheel').isVisible(), false, 'a tap does not open the wheel');
  assert.equal(await page.evaluate(() => document.querySelector('#radio-dashboard').classList.contains('mini')), true, 'and does not open the controls');
  const s1 = await station();
  await f.down(7, sticker);
  await page.waitForSelector('#radio-wheel:not([hidden])', { timeout: 20000 });
  const before2 = await page.evaluate(() => document.querySelector('#radio-wheel .slot.on').textContent);
  await f.move(7, { x: sticker.x + 70, y: sticker.y + 70 }); // drag down-right
  await frames(page, 3);
  const aimed = await page.evaluate(() => document.querySelector('#radio-wheel .slot.on').textContent);
  await page.screenshot({ path: `${shots}/4-radio-wheel.png` });
  await f.up(7);
  await frames(page, 3);
  assert.equal(await page.locator('#radio-wheel').isVisible(), false, 'release closes the wheel');
  console.log(`radio: ${s0} → tap → ${s1}; wheel ${before2} → aimed ${aimed} → now "${await station()}"`);
  assert.notEqual(aimed, before2, 'dragging aims the wheel');

  // Pause, resume, pause, main menu.
  await page.tap('#touch .pause', { force: true }); await frames(page, 3);
  assert.equal(await state(page), 'paused', 'pause button');
  await page.screenshot({ path: `${shots}/5-pause.png` });
  await page.tap('[data-tap="confirm"]'); await frames(page, 3);
  assert.equal(await state(page), 'play', 'RESUME');
  await page.tap('#touch .pause', { force: true }); await frames(page, 3);
  await page.tap('[data-tap="back"]'); await frames(page, 3);
  assert.equal(await state(page), 'title', 'MAIN MENU');

  // How to play and the game-over screen by tap.
  await page.tap('[data-tap="alt"]'); await frames(page, 2);
  assert.equal(await page.locator('.howto').isVisible(), true, 'HOW TO PLAY');
  await page.screenshot({ path: `${shots}/x-howto.png` });
  await page.tap('.howto', { force: true }); await frames(page, 2);
  assert.equal(await page.locator('.howto').count(), 0, 'tap closes how to play');
  await page.tap('.press-start', { force: true }); await frames(page, 2); await page.tap('.confirm', { force: true }); await frames(page, 2);
  await page.evaluate(() => { window.game.time = 0.01; }); await frames(page, 3);
  assert.equal(await state(page), 'over');
  await page.screenshot({ path: `${shots}/x-over.png` });
  await page.tap('[data-tap="back"]'); await frames(page, 2);
  assert.equal(await state(page), 'picker', 'CHANGE CAB');
  await page.tap('.confirm', { force: true }); await frames(page, 2);
  await page.evaluate(() => { window.game.time = 0.01; }); await frames(page, 3);
  await page.tap('[data-tap="confirm"]'); await frames(page, 2);
  assert.equal(await state(page), 'play', 'DRIVE AGAIN');

  assert.equal(await page.evaluate(() => !!document.fullscreenElement), true, 'the first touch went fullscreen');
  await page.evaluate(() => document.exitFullscreen());
  await frames(page, 2);
  // Upright: the rotate card, and the shift pauses.
  await page.setViewportSize({ width: 393, height: 852 });
  await frames(page, 3);
  assert.equal(await page.locator('#rotate').isVisible(), true, 'rotate card in portrait');
  assert.equal(await state(page), 'paused', 'turning upright pauses');
  await page.screenshot({ path: `${shots}/6-portrait.png` });
  await page.setViewportSize({ width: 852, height: 393 });
  await frames(page, 2);
  assert.equal(await page.locator('#rotate').isVisible(), false);

  // A pad takes over: touch controls hide.
  await page.evaluate(() => {
    const pad = { index: 0, connected: true, mapping: 'standard', id: 'Test pad', axes: [0, 0, 0, 0], buttons: Array.from({ length: 17 }, () => ({ pressed: false, value: 0 })) };
    pad.buttons[0] = { pressed: true, value: 1 };
    navigator.getGamepads = () => [pad];
  });
  await frames(page, 3);
  assert.equal(await page.evaluate(() => document.documentElement.classList.contains('touch')), false, 'a pad turns touch mode off');
  assert.equal(await page.locator('#touch').isVisible(), false);
  const look = await page.evaluate(() => window.game.look.settings.height);
  assert.equal(look, 480, 'phones default to 480p');
  await ctx.close();
}

// ---------- layout: nothing overlaps at phone sizes ----------
for (const [w, h] of [[852, 393], [740, 360]]) {
  const { ctx, page } = await open(phone(w, h));
  const toast = () => page.evaluate(() => { const t = document.querySelector('#radio-toast'); t.hidden = false; t.textContent = '📻 Punk\'s Not Dead'; });
  await toast();
  await page.screenshot({ path: `${shots}/title-${w}x${h}.png` });
  const titleBad = await overlaps(page, ['.press-start', '.title-screen .tap-btn', '.title-screen .radio-menu-button', '.logo-block', '#radio-dashboard', '#radio-toast']);
  await page.tap('.press-start', { force: true }); await frames(page, 2);
  await toast();
  await page.screenshot({ path: `${shots}/picker-${w}x${h}.png` });
  const pickerBad = [...titleBad, ...await overlaps(page, ['.picker-panel', '.picker-screen .corner-back', '.logo-block', '#radio-dashboard', '#radio-toast'])];
  await page.tap('.confirm', { force: true }); await frames(page, 2);
  await busyHud(page);
  await page.screenshot({ path: `${shots}/hud-${w}x${h}.png` });
  const bad = await overlaps(page, HUD);
  console.log(`${w}x${h}: ${bad.length + pickerBad.length ? 'OVERLAPS ' + [...bad, ...pickerBad].join(', ') : 'no overlaps'}`);
  assert.deepEqual([...bad, ...pickerBad], [], `no overlaps at ${w}x${h}`);
  await ctx.close();
}

// ---------- desktop: no touch UI, same HUD ----------
{
  const { ctx, page } = await open({ viewport: { width: 1280, height: 800 } });
  assert.equal(await page.evaluate(() => document.documentElement.classList.contains('touch')), false, 'no touch mode on desktop');
  assert.equal(await page.locator('.press-start .pad-only').isVisible(), true);
  await page.keyboard.press('Enter'); await frames(page, 2); await page.keyboard.press('Enter'); await frames(page, 2);
  assert.equal(await state(page), 'play', 'keyboard still starts');
  assert.equal(await page.locator('#touch').isVisible(), false, 'no touch controls on desktop');
  await busyHud(page);
  const rects = await page.evaluate((sels) => Object.fromEntries(sels.map((s) => { const r = document.querySelector(s)?.getBoundingClientRect(); return [s, r ? [r.x, r.y, r.width, r.height].map(Math.round) : null]; })), HUD.slice(0, 11));
  console.log('desktop HUD rects', JSON.stringify(rects));
  assert.equal(await page.evaluate(() => window.game.look.settings.height), 720, 'desktop keeps 720p');
  await page.screenshot({ path: `${shots}/desktop-hud.png` });
  await ctx.close();
}
await browser.close();
console.log('mobile checks passed; screenshots in', shots);
