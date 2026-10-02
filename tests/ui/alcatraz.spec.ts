import { test, expect } from '@playwright/test';

// The Alcatraz Express (features.ts): every cab, from anywhere across the street and a little
// off-line, flat out with no steering, must land on the island and still be on it at the end
// (the tyre wall stops it). The physics runs in the page at a fixed step, so this is exact.

test('every cab makes the Alcatraz jump', async ({ page }) => {
  test.skip(test.info().project.name !== 'laptop-1366x768', 'physics, not layout: one size is enough');
  await page.goto('/?still');
  await page.waitForFunction(() => (window as unknown as { still?: unknown }).still, null, { timeout: 170_000 });
  const misses = await page.evaluate(() => {
    type Car = { reset(x: number, z: number, yaw: number): void; step(dt: number, inp: object): { landed: number }; pos: { x: number; y: number; z: number } };
    const g = (window as unknown as { game: { chooseCab(i: number): void; car: Car } }).game;
    const input = { throttle: 1, brake: 0, steer: 0, handbrake: false, confirm: false, pause: false, restart: false, debug: false, hop: false, navX: 0, navY: 0, back: false, alt: false, board: false, lookX: 0, select: -1, radioNext: false, radioSkip: false, radioMenu: false, radioHold: false, aimX: 0, aimY: 0, padConfirm: false };
    const out: string[] = [];
    for (let cab = 0; cab < 4; cab++) {
      g.chooseCab(cab);
      // Across the street (x 186..198), heading north or up to ~6 degrees off towards the pier.
      for (const x of [188, 192, 196]) for (const off of [0, -0.1]) {
        const car = g.car;
        car.reset(x, -300, Math.PI - off);
        let landed = false;
        for (let t = 0; t < 9; t += 1 / 120) if (car.step(1 / 120, input).landed > 0.5) landed = true;
        if (!landed || car.pos.y < 4) out.push(`cab ${cab} from x ${x}, ${off} rad: ended at ${car.pos.x.toFixed(1)}, ${car.pos.y.toFixed(1)}, ${car.pos.z.toFixed(1)}`);
      }
    }
    return out;
  });
  expect(misses).toEqual([]);
});
