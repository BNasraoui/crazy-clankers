import type { Input } from './input';
import { unlockAudio } from './audio';
import { translate } from './i18n';

// Touch controls for phones held sideways. A floating thumb-stick on the left
// for steering, sticker buttons on the right, a pause button up top, taps on
// menus. Everything lands in the same Input the keyboard and pads fill, so the
// game can't tell a thumb from a trigger.
//
// Touch mode turns on for coarse pointers or the first touch, and off again as
// soon as a pad or the keyboard is used (the Steam Deck has a touchscreen too).

const DEAD = 8; // px of thumb travel before the wheel turns
const FULL = 58; // px for full lock
const AIM = 26; // px of drag before the station wheel follows the thumb

export type TapAction = 'confirm' | 'back' | 'alt' | 'pause' | 'restart' | 'board';

let active = false;
const root = document.documentElement;

// Held state, plus edges waiting for the next readInput.
let steer = 0;
const held = { gas: false, brake: false, drift: false };
const edges = new Set<TapAction | 'hop'>();
let pick = -1;
let radioDown = false;
let radioPressed = false; // pressed since the last frame (so a tap between two frames still counts)
let aim = { x: 0, y: 0 };

export const touchActive = () => active;

export function setTouchMode(on: boolean) {
  if (on === active) return;
  active = on;
  root.classList.toggle('touch', on);
  if (!on) release();
}

function release() {
  steer = 0;
  held.gas = held.brake = held.drift = false;
  radioDown = false;
  stickEl.hidden = true;
  stickId = null;
  for (const b of buttons.values()) b.classList.remove('down');
  buttons.clear();
}

/** ORs the touch state into this frame's input, like another pad. */
export function mergeTouch(input: Input) {
  if (active) {
    if (steer !== 0) input.steer = steer;
    if (held.gas) input.throttle = 1;
    if (held.brake) input.brake = 1;
    input.handbrake ||= held.drift;
    input.hop ||= edges.has('hop');
    input.confirm ||= edges.has('confirm');
    input.back ||= edges.has('back');
    input.alt ||= edges.has('alt');
    input.pause ||= edges.has('pause');
    input.restart ||= edges.has('restart');
    input.board ||= edges.has('board');
    if (pick >= 0) input.select = pick;
    if (radioDown || radioPressed) {
      input.radioHold = true;
      if (Math.hypot(aim.x, aim.y) > 0.5) { input.aimX = aim.x; input.aimY = aim.y; }
    }
  }
  radioPressed = false;
  edges.clear();
  pick = -1;
}

// A short buzz on a crash, where the phone can.
export function buzz(impact: number) {
  if (active && impact > 6) navigator.vibrate?.(Math.min(60, 15 + impact * 1.5));
}

// ---------- the controls ----------

const layer = document.createElement('div');
layer.id = 'touch';
layer.innerHTML = `
  <div class="steer-zone"></div>
  <div class="stick" hidden><i></i></div>
  <button type="button" class="tb gas" data-hold="gas"><span data-i18n="touch.gas"></span></button>
  <button type="button" class="tb brake" data-hold="brake"><span data-i18n="touch.brake"></span><small data-i18n="touch.reverse"></small></button>
  <button type="button" class="tb drift" data-hold="drift"><span data-i18n="touch.drift"></span></button>
  <button type="button" class="tb hop" data-edge="hop"><span data-i18n="touch.hop"></span></button>
  <button type="button" class="tb pause" data-edge="pause" data-i18n-aria="touch.pause">❚❚</button>`;
translate(layer);
document.body.appendChild(layer);
const zone = layer.querySelector<HTMLElement>('.steer-zone')!;
const stickEl = layer.querySelector<HTMLElement>('.stick')!;
const knob = stickEl.querySelector<HTMLElement>('i')!;

let stickId: number | null = null;
let stickX = 0;
const buttons = new Map<number, HTMLElement>(); // pointerId -> held button

zone.addEventListener('pointerdown', (e) => {
  if (stickId !== null) return;
  stickId = e.pointerId;
  stickX = e.clientX;
  zone.setPointerCapture(e.pointerId);
  stickEl.style.left = `${e.clientX}px`;
  stickEl.style.top = `${e.clientY}px`;
  stickEl.hidden = false;
  moveStick(e.clientX);
});
zone.addEventListener('pointermove', (e) => { if (e.pointerId === stickId) moveStick(e.clientX); });
const endStick = (e: PointerEvent) => {
  if (e.pointerId !== stickId) return;
  stickId = null;
  steer = 0;
  stickEl.hidden = true;
};
zone.addEventListener('pointerup', endStick);
zone.addEventListener('pointercancel', endStick);

