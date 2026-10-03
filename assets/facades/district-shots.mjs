// Screenshots of each district's houses (and downtown towers) from the middle of the street.
//   npx vite --port 5181 &   then   TMPDIR=<dir on disk> node assets/facades/district-shots.mjs <outdir> [port]
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
// Block (bi, bj) spans x = -320 + 64 bi .. +64 (same for z with bj); streets run on the block edges.
const street = (bi, bj, dy = 6, back = 26) => { // stand on the street north of the block, looking along its north face
  const x = -320 + 64 * bi + 32, z = -320 + 64 * bj;
  return [[x - back, 2, z - 1], [x + 6, dy, z + 12]];
};
const shots = [ // [name, camera (y is above the ground), look-at]
  ['haight', ...street(3, 4)],
  ['pacheights', ...street(1, 3)],
  ['northbeach', ...street(3, 1)],
  ['nob', ...street(5, 2, 14)],
  ['soma', ...street(7, 5, 9)],
  ['mission', ...street(4, 7)],
  ['sunset', ...street(1, 6)],
  ['potrero', ...street(7, 8)],
  ['fidi', ...street(8, 2, 20, 45)],
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
