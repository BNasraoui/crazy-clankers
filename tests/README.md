Radio browser checks (run Vite in another terminal with `npm run dev`):

```sh
mkdir -p /tmp/clankers-radio
TMPDIR=/tmp/clankers-radio node tests/radio.mjs
TMPDIR=/tmp/clankers-radio node tests/radio-playback.mjs
TMPDIR=/tmp/clankers-radio node tests/radio-input.mjs
```

`radio.mjs` runs the actual game at 1280×800 and waits only for `window.game` to initialize. It checks title/pause navigation and station CRUD/persistence; YouTube requests are blocked. Screenshots go to `/tmp/clankers-radio`.

The playback harness uses the real Radio class with a fake YouTube IFrame API to exercise playlist shuffle, error recovery (including a stuck index), visibility/teardown, pause, quip ducking, local WAV playback, and station edits during local playback. The input harness checks blocked localStorage and standard/unmapped controller bindings.

Actual YouTube playback, browser autoplay policies and the Steam Deck system file chooser still need an interactive browser/device check. The game displays an explicit Play prompt when autoplay is blocked. No test downloads music.
