# Sound credits

Every file here may be used on a public website. All are mono MP3s.

| Files | Source | Licence |
|---|---|---|
| `crash-metal-*.mp3` (from `impactMetal_heavy_000…004`), `crash-panel-*.mp3` (`impactPlate_heavy_000/002/004`), `crash-glass-*.mp3` (`impactGlass_heavy_000/002/004`), `thud-*.mp3` (`impactSoft_heavy_000/002/004`) | [Impact Sounds](https://kenney.nl/assets/impact-sounds) by Kenney (kenney.nl) | [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/) |
| `splash-01.mp3`, `splash-04.mp3`, `splash-07.mp3`, `bubbles.mp3` (from `splash_01/04/07`, `bubble_01`) | [40 CC0 water / splash / slime SFX](https://opengameart.org/content/40-cc0-water-splash-slime-sfx) by rubberduck, on OpenGameArt | [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/) |
| `voices/*.mp3` | Generated for this game with [Kokoro-82M](https://huggingface.co/hexgrad/Kokoro-82M) (Apache-2.0) via [kokoro-onnx](https://github.com/thewh1teagle/kokoro-onnx) (MIT), run locally; script and lines in `tools/voices/` | Our own output; Kokoro's licence puts no restriction on generated audio |

Converted with ffmpeg: downmixed to mono, leading silence trimmed. The voice
clips are also pitched/sped up a touch, band-limited, compressed, given a short
slap-back echo and peak-normalised (see `tools/voices/generate.py`).

The tyre squeal, rubber scrub and motor whine are synthesised at runtime in
`src/sfx.ts`; they have no files.