function moveStick(x: number) {
  const dx = Math.max(-FULL, Math.min(FULL, x - stickX));
  knob.style.transform = `translateX(${dx}px)`;
  const mag = Math.max(0, Math.abs(dx) - DEAD) / (FULL - DEAD);
  steer = Math.sign(dx) * mag;
}

for (const b of layer.querySelectorAll<HTMLElement>('.tb')) {
  b.addEventListener('pointerdown', (e) => {
    b.setPointerCapture(e.pointerId);
    buttons.set(e.pointerId, b);
    b.classList.add('down');
    const hold = b.dataset.hold as keyof typeof held | undefined;
    if (hold) held[hold] = true;
    if (b.dataset.edge) edges.add(b.dataset.edge as TapAction | 'hop');
  });
  const up = (e: PointerEvent) => {
    if (buttons.get(e.pointerId) !== b) return;
    buttons.delete(e.pointerId);
    b.classList.remove('down');
    const hold = b.dataset.hold as keyof typeof held | undefined;
    if (hold) held[hold] = false;
  };
  b.addEventListener('pointerup', up);
  b.addEventListener('pointercancel', up);
}

// Menus: anything marked data-tap="confirm|back|..." or data-cab="i" acts as that button.
document.addEventListener('click', (e) => {
  const el = (e.target as Element).closest<HTMLElement>('[data-tap], [data-cab]');
  if (!el) return;
  if (el.dataset.cab) pick = Number(el.dataset.cab);
  if (el.dataset.tap) edges.add(el.dataset.tap as TapAction);
});

// Radio sticker: tap for the next station, hold for the station wheel and drag to aim.
let radioStart = { x: 0, y: 0 };
let radioId: number | null = null;
document.addEventListener('pointerdown', (e) => {
  if (!active || !(e.target as Element).closest('#radio-dashboard > b')) return;
  radioId = e.pointerId;
  radioStart = { x: e.clientX, y: e.clientY };
  aim = { x: 0, y: 0 };
  radioDown = radioPressed = true;
  (e.target as Element).setPointerCapture(e.pointerId);
});
document.addEventListener('pointermove', (e) => {
  if (e.pointerId !== radioId) return;
  const dx = e.clientX - radioStart.x, dy = e.clientY - radioStart.y;
  const d = Math.hypot(dx, dy);
  aim = d < AIM ? { x: 0, y: 0 } : { x: dx / d, y: dy / d };
});
const endRadio = (e: PointerEvent) => { if (e.pointerId === radioId) { radioId = null; radioDown = false; } };
document.addEventListener('pointerup', endRadio);
document.addEventListener('pointercancel', endRadio);
// In touch mode the sticker is the radio button, not the show-controls toggle.
addEventListener('click', (e) => {
  if (active && (e.target as Element).closest('#radio-dashboard > b')) e.stopPropagation();
}, true);

// ---------- switching modes, and the phone itself ----------

if (matchMedia('(pointer: coarse)').matches && !navigator.getGamepads?.().some((p) => p?.connected)) setTouchMode(true);
addEventListener('touchstart', () => setTouchMode(true), { capture: true, passive: true });
addEventListener('keydown', (e) => { if (!(e.target as Element).closest?.('input, textarea')) setTouchMode(false); });

// No pinch-zoom, long-press menus or rubber-banding on the game.
document.addEventListener('gesturestart', (e) => e.preventDefault());
layer.addEventListener('contextmenu', (e) => e.preventDefault());
document.addEventListener('touchmove', (e) => {
  if (!(e.target as Element).closest?.('#radio-screen, #lookpanel, .cab-list')) e.preventDefault(); // these scroll
}, { passive: false });

// Turning the phone upright mid-shift pauses it (the rotate card covers the screen).
matchMedia('(orientation: portrait)').addEventListener('change', (e) => {
  if (e.matches && active && document.body.dataset.state === 'play') edges.add('pause');
});

// Fullscreen on a phone: every tap asks again until the game is fullscreen (a first touch can be
// refused, and leaving the app drops it), then locks to landscape where the browser lets us
// (Android Chrome; iPhone Safari has no fullscreen for pages, only "Add to Home Screen").
let asking = false;
const goFullscreen = () => {
  unlockAudio(); // cheap after the first time; iOS can suspend the context when the app is backgrounded
  if (document.fullscreenElement || asking || !root.requestFullscreen) return;
  asking = true;
  root.requestFullscreen({ navigationUI: 'hide' })
    .then(() => (screen.orientation as ScreenOrientation & { lock?: (o: string) => Promise<void> }).lock?.('landscape'))
    .catch(() => {})
    .finally(() => { asking = false; });
};
addEventListener('touchend', goFullscreen, { capture: true });
addEventListener('click', () => { if (active) goFullscreen(); }, { capture: true });
