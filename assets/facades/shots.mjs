// Screenshots of every drop-off building from across the street.
//   npx vite --port 5181 &   then   TMPDIR=<dir on disk> node assets/facades/shots.mjs <outdir> [port]
// Needs playwright (npx playwright install chromium). Set TMPDIR to a disk folder: a full /tmp breaks headless Chrome.
import { chromium } from 'playwright';
const S = process.argv[2];
const browser = await chromium.launch({ args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
const errors = [];
page.on('pageerror', e => errors.push('PAGEERROR ' + e.message));
page.on('console', m => { if (m.type() === 'error' && !m.text().includes('INSUFFICIENT')) errors.push(m.text().slice(0, 200)); });
await page.goto(`http://localhost:${process.argv[3] ?? 5181}/`);
await page.waitForFunction(() => window.game, null, { timeout: 180000 });
await page.waitForTimeout(3000);
const shots = [ // [name, camera (y is above the ground), look-at]
  ['phlz', [25.6, 2, -140], [25.6, 6, -116]],
  ['barris', [140, 2, 99], [116, 6, 99]],
  ['seriesa', [166, 2, -54], [166, 7, -76]],
  ['lab', [136, 2, -35], [116, 6, -35]],
  ['crypto', [224, 2, 56], [224, 8, 76]],
  ['burrito', [-56, 2, 96], [-76, 6, 96]],
  ['ladies-park', [-14, 2.5, 34], [12, 8, 22]],
  ['ladies-north', [29, 2, -6], [29, 8, 12]],
];
for (const [name, pos, look] of shots) {
  await page.evaluate(([pos, look]) => {
    const g = window.game; g.renderer.setAnimationLoop(null);
    document.getElementById('overlay').innerHTML = ''; document.getElementById('hud').style.display = 'none';
    g.camera.fov = 60; g.camera.updateProjectionMatrix();
    g.car.reset(pos[0], pos[2], 0);
    const y = g.car.pos.y;
    g.camera.position.set(pos[0], y + pos[1], pos[2]);
    g.camera.lookAt(look[0], y + look[1], look[2]);
    g.camera.updateMatrixWorld();
    g.sky.position.copy(g.camera.position); if (g.sky.children[0]) g.sky.children[0].position.y = -2 - g.camera.position.y;
    g.look.render(g.scene, g.camera, 1, 0);
  }, [pos, look]);
  await page.screenshot({ path: `${S}/${name}.png`, timeout: 120000 });
}
console.log('errors', JSON.stringify(errors.slice(0, 5)));
await browser.close();
