import type { Input } from './input';
import { voiceActive } from './audio';

export interface Station { name: string; source: string }
// PLACEHOLDERS — Ben: replace these official NCS video stations with your playlists.
export const DEFAULT_STATIONS: Station[] = [
  { name: 'NCS · On & On', source: 'K4DyBUG242c' },
  { name: 'NCS · Cartoon & Friends', source: 'Dr8xAycPpYw' },
];
const STORAGE_KEY = 'clankers.radio.v1';

export function youtubeSource(value: string): { kind: 'video' | 'playlist'; id: string } | null {
  let id = value.trim();
  if (/^(?:https?:\/\/|(?:www\.|m\.|music\.)?youtube\.com\/|youtu\.be\/)/i.test(id)) {
    try {
      const url = new URL(id.includes('://') ? id : `https://${id}`);
      if (!['youtube.com', 'www.youtube.com', 'm.youtube.com', 'music.youtube.com', 'youtu.be', 'www.youtube-nocookie.com'].includes(url.hostname)) return null;
      id = url.searchParams.get('list') || (url.hostname === 'youtu.be' ? url.pathname.slice(1) : url.searchParams.get('v') || url.pathname.match(/^\/(?:embed|shorts|live)\/([^/]+)/)?.[1] || '');
    } catch { return null; }
  }
  if (/^[\w-]{11}$/.test(id)) return { kind: 'video', id };
  if (/^(?:PL|UU|OLAK5uy_|RD|FL)[\w-]{10,}$/.test(id)) return { kind: 'playlist', id };
  return null;
}

interface Player {
  cuePlaylist(options: { listType: string; list: string }): void;
  cueVideoById(id: string): void;
  playVideo(): void;
  playVideoAt(index: number): void;
  pauseVideo(): void;
  nextVideo(): void;
  setShuffle(on: boolean): void;
  setLoop(on: boolean): void;
  setVolume(volume: number): void;
  getPlaylist(): string[] | undefined;
  getPlaylistIndex(): number;
  getVideoData(): { title?: string; video_id?: string };
  destroy(): void;
}
interface PlayerOptions {
  width: number; height: number;
  playerVars: Record<string, string | number>;
  events: {
    onReady(e: { target: Player }): void;
    onStateChange(e: { data: number }): void;
    onError(e: { data: number }): void;
    onAutoplayBlocked(): void;
  };
}
type YouTube = { Player: new (element: HTMLElement, options: PlayerOptions) => Player };
declare global { interface Window { YT?: YouTube; onYouTubeIframeAPIReady?: () => void } }
let api: Promise<YouTube> | undefined;
function loadYouTube(): Promise<YouTube> {
  if (window.YT?.Player) return Promise.resolve(window.YT);
  if (!api) api = new Promise((resolve, reject) => {
    const previous = window.onYouTubeIframeAPIReady;
    const timer = window.setTimeout(() => reject(new Error('YouTube did not respond. Reload to retry.')), 15000);
    window.onYouTubeIframeAPIReady = () => {
      clearTimeout(timer);
      previous?.();
      if (window.YT) resolve(window.YT);
    };
    const script = document.createElement('script');
    script.src = 'https://www.youtube.com/iframe_api';
    script.onerror = () => { clearTimeout(timer); reject(new Error('YouTube is unavailable. Try local files or reload.')); };
    document.head.append(script);
  });
  return api;
}

function button(text: string, action: () => void) {
  const el = document.createElement('button');
  el.type = 'button'; el.textContent = text; el.onclick = action;
  return el;
}
function shuffle<T>(items: T[]): T[] {
  for (let i = items.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [items[i], items[j]] = [items[j], items[i]];
  }
  return items;
}

export class Radio {
  private stations: Station[] = DEFAULT_STATIONS.map(s => ({ ...s }));
  private selected = 0; // stations.length is the local-files station
  private player?: Player;
  private ready = false;
  private generation = 0;
  private enabled = false;
  private playing = false;
  private interacted = false;
  private volume = 0.35;
  private ducked = false;
  private failedTracks = new Set<number>();
  private failedAttempts = 0;
  private failedStations = new Set<number>();
  private watchdog = 0;
  private retry = 0;
  private toastTimer = 0;
  private files: File[] = [];
  private fileIndex = 0;
  private objectURL = '';
  private audio = new Audio();
  private dashboard = document.createElement('aside');
  private playerSlot = document.createElement('div');
  private stationLabel = document.createElement('b');
  private trackLabel = document.createElement('div');
  private screen = document.createElement('section');
  private rows = document.createElement('div');
  private toast = document.createElement('div');
  private note = document.createElement('p');
  private toggle = button('Play', () => this.playPause());
  private collapsed = button('📻 Radio off · turn on', () => this.tune(this.selected));
  private returnFocus: HTMLElement | null = null;

