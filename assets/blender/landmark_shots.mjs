// In-game screenshots of the landmarks, to docs/renders/landmark-game-<name>.png.
//   npx vite --port 5181 &   then   TMPDIR=<dir on disk> node assets/blender/landmark_shots.mjs [port] [name...]
// Needs playwright (npx playwright install chromium). Set TMPDIR to a disk folder: a full /tmp breaks headless Chrome.
import { chromium } from 'playwright';
const port = process.argv[2] ?? 5181;
const only = process.argv.slice(3);
const browser = await chromium.launch({ args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
const page = await browser.newPage({ viewport: { width: 1280, height: 720 } });
const errors = [];
page.on('pageerror', e => errors.push('PAGEERROR ' + e.message));
page.on('console', m => { if (m.type() === 'error' && !m.text().includes('INSUFFICIENT')) errors.push(m.text().slice(0, 200)); });
await page.goto(`http://localhost:${port}/`);
await page.waitForFunction(() => window.game, null, { timeout: 180000 });
await page.waitForTimeout(4000);
const shots = [ // [name, camera (y is above the ground there), look-at (y above the same ground)]
  ['city_hall', [70, 9, 22], [30, 16, -32]],
  ['dragon_gate', [131, 3, -134], [128, 6, -160]],
  ['palace_of_fine_arts', [-238, 9, -262], [-292, 6, -288]],
  ['lombard_street', [-200, 6, -266], [-150, 14, -256]],
  ['alcatraz', [222, 30, -378], [150, 18, -440]],
];
for (const [name, pos, look] of shots) {
  if (only.length && !only.includes(name)) continue;
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
  await page.screenshot({ path: `docs/renders/landmark-game-${name}.png`, timeout: 120000 });
  console.log('shot', name);
}
console.log('errors', JSON.stringify(errors.slice(0, 5)));
await browser.close();
