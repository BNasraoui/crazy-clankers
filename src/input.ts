import { useDevice } from './prompts';
import { mergeTouch, setTouchMode } from './touch';

export interface Input {
  radioNext: boolean;
  radioSkip: boolean;
  radioMenu: boolean;
  radioHold: boolean; // LB / T held: the station wheel
  aimX: number; // right stick, -1..1 (picks on the station wheel)
  aimY: number;
  padConfirm: boolean;
  throttle: number;
  brake: number;
  steer: number; // -1 left .. 1 right
  handbrake: boolean;
  confirm: boolean; // edge-triggered
  pause: boolean; // edge-triggered
  restart: boolean; // edge-triggered
  debug: boolean; // edge-triggered: toggles the look panel
  hop: boolean; // edge-triggered: Crazy Hop
  navX: number; // edge-triggered menu move: -1, 0 or 1
  navY: number;
  back: boolean; // edge-triggered: B / Esc / Backspace
  alt: boolean; // edge-triggered: Y / H
  lookX: number; // right stick (or Q/E) for inspecting, -1..1
  select: number; // a cab tapped in the picker, or -1
}

const held = new Set<string>();
const fresh = new Set<string>();
const GAME_KEYS = ['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight', 'Space'];

addEventListener('keydown', (e) => {
  const target = e.target instanceof HTMLElement ? e.target : null;
  if (e.code !== 'Escape' && (target?.closest('input, textarea, #radio-screen') ||
    (target?.closest('button') && ['Enter', 'Space'].includes(e.code)))) return;
  if (!held.has(e.code)) fresh.add(e.code);
  held.add(e.code);
  if (GAME_KEYS.includes(e.code)) e.preventDefault();
});
addEventListener('keyup', (e) => held.delete(e.code));
addEventListener('blur', () => held.clear());

// Per-pad button state from last frame, for edge detection.
const prevButtons = new Map<number, boolean[]>();
let keySteer = 0;
// Stick-as-D-pad latch for menus, so one flick moves one step.
let stickNav = { x: 0, y: 0 };
export let padName = '';
// Live readout of every pad the browser reports (shown in the look panel).
export let padDebug = '';

const down = (...codes: string[]) => codes.some((c) => held.has(c));
const tapped = (...codes: string[]) => codes.some((c) => fresh.has(c));

// One controller's state, normalised to the standard Xbox-style layout.
interface PadState { steer: number; throttle: number; brake: number; buttons: boolean[]; ly: number; rx: number; ry: number }

// Browsers report the "standard" layout for most pads. On Linux, Steam's virtual
// Xbox 360 pad can arrive unmapped instead: then triggers are axes 2 and 5 (-1..1)
// and Start is button 7.
function readPad(p: Gamepad): PadState {
  const pressed = p.buttons.map((x) => x.pressed || x.value > 0.5);
  if (p.mapping === 'standard') {
    return { steer: p.axes[0] ?? 0, throttle: p.buttons[7]?.value ?? 0, brake: p.buttons[6]?.value ?? 0, buttons: pressed, ly: p.axes[1] ?? 0, rx: p.axes[2] ?? 0, ry: p.axes[3] ?? 0 };
  }
  const trig = (i: number) => (p.axes.length > i ? Math.max(0, ((p.axes[i] ?? -1) + 1) / 2) : 0);
  // Remap to standard indices: 0 A, 1 B, 2 X, 3 Y, 4 LB, 5 RB, 8 Back, 9 Start.
  const std: boolean[] = [];
  std[0] = pressed[0]; std[1] = pressed[1]; std[2] = pressed[2]; std[3] = pressed[3];
  std[4] = pressed[4]; std[5] = pressed[5]; std[8] = pressed[6]; std[9] = pressed[7];
  // D-pad arrives as a hat on axes 6/7.
  const hx = p.axes[6] ?? 0, hy = p.axes[7] ?? 0;
  std[12] = hy < -0.5; std[13] = hy > 0.5; std[14] = hx < -0.5; std[15] = hx > 0.5;
  return { steer: p.axes[0] ?? 0, throttle: trig(5), brake: trig(2), buttons: std, ly: p.axes[1] ?? 0, rx: p.axes[3] ?? 0, ry: p.axes[4] ?? 0 };
}