  constructor() {
    try {
      const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || 'null');
      if (saved && Array.isArray(saved.stations)) {
        this.stations = saved.stations.filter((s: Station) => s && typeof s.name === 'string' && typeof s.source === 'string' && youtubeSource(s.source)).map((s: Station) => ({ name: s.name.slice(0, 80), source: s.source }));
        if (typeof saved.volume === 'number' && Number.isFinite(saved.volume)) this.volume = Math.max(0, Math.min(1, saved.volume));
      }
    } catch { /* Storage is optional, including in private browsing. */ }
    this.dashboard.id = 'radio-dashboard';
    this.dashboard.setAttribute('aria-label', 'Dashboard radio');
    this.dashboard.hidden = true;
    this.playerSlot.className = 'radio-player';
    this.trackLabel.className = 'radio-track';
    const controls = document.createElement('div'); controls.className = 'radio-controls';
    controls.append(button('◀ Station', () => this.nextStation(-1)), this.toggle, button('Skip ▶', () => this.nextTrack()), button('Station ▶', () => this.nextStation(1)), button('Off / collapse', () => this.off()));
    this.dashboard.append(this.stationLabel, this.trackLabel, this.playerSlot, controls, this.volumeControl());
    this.collapsed.id = 'radio-collapsed';
    this.toast.id = 'radio-toast'; this.toast.setAttribute('role', 'status'); this.toast.hidden = true;
    this.screen.id = 'radio-screen'; this.screen.hidden = true;
    this.screen.setAttribute('aria-label', 'Radio stations');
    this.screen.innerHTML = `<header><span>CLANKERS FM / YOUR AIRWAVES</span><h2>RADIO</h2></header><p>T / LB: next station · N / X: skip (driving)<br>D-pad: focus · A: select · B / Esc: back</p>`;
    this.note.setAttribute('role', 'status');
    const form = document.createElement('form');
    form.innerHTML = `<label>YouTube URL or ID<input name="source" required placeholder="Paste a playlist or video URL"></label><label>Station name (optional)<input name="name" maxlength="80" placeholder="Late-night fares"></label><button type="submit">Add station</button>`;
    form.onsubmit = e => {
      e.preventDefault();
      const data = new FormData(form), source = String(data.get('source')).trim();
      const parsed = youtubeSource(source);
      if (!parsed) { this.message('Paste a valid YouTube playlist or video URL / ID.'); return; }
      if (this.selected === this.stations.length) ++this.selected;
      this.stations.push({ source, name: String(data.get('name')).trim() || `YouTube ${parsed.kind} ${parsed.id}` });
      this.save(); this.renderStations(); form.reset();
    };
    const local = document.createElement('div'); local.className = 'radio-local';
    local.append(button('Play my own files', () => this.pickFiles(false)), button('Choose folder', () => this.pickFiles(true)));
    const privacy = document.createElement('p'); privacy.textContent = 'Local files stay on this device. Choose them again after reloading. YouTube streams directly in its visible player.';
    const transport = document.createElement('div'); transport.className = 'radio-controls';
    transport.append(button('Previous station', () => this.nextStation(-1)), button('Play / pause', () => this.playPause()), button('Skip track', () => this.nextTrack()), button('Next station', () => this.nextStation(1)), button('Radio off', () => this.off()), this.volumeControl());
    this.screen.append(transport, this.rows, form, local, privacy, this.note, button('Back to game', () => this.close()));
    document.body.append(this.dashboard, this.collapsed, this.screen, this.toast);
    this.renderStations();
    this.audio.onended = () => this.nextTrack();
    this.audio.onerror = () => this.trackFailed();
    document.addEventListener('click', e => {
      if ((e.target as Element).closest('[data-radio-open]')) this.open();
      else if (!this.interacted && e.isTrusted) this.gesture();
    });
    document.addEventListener('visibilitychange', () => {
      if (document.hidden && this.selected < this.stations.length) this.off();
    });
    addEventListener('resize', () => {
      if (this.enabled && !this.hasRoom()) { this.off(); this.message('Radio off: enlarge the window to show the YouTube player.'); }
    });
  }

  /** Returns true when the radio screen consumes menu input. */
  frame(input: Input, state: string): boolean {
    const menu = state === 'title' || state === 'paused';
    if (!this.interacted && (input.confirm || input.back || input.alt || input.navX || input.navY || input.radioNext || input.radioSkip || input.radioMenu)) this.gesture();
    const duck = voiceActive();
    if (duck !== this.ducked) { this.ducked = duck; this.applyVolume(); }
    if (this.screen.hidden && menu && (input.radioMenu || input.radioSkip)) { this.open(); return true; }
    if (!this.screen.hidden) {
      if (input.back || input.pause) { this.close(); return true; }
      const controls = [...this.screen.querySelectorAll<HTMLElement>('button:not(:disabled), input')];
      const index = controls.indexOf(document.activeElement as HTMLElement);
      const focused = document.activeElement;
      if (input.navX && focused instanceof HTMLInputElement && focused.type === 'range') {
        focused.value = String(Number(focused.value) + input.navX * 5);
        focused.dispatchEvent(new Event('input'));
      }
      const move = input.navY || (focused instanceof HTMLInputElement && focused.type === 'range' ? 0 : input.navX);
      if (move) controls[(index + move + controls.length) % controls.length]?.focus();
      if (input.padConfirm) (document.activeElement as HTMLElement)?.click();
      return true;
    }
    if (state === 'play') {
      if (input.radioNext) this.nextStation(1);
      if (input.radioSkip) this.nextTrack();
    }
    return false;
  }

  private gesture() {
    this.interacted = true;
    if (this.stations.length) this.tune(0);
  }

  private hasRoom() { return innerWidth >= 660 && innerHeight >= 600; }

  private save() {
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify({ stations: this.stations, volume: this.volume })); } catch { /* Play without persistence. */ }
  }

  private message(text: string) {
    this.note.textContent = text; this.toast.textContent = text; this.toast.hidden = false;
    clearTimeout(this.toastTimer);
    this.toastTimer = window.setTimeout(() => { this.toast.hidden = true; }, 4000);
  }

  private stopSource() {
    ++this.generation;
    clearTimeout(this.watchdog); clearTimeout(this.retry);
    this.audio.pause(); this.audio.removeAttribute('src'); this.audio.load();
    if (this.objectURL) { URL.revokeObjectURL(this.objectURL); this.objectURL = ''; }
    this.ready = false;
    this.player?.destroy(); this.player = undefined;
    this.playerSlot.replaceChildren();
  }

  off() {
    this.stopSource(); // Destroy the iframe before hiding it: never hidden YouTube audio.
    this.enabled = this.playing = false;
    this.dashboard.hidden = true; this.collapsed.hidden = false;
  }

  nextStation(direction: number) {
    this.tune((this.selected + direction + this.stations.length + 1) % (this.stations.length + 1));
  }

  private tune(index: number, automatic = false) {
    this.interacted = true;
    if (!automatic) this.failedStations.clear();
    this.stopSource();
    this.selected = index; this.failedTracks.clear(); this.failedAttempts = 0;
    const station = this.stations[index];
    if (station && (!this.hasRoom() || document.hidden)) { this.off(); this.message('Radio off: the YouTube player needs a visible window (660 × 600 or larger).'); return; }
    this.enabled = this.playing = true;
    this.dashboard.hidden = false; this.collapsed.hidden = true;
    this.toggle.textContent = 'Pause';
    this.stationLabel.textContent = station?.name || 'Play my own files';
    this.trackLabel.textContent = 'Tuning…';
    this.playerSlot.hidden = !station;
    this.message(`📻 ${this.stationLabel.textContent}`);
    if (!station) {
      if (this.files.length) this.playFile();
      else { this.off(); this.message('Choose files or a folder in the Radio screen (M / X in a menu).'); }
      return;
    }
    const token = this.generation;
    void loadYouTube().then(YT => {
      if (token !== this.generation) return;
      const mount = document.createElement('div'); this.playerSlot.append(mount);
      let shuffled = false;
      const source = youtubeSource(station.source)!;
      this.player = new YT.Player(mount, {
        width: 288, height: 216,
        playerVars: { controls: 1, playsinline: 1, origin: location.origin, autoplay: 0 },
        events: {
          onReady: ({ target }) => {
            if (token !== this.generation) return;
            this.ready = true; this.applyVolume();
            if (source.kind === 'playlist') target.cuePlaylist({ listType: 'playlist', list: source.id });
            else target.cueVideoById(source.id);
            this.armWatchdog();
          },
          onStateChange: ({ data }) => {
            if (token !== this.generation || !this.ready) return;
            if (data === 5 && !shuffled) {
              shuffled = true;
              if (source.kind === 'playlist') {
                this.player!.setShuffle(true); this.player!.setLoop(true);
                const count = this.player!.getPlaylist()?.length || 1;
                if (this.playing) this.player!.playVideoAt(Math.floor(Math.random() * count));
              } else if (this.playing) this.player!.playVideo();
            }
            if (data === 1) {
              this.failedAttempts = 0;
              clearTimeout(this.watchdog);
              this.playing = true; this.toggle.textContent = 'Pause';
              this.trackLabel.textContent = this.player!.getVideoData().title || 'Playing on YouTube';
            }
            if (data === 2) { clearTimeout(this.watchdog); this.playing = false; this.toggle.textContent = 'Play'; }
            if (data === 0 && source.kind === 'video') this.nextStation(1);
          },
          onError: ({ data }) => {
            if (token !== this.generation) return;
            if ([2, 5, 100, 101, 150].includes(data)) this.trackFailed();
            else { this.off(); this.message(`YouTube error ${data}. Try again using the visible player or another station.`); }
          },
          onAutoplayBlocked: () => {
            if (token !== this.generation) return;
            clearTimeout(this.watchdog); this.playing = false; this.toggle.textContent = 'Play';
            this.message('Press Play in the YouTube player to start audio.');
          },
        },
      });
      this.armWatchdog();
    }).catch(error => {
      if (token !== this.generation) return;
      this.off(); this.message(error.message);
    });
  }

  private armWatchdog() {
    clearTimeout(this.watchdog);
    if (!this.playing) return;
    this.watchdog = window.setTimeout(() => this.stationFailed(), 20000);
  }

  private trackFailed() {
    if (!this.enabled) return;
    if (!this.playing) { this.off(); this.message('Track unavailable. Choose a station to resume.'); return; }
    clearTimeout(this.watchdog); clearTimeout(this.retry);
    const local = this.selected === this.stations.length;
    const count = local ? this.files.length : this.player?.getPlaylist()?.length || 1;
    this.failedTracks.add(local ? this.fileIndex : this.player?.getPlaylistIndex() ?? 0);
    ++this.failedAttempts;
    if (this.failedTracks.size >= count || (!local && this.failedAttempts >= count)) { this.stationFailed(); return; }
    this.message('Track unavailable — skipping.');
    this.retry = window.setTimeout(() => this.nextTrack(), 300);
  }

  private stationFailed() {
    const name = this.stationLabel.textContent;
    this.failedStations.add(this.selected);
    for (let step = 1; step <= this.stations.length + 1; step++) {
      const next = (this.selected + step) % (this.stations.length + 1);
      if (!this.failedStations.has(next) && (next < this.stations.length || this.files.length)) {
        this.tune(next, true); this.message(`${name} unavailable — trying ${this.stationLabel.textContent}.`); return;
      }
    }
    this.off(); this.message('No playable stations. Add another station or choose local files.');
  }

  playPause() {
    if (!this.enabled) { this.tune(this.selected); return; }
    this.playing = !this.playing;
    this.toggle.textContent = this.playing ? 'Pause' : 'Play';
    clearTimeout(this.watchdog);
    if (this.selected === this.stations.length) {
      if (this.playing) this.startLocalAudio(); else this.audio.pause();
    } else if (this.ready) {
      if (this.playing) this.player?.playVideo(); else this.player?.pauseVideo();
    }
  }

  nextTrack() {
    if (!this.enabled) return;
    clearTimeout(this.retry);
    if (this.selected === this.stations.length) {
      this.fileIndex = (this.fileIndex + 1) % this.files.length; this.playFile();
    } else if (this.ready) {
      if (youtubeSource(this.stations[this.selected].source)?.kind === 'playlist') {
        this.playing = true; this.player?.nextVideo(); this.armWatchdog();
      } else this.nextStation(1);
    }
  }

  private volumeControl() {
    const label = document.createElement('label'); label.textContent = 'Volume ';
    const slider = document.createElement('input');
    slider.type = 'range'; slider.min = '0'; slider.max = '100'; slider.value = String(this.volume * 100);
    slider.setAttribute('aria-label', 'Radio volume'); slider.dataset.radioVolume = '';
    slider.oninput = () => {
      this.volume = Number(slider.value) / 100;
      document.querySelectorAll<HTMLInputElement>('[data-radio-volume]').forEach(el => { el.value = slider.value; });
      this.applyVolume(); this.save();
    };
    label.append(slider);
    return label;
  }

  private applyVolume() {
    const volume = this.volume * (this.ducked ? 0.6 : 1);
    this.audio.volume = volume;
    if (this.ready) this.player?.setVolume(volume * 100);
  }

  private pickFiles(folder: boolean) {
    const picker = document.createElement('input'); picker.type = 'file'; picker.accept = 'audio/*'; picker.multiple = true;
    if (folder) picker.setAttribute('webkitdirectory', '');
    picker.onchange = () => {
      const files = [...(picker.files || [])].filter(f => f.type.startsWith('audio/') || /\.(mp3|wav|ogg|m4a|aac|flac|opus|webm)$/i.test(f.name));
      if (!files.length) { this.message('No audio files selected.'); return; }
      this.files = shuffle(files); this.fileIndex = 0; this.tune(this.stations.length);
    };
    picker.click();
  }

  private playFile() {
    this.audio.pause();
    if (this.objectURL) URL.revokeObjectURL(this.objectURL);
    this.objectURL = URL.createObjectURL(this.files[this.fileIndex]);
    this.audio.src = this.objectURL;
    this.trackLabel.textContent = this.files[this.fileIndex].name;
    this.playing = true; this.toggle.textContent = 'Pause';
    this.applyVolume(); this.startLocalAudio();
  }

  private startLocalAudio() {
    const token = this.generation;
    void this.audio.play().catch(error => {
      if (token !== this.generation || error.name === 'AbortError') return;
      if (error.name === 'NotAllowedError') {
        this.playing = false; this.toggle.textContent = 'Play'; this.message('Press Play to start your files.');
      } else this.trackFailed();
    });
  }

  private open() {
    if (!this.interacted) this.gesture();
    this.returnFocus = document.activeElement as HTMLElement;
    this.screen.hidden = false;
    this.screen.querySelector<HTMLElement>('button')?.focus();
  }

  private close() {
    this.screen.hidden = true;
    this.returnFocus?.focus();
    if (document.activeElement?.closest('#radio-screen')) (document.activeElement as HTMLElement).blur();
  }

  private renderStations() {
    this.rows.replaceChildren();
    this.stations.forEach((station, index) => {
      const row = document.createElement('div'); row.className = 'radio-station';
      const name = document.createElement('input'); name.value = station.name; name.maxLength = 80; name.setAttribute('aria-label', 'Station name');
      const rename = button('Save name', () => {
        station.name = name.value.trim() || station.name; this.save(); this.renderStations();
        if (this.selected === index) this.stationLabel.textContent = station.name;
      });
      const move = (direction: number) => {
        const next = index + direction;
        [this.stations[index], this.stations[next]] = [this.stations[next], this.stations[index]];
        if (this.selected === index) this.selected = next; else if (this.selected === next) this.selected = index;
        this.failedStations.clear(); this.save(); this.renderStations();
      };
      const up = button('Move up', () => move(-1)); up.disabled = index === 0;
      const down = button('Move down', () => move(1)); down.disabled = index === this.stations.length - 1;
      row.append(button(`Tune ${station.name}`, () => this.tune(index)), name, rename, up, down, button('Remove', () => {
        if (this.selected === index) this.off();
        this.stations.splice(index, 1);
        if (this.selected > index) --this.selected;
        this.failedStations.clear(); this.save(); this.renderStations();
      }));
      this.rows.append(row);
    });
  }
}
