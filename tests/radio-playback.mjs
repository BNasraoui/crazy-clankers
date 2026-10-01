// A fake IFrame API isolates our lifecycle/error handling from YouTube and autoplay policy.
import assert from 'node:assert/strict';
import { chromium } from 'playwright';
const browser = await chromium.launch({ headless: true });
try {
  const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
  await page.route('**/radio-harness', r => r.fulfill({ contentType: 'text/html', body: '<html><head><link rel="stylesheet" href="/src/style.css"></head><body><button data-radio-open>Radio</button></body></html>' }));
  await page.goto('http://localhost:5173/radio-harness');
  await page.evaluate(async () => {
    window.players = [];
    window.YT = { Player: class {
      constructor(mount, options) {
        this.options = options; this.index = 0; this.list = []; this.calls = [];
        this.iframe = document.createElement('iframe'); mount.replaceWith(this.iframe);
        window.players.push(this);
        queueMicrotask(() => options.events.onReady({ target: this }));
      }
      cueVideoById(id) { this.video = id; this.list = []; queueMicrotask(() => this.options.events.onStateChange({ data: 5 })); }
      cuePlaylist() { this.list = ['aaaaaaaaaaa', 'bbbbbbbbbbb']; queueMicrotask(() => this.options.events.onStateChange({ data: 5 })); }
      playVideo() { this.calls.push('play'); this.options.events.onStateChange({ data: 1 }); }
      pauseVideo() { this.calls.push('pause'); this.options.events.onStateChange({ data: 2 }); }
      playVideoAt(i) { this.index = i; this.playVideo(); }
      nextVideo() { this.index = (this.index + 1) % this.list.length; this.calls.push('next'); }
      setShuffle(value) { this.shuffled = value; }
      setLoop() {}
      setVolume(value) { this.volume = value; }
      getPlaylist() { return this.list; }
      getPlaylistIndex() { return this.index; }
      getVideoData() { return { title: 'Test track', video_id: this.video }; }
      destroy() { this.destroyed = true; this.iframe.remove(); }
    }};
    const { Radio, youtubeSource } = await import('/tests/radio-fixture.ts');
    window.parse = youtubeSource;
    window.radio = new Radio();
  });
  assert.equal(await page.locator('iframe').count(), 0, 'no player on page load');
  for (const [source, kind] of [['K4DyBUG242c', 'video'], ['https://youtu.be/K4DyBUG242c?t=5', 'video'], ['https://www.youtube.com/shorts/K4DyBUG242c', 'video'], ['https://www.youtube.com/watch?v=K4DyBUG242c&list=PLabcdefghijklmnop', 'playlist']]) {
    assert.equal(await page.evaluate(s => window.parse(s)?.kind, source), kind);
  }
  assert.equal(await page.evaluate(() => window.parse('https://evil.example/watch?v=K4DyBUG242c')), null);
  await page.getByRole('button', { name: 'Radio', exact: true }).click();
  await page.waitForFunction(() => window.players.length === 1);
  await page.getByRole('button', { name: 'Off / collapse' }).click();
  await page.evaluate(() => { window.players = []; });
  await page.getByLabel('YouTube URL or ID').fill('PLabcdefghijklmnop');
  await page.getByLabel('Station name (optional)').fill('Playlist');
  await page.getByRole('button', { name: 'Add station' }).click();
  await page.getByRole('button', { name: 'Tune Playlist' }).click();
  await page.waitForFunction(() => window.players.at(-1)?.shuffled);
  const box = await page.locator('iframe').boundingBox();
  assert.ok(box.width >= 200 && box.height >= 200);
  assert.equal(await page.locator('.radio-track').textContent(), 'Test track');
  await page.getByRole('button', { name: 'Pause', exact: true }).click();
  assert.equal(await page.evaluate(() => window.players.at(-1).calls.at(-1)), 'pause');
  await page.getByRole('button', { name: 'Play', exact: true }).click();
  await page.evaluate(async () => {
    const { babble } = await import('/tests/radio-fixture.ts'); babble('hello passenger', 300);
    window.radio.frame({}, 'play');
  });
  assert.ok(await page.evaluate(() => window.players.at(-1).volume < 35), 'quips duck volume');
  await page.evaluate(() => window.players.at(-1).options.events.onError({ data: 101 }));
  await page.waitForFunction(() => window.players.at(-1).calls.includes('next'));
  await page.evaluate(() => window.players.at(-1).options.events.onError({ data: 150 }));
  await page.waitForFunction(() => window.players.length === 2);
  assert.equal(await page.evaluate(() => window.players[0].destroyed), true);
  await page.evaluate(() => window.players.at(-1).options.events.onError({ data: 100 }));
  await page.waitForFunction(() => window.players.length === 3);
  await page.evaluate(() => window.players.at(-1).options.events.onError({ data: 2 }));
  assert.equal(await page.locator('#radio-dashboard').isVisible(), false, 'all stations failing stops bounded fallback');
  // A stale callback after Off must not restart playback or create a hidden iframe.
  await page.getByRole('button', { name: 'Tune Playlist' }).click();
  await page.waitForFunction(() => window.players.length === 4);
  await page.getByRole('button', { name: 'Off / collapse' }).click();
  await page.evaluate(() => window.players.at(-1).options.events.onStateChange({ data: 5 }));
  assert.equal(await page.locator('iframe').count(), 0);
  // Local playback uses blob URLs, and editing YouTube stations must not change its identity.
  const wav = Buffer.alloc(44 + 8000 * 2);
  wav.write('RIFF'); wav.writeUInt32LE(wav.length - 8, 4); wav.write('WAVEfmt ', 8); wav.writeUInt32LE(16, 16);
  wav.writeUInt16LE(1, 20); wav.writeUInt16LE(1, 22); wav.writeUInt32LE(8000, 24); wav.writeUInt32LE(16000, 28);
  wav.writeUInt16LE(2, 32); wav.writeUInt16LE(16, 34); wav.write('data', 36); wav.writeUInt32LE(wav.length - 44, 40);
  const chooser = page.waitForEvent('filechooser');
  await page.getByRole('button', { name: 'Play my own files', exact: true }).click();
  await (await chooser).setFiles([{ name: 'local.wav', mimeType: 'audio/wav', buffer: wav }]);
  await page.waitForFunction(() => document.querySelector('.radio-track').textContent === 'local.wav');
  await page.getByLabel('YouTube URL or ID').fill('K4DyBUG242c');
  await page.getByRole('button', { name: 'Add station' }).click();
  await page.getByRole('button', { name: 'Skip ▶', exact: true }).click();
  assert.equal(await page.locator('.radio-track').textContent(), 'local.wav', 'adding station preserves active local source');
  await page.getByRole('button', { name: 'Station ▶', exact: true }).click();
  assert.equal(await page.locator('#radio-dashboard > b').textContent(), 'NCS · On & On', 'local station stays last after adding a station');
  assert.equal(await page.locator('#radio-screen').getByRole('button', { name: 'Radio off', exact: true }).count(), 1, 'controller menu can switch radio off');
  await page.screenshot({ path: '/tmp/clankers-radio/playback.png' });
  await page.getByRole('button', { name: 'Tune Playlist' }).click();
  await page.evaluate(() => {
    window.stuckPlayer = window.players.at(-1);
    window.stuckPlayer.nextVideo = () => {};
    window.stuckPlayer.options.events.onError({ data: 5 });
  });
  await page.evaluate(() => window.stuckPlayer.options.events.onError({ data: 101 }));
  assert.equal(await page.evaluate(() => window.stuckPlayer.destroyed), true, 'a stuck playlist index cannot retry forever');
  await page.getByRole('button', { name: 'Tune Playlist' }).click();
  await page.getByRole('button', { name: 'Pause', exact: true }).click();
  const pausedCount = await page.evaluate(() => window.players.length);
  await page.evaluate(() => window.players.at(-1).options.events.onError({ data: 5 }));
  await page.evaluate(() => window.players.at(-1).options.events.onError({ data: 5 }));
  assert.equal(await page.evaluate(() => window.players.length), pausedCount, 'errors after pause must not start a new station');
  console.log('Radio playback: URLs, gesture, shuffle, dimensions, pause, ducking, errors, cancellation, local files passed');
} finally { await browser.close(); }