export function readInput(dt: number): Input {
  const pads = [...(navigator.getGamepads?.() ?? [])].filter((p): p is Gamepad => !!p && p.connected);

  // Keyboard: ease the steering so taps don't snap the wheel.
  const target = (down('KeyD', 'ArrowRight') ? 1 : 0) - (down('KeyA', 'ArrowLeft') ? 1 : 0);
  const rate = target === 0 ? 8 : 5;
  keySteer += Math.max(-rate * dt, Math.min(rate * dt, target - keySteer));

  const input: Input = {
    radioNext: tapped('KeyT'),
    radioSkip: tapped('KeyN'),
    radioMenu: tapped('KeyM'),
    radioHold: down('KeyT'),
    aimX: 0,
    aimY: 0,
    padConfirm: false,
    throttle: down('KeyW', 'ArrowUp') ? 1 : 0,
    brake: down('KeyS', 'ArrowDown') ? 1 : 0,
    steer: keySteer,
    handbrake: down('Space', 'ShiftLeft'),
    confirm: tapped('Enter', 'Space'),
    pause: tapped('Escape', 'KeyP'),
    restart: tapped('KeyR'),
    debug: false, // the look panel listens for ` itself
    hop: tapped('KeyE', 'KeyJ'),
    navX: (tapped('ArrowRight', 'KeyD') ? 1 : 0) - (tapped('ArrowLeft', 'KeyA') ? 1 : 0),
    navY: (tapped('ArrowDown', 'KeyS') ? 1 : 0) - (tapped('ArrowUp', 'KeyW') ? 1 : 0),
    back: tapped('Escape', 'Backspace'),
    alt: tapped('KeyH'),
    lookX: (down('KeyX') ? 1 : 0) - (down('KeyZ') ? 1 : 0),
    select: -1,
  };

  // Merge every connected pad. Some devices are listed but never send input
  // (the Steam Deck's raw controller, which Steam holds), so we can't just take the first.
  let active: Gamepad | null = null;
  const debug: string[] = [];
  for (const p of pads) {
    const st = readPad(p);
    const prev = prevButtons.get(p.index) ?? [];
    const edge = (i: number) => !!st.buttons[i] && !prev[i];
    const sx = st.steer;
    const stick = Math.abs(sx) < 0.15 ? 0 : Math.sign(sx) * ((Math.abs(sx) - 0.15) / 0.85);
    if (stick !== 0) input.steer = stick;
    input.throttle = Math.max(input.throttle, st.throttle);
    input.brake = Math.max(input.brake, st.brake);
    input.handbrake ||= !!(st.buttons[1] || st.buttons[5]);
    input.confirm ||= edge(0);
    input.padConfirm ||= edge(0);
    input.radioNext ||= edge(4);
    input.radioSkip ||= edge(2);
    input.radioHold ||= !!st.buttons[4];
    if (Math.hypot(st.rx, st.ry) > 0.5) { input.aimX = st.rx; input.aimY = st.ry; }
    input.pause ||= edge(9);
    input.restart ||= edge(3);
    input.debug ||= edge(8);
    input.hop ||= edge(0);
    input.back ||= edge(1);
    input.alt ||= edge(3);
    if (edge(12)) input.navY = -1;
    if (edge(13)) input.navY = 1;
    if (edge(14)) input.navX = -1;
    if (edge(15)) input.navX = 1;
    const rx = Math.abs(st.rx) < 0.2 ? 0 : st.rx;
    if (rx !== 0) input.lookX = rx;
    // Left stick flicks act as a D-pad in menus.
    const fx = st.steer > 0.6 ? 1 : st.steer < -0.6 ? -1 : 0;
    const fy = st.ly > 0.6 ? 1 : st.ly < -0.6 ? -1 : 0;
    if (fx && fx !== stickNav.x) input.navX = fx;
    if (fy && fy !== stickNav.y) input.navY = fy;
    stickNav = { x: fx, y: fy };
    prevButtons.set(p.index, st.buttons);
    const busy = stick !== 0 || st.throttle > 0.05 || st.brake > 0.05 || st.buttons.some(Boolean);
    if (busy) { useDevice('pad'); setTouchMode(false); }
    if (busy || !active) active = p;
    debug.push(`#${p.index} ${p.id.slice(0, 40)} [${p.mapping || 'unmapped'}] ` +
      `axes ${p.axes.map((a) => a.toFixed(1)).join(' ')} | buttons ${p.buttons.map((b, i) => (b.pressed ? i : '')).filter(String).join(',') || '-'}`);
  }
  padName = active?.id ?? '';
  padDebug = pads.length ? debug.join('\n') : 'No gamepads reported by the browser. Press any button on the controller.';
  mergeTouch(input);
  fresh.clear();
  return input;
}
