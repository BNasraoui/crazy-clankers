// Button prompts that follow whatever you last touched: a pad's coloured face
// buttons, keyboard keycaps, or plain words on a touchscreen. The page carries
// data-input="pad" | "kb" | "touch" and CSS shows the matching label.

import { setTouchMode } from './touch';

export type Device = 'pad' | 'kb' | 'touch';
export type Act = 'confirm' | 'back' | 'alt' | 'choose' | 'restart' | 'menu' | 'radio' | 'board';

const coarse = typeof matchMedia === 'function' && matchMedia('(pointer: coarse)').matches;
let device: Device = coarse ? 'touch' : 'kb';
document.documentElement.dataset.input = device;

export function useDevice(d: Device) {
  if (d === device) return;
  device = d;
  document.documentElement.dataset.input = d;
  setTouchMode(d === 'touch'); // the touch controls and tap buttons follow the same device
}

addEventListener('keydown', () => useDevice('kb'), true);
// pointerType tells a real mouse from a finger (a tap also fires a fake mouse event, so don't listen for those).
addEventListener('pointerdown', (e) => useDevice(e.pointerType === 'mouse' ? 'kb' : 'touch'), true);

// [pad face button, its colour class, keyboard key]. On a touchscreen the label itself is what you tap.
const KEYS: Record<Act, [string, string, string]> = {
  confirm: ['A', 'a', 'Enter'],
  back: ['B', 'b', 'Esc'],
  alt: ['Y', 'y', 'H'],
  choose: ['✚', 'pad', '◀ ▶'],
  restart: ['Y', 'y', 'R'],
  menu: ['B', 'b', '⌫'],
  radio: ['X', 'x', 'M'],
  board: ['RB', 'pad bumper', 'Tab'],
};

export const glyph = (cls: string, label: string) => `<i class="glyph ${cls}"><b>${label}</b></i>`;
export const keycap = (label: string) => `<i class="keycap"><b>${label}</b></i>`;

// One prompt glyph that changes with the device.
export function key(act: Act) {
  const [pad, cls, kb] = KEYS[act];
  return `<span class="key"><span class="k-pad">${glyph(cls, pad)}</span><span class="k-kb">${keycap(kb)}</span></span>`;
}

// A whole phrase per device, for the big calls to action.
export function phrase(pad: string, kb: string, touch: string) {
  return `<span class="k-pad">${pad}</span><span class="k-kb">${kb}</span><span class="k-touch">${touch}</span>`;
}
