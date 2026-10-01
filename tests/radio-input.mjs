import assert from 'node:assert/strict';
import { chromium } from 'playwright';
const browser = await chromium.launch({ headless: true });
try {
  const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
  await page.route('**/radio-harness', r => r.fulfill({ contentType: 'text/html', body: '<html><body></body></html>' }));
  await page.route('https://www.youtube.com/**', r => r.abort());
  await page.goto('http://localhost:5173/radio-harness');
  await page.evaluate(async () => {
    Storage.prototype.getItem = Storage.prototype.setItem = () => { throw new Error('Storage blocked'); };
    const { Radio, readInput } = await import('/tests/radio-fixture.ts');
    window.radio = new Radio(); window.readInput = readInput;
    window.pad = { index: 0, connected: true, mapping: 'standard', id: 'Test pad', axes: [0, 0, 0, 0], buttons: Array.from({ length: 17 }, () => ({ pressed: false, value: 0 })) };
    navigator.getGamepads = () => [window.pad];
  });
  const press = async (index, state = 'title') => page.evaluate(({ index, state }) => {
    window.pad.buttons.forEach(b => { b.pressed = false; }); window.readInput(.016);
    window.pad.buttons[index].pressed = true;
    const input = window.readInput(.016);
    const consumed = window.radio.frame(input, state);
    return { input, consumed };
  }, { index, state });
  assert.equal((await press(2)).consumed, true, 'X opens Radio from title');
  assert.equal(await page.locator('#radio-screen').isVisible(), true);
  await page.getByLabel('YouTube URL or ID').fill('K4DyBUG242c');
  await page.getByRole('button', { name: 'Add station', exact: true }).click();
  assert.equal(await page.locator('.radio-station').count(), 3, 'station edits work with storage blocked');
  const volume = page.locator('#radio-screen').getByLabel('Radio volume');
  await volume.focus();
  await press(15);
  assert.equal(await volume.inputValue(), '40', 'D-pad adjusts focused volume');
  await page.locator('#radio-screen').getByRole('button', { name: 'Radio off', exact: true }).focus();
  await press(0);
  assert.equal(await page.locator('#radio-dashboard').isVisible(), false, 'A activates radio off');
  await press(1);
  assert.equal(await page.locator('#radio-screen').isVisible(), false, 'B returns to game');
  const lb = await press(4, 'play');
  assert.equal(lb.input.radioNext, true); assert.equal(lb.input.handbrake, false);
  assert.equal(await page.evaluate(() => window.readInput(.016).radioNext), false, 'held LB does not repeat');
  const x = await press(2, 'play'); assert.equal(x.input.radioSkip, true); assert.equal(x.input.hop, false);
  await page.evaluate(() => { window.pad.mapping = ''; window.pad.axes = [0, 0, -1, 0, 0, -1, 0, 0]; });
  assert.equal((await press(4, 'play')).input.radioNext, true, 'unmapped Steam controller LB works');
  assert.equal((await press(2, 'play')).input.radioSkip, true, 'unmapped Steam controller X works');
  assert.equal(await page.locator('script[src="https://www.youtube.com/iframe_api"]').count(), 1, 'YouTube API is loaded once across station changes');
  console.log('Radio input: blocked storage, standard/unmapped pads, focus, volume, off, back, edge detection passed');
} finally { await browser.close(); }
