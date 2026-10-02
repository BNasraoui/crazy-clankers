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

Phone checks (Vite on port 5179: `npx vite --port 5179`; set TMPDIR to a folder on disk, a full /tmp breaks headless Chrome):

```sh
TMPDIR=$HOME/.cache/clankers-tmp node tests/mobile.mjs   # a whole shift by touch, layout overlaps, rotate card, desktop/pad unchanged
TMPDIR=$HOME/.cache/clankers-tmp node tests/mobile-perf.mjs   # frame time in phone emulation
```

`mobile.mjs` emulates an iPhone 15 on its side (852×393, touch) and drives the game with real multi-touch through CDP: title → picker (tap a cab, back, drive) → steer, Launch Mode (DRIFT + GAS, let go of DRIFT), gas, hop, brake/reverse → pickup → radio sticker tap and hold-drag-release → pause / resume / main menu → how to play → game over → portrait. It then checks for overlapping HUD panels and touch buttons at 852×393 and 740×360, and that 1280×800 has no touch UI. Screenshots go to `$TMPDIR/clankers-mobile` (or the second argument). SwiftShader runs at about two frames a second, so the run takes a few minutes and the perf numbers are only good for before/after comparisons.

## UI tests (CI)

`npx playwright test` runs tests/ui/screens.spec.ts at six sizes (Steam Deck 1280x800, laptops 1000x532 and 1366x768, desktop 1920x1080, phones 780x300 and 915x412): title, picker (two cabs), driving with a passenger, pause and results. Each screen gets exact layout checks (what you must read or press is on screen; the HUD isn't under the touch buttons; the picker isn't squeezed) and a snapshot of the interface with the 3D view hidden. Math.random is seeded, so every run is the same.

GitHub Actions runs them on every PR and push (.github/workflows/ui.yml) in the official Playwright container. Approved snapshots live in tests/ui/snapshots/ and are made by CI itself (fonts render differently on every machine): a new screen's first run on a push approves it and commits it. After an intended design change, run the workflow by hand with "update snapshots" ticked. Locally, check layout without snapshots: `npx playwright test --ignore-snapshots` (set TMPDIR to a disk folder).
