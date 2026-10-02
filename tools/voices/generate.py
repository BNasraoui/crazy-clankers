"""Renders the pedestrian shouts in lines.json to public/sounds/voices/*.mp3.

Kokoro-82M (Apache-2.0) via kokoro-onnx, run locally. Setup:
  uv venv && uv pip install kokoro-onnx soundfile numpy imageio-ffmpeg
  curl -LO https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx
  curl -LO https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin
  python tools/voices/generate.py --models <dir with the two files>

Each clip is sped up and pitched up a touch (people shouting in a panic),
band-limited, compressed, given a short street slap-back echo, trimmed,
peak-normalised and saved as a small mono MP3.
"""
import argparse, json, os, re, subprocess, tempfile
import numpy as np
import soundfile as sf
import imageio_ffmpeg
from kokoro_onnx import Kokoro

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
OUT = os.path.join(ROOT, 'public', 'sounds', 'voices')
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
FEMALE = {'dogwalker'}
KINDS = ['courier', 'dogwalker', 'hippie', 'jogger', 'scooter', 'tourist']

ap = argparse.ArgumentParser()
ap.add_argument('--models', default='.')
args = ap.parse_args()
spec = json.load(open(os.path.join(os.path.dirname(__file__), 'lines.json')))
kokoro = Kokoro(os.path.join(args.models, 'kokoro-v1.0.onnx'), os.path.join(args.models, 'voices-v1.0.bin'))
os.makedirs(OUT, exist_ok=True)
for f in os.listdir(OUT):
    if f.endswith('.mp3'): os.remove(os.path.join(OUT, f))  # stale clips are rebuilt below
turn = {k: 0 for k in KINDS}


def voice_for(kinds):
    # Rotate through each kind's voices so lines spread across the cast.
    k = min(kinds, key=lambda k: turn[k])
    turn[k] += 1
    pool = spec['voices'][k]
    return pool[turn[k] % len(pool)]


def slug(text):
    return re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-')[:28]


def render(text, voice, path, speed, pitch, phonemes=False, scream=False):
    samples, sr = kokoro.create(text, voice=voice, speed=speed, lang='en-us', is_phonemes=phonemes)
    with tempfile.TemporaryDirectory() as tmp:
        raw = os.path.join(tmp, 'raw.wav')
        mid = os.path.join(tmp, 'mid.wav')
        sf.write(raw, samples, sr)
        # Kokoro can't hold a vowel, so a scream is a sung "aaa" pushed way up, stretched and shaken.
        shriek = ['atempo=0.7', 'vibrato=f=7:d=0.3', 'afade=t=out:st=0.55:d=0.45'] if scream else []
        chain = ','.join([
            f'asetrate={int(sr * pitch)}', f'aresample={sr}', *shriek,
            'highpass=f=140', 'lowpass=f=8500',
            'equalizer=f=2800:t=q:w=1.2:g=4',
            'acompressor=threshold=-20dB:ratio=4:attack=4:release=80:makeup=5',
            'aecho=0.9:0.55:19|47:0.16|0.07',  # a short slap off the buildings
            'silenceremove=start_periods=1:start_threshold=-45dB:stop_periods=-1:stop_threshold=-45dB:stop_duration=0.15',
        ])
        subprocess.run([FFMPEG, '-v', 'error', '-y', '-i', raw, '-af', chain, mid], check=True)
        x, sr2 = sf.read(mid, dtype='float32')
        x = x / max(1e-6, np.abs(x).max()) * 0.89  # -1 dBFS peak
        fade = min(len(x), int(sr2 * 0.04))
        x[-fade:] *= np.linspace(1, 0, fade)
        sf.write(mid, x, sr2)
        subprocess.run([FFMPEG, '-v', 'error', '-y', '-i', mid, '-ac', '1', '-ar', '22050', '-c:a', 'libmp3lame', '-b:a', '48k', path], check=True)
    return len(x) / sr2


clips = []
n = 0
for line in spec['lines']:
    kinds = KINDS if 'any' in line['kinds'] else line['kinds']
    groups = [g for g in ([k for k in kinds if k not in FEMALE], [k for k in kinds if k in FEMALE]) if g]
    for g in groups:
        n += 1
        voice = voice_for(g)
        name = f'line{n:02d}-{slug(line["text"])}.mp3'
        dur = render(line.get('say', line['text']), voice, os.path.join(OUT, name), speed=1.15, pitch=1.05)
        clips.append({'file': name, 'kinds': g, 'text': line['text'], 'voice': voice, 'scream': False, 'dur': round(dur, 2)})
        print(name, voice, f'{dur:.2f}s')

male = [k for k in KINDS if k not in FEMALE]
for i, s in enumerate(spec['screams']):
    for g in (male, sorted(FEMALE)):
        n += 1
        voice = voice_for(g)
        name = f'scream{n:02d}-{slug(s["text"])}.mp3'
        dur = render(s.get('say', s['text']), voice, os.path.join(OUT, name), speed=1.1, pitch=1.5 if s.get('scream') else 1.08,
                     phonemes=s.get('phonemes', False), scream=s.get('scream', False))
        clips.append({'file': name, 'kinds': g, 'text': s['text'], 'voice': voice, 'scream': True, 'dur': round(dur, 2)})
        print(name, voice, f'{dur:.2f}s')

json.dump({'clips': clips}, open(os.path.join(OUT, 'voices.json'), 'w'), indent=1)
print(len(clips), 'clips')
