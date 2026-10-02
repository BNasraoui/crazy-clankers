import { test, expect } from '@playwright/test';

// The 3D world, frozen: guards the look of the city when its rendering changes (fewer triangles,
// simpler far buildings, fewer draw calls should all look the same). ?still stops the game loop,
// waits for every drawing, model and sprite, and renders one frame at a fixed time from a camera
// the test places (main.ts). The UI is hidden; screens.spec.ts covers it. One screen size is
// enough here, and Math.random is seeded so traffic and passengers stand in the same places.

const SEED = `(() => {
  let a = 1234567;
  Math.random = () => { a = (a + 0x6d2b79f5) | 0; let t = Math.imul(a ^ (a >>> 15), 1 | a); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
  try { localStorage.clear(); } catch { /* fine */ }
})();`;

type V = [number, number, number];
// Views around where the shift starts, as [eye offset, target offset] from the cab.
const VIEWS: Record<string, [V, V]> = {
  rank: [[-2, 7, 24], [0, 1, 0]],
  street: [[0, 3, -9], [0, 2, 30]],
  overview: [[70, 80, 70], [0, 0, 0]],
  skyline: [[0, 30, 0], [-200, 20, -200]],
};

test.describe('world', () => {
  test.beforeEach(() => test.skip(test.info().project.name !== 'laptop-1366x768', 'one size is enough for the 3D view'));

  for (const [name, [eye, target]] of Object.entries(VIEWS)) {
    test(name, async ({ page }) => {
      await page.addInitScript(SEED);
      await page.goto('/?still');
      await page.waitForFunction(() => (window as unknown as { still?: unknown }).still, null, { timeout: 170_000 });
      await page.addStyleTag({ content: '#overlay, #hud, #radio-dashboard, #radio-collapsed, #radio-toast, #touch, #quip, #popups { visibility: hidden !important; }' });
      await page.evaluate(([eye, target]) => {
        type Fare = { person: { root: { visible: boolean } }; marker: { visible: boolean } };
        const w = window as unknown as { game: { car: { pos: { x: number; y: number; z: number } }; waiting: Fare[] }; still: (e: V, t: V) => void };
        // Waiting fares depend on how the boot went; these views are about the city.
        for (const f of w.game.waiting) f.person.root.visible = f.marker.visible = false;
        const c = w.game.car.pos;
        w.still([c.x + eye[0], c.y + eye[1], c.z + eye[2]], [c.x + target[0], c.y + target[1], c.z + target[2]]);
      }, [eye, target] as [V, V]);
      // The 3D view changes a little between GPUs and drivers; CI renders in software, the same way every run.
      await expect(page).toHaveScreenshot(`world-${name}.png`, { maxDiffPixelRatio: 0.02 });
    });
  }
});
