export interface Input {
  throttle: number;
  brake: number;
  steer: number; // -1 left .. 1 right
  handbrake: boolean;
  confirm: boolean; // edge-triggered
  pause: boolean; // edge-triggered
  restart: boolean; // edge-triggered
  debug: boolean; // edge-triggered: toggles the look panel
}

const held = new Set<string>();
const fresh = new Set<string>();
const GAME_KEYS = ['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight', 'Space'];

addEventListener('keydown', (e) => {
  if (!held.has(e.code)) fresh.add(e.code);
  held.add(e.code);
  if (GAME_KEYS.includes(e.code)) e.preventDefault();
});
addEventListener('keyup', (e) => held.delete(e.code));
addEventListener('blur', () => held.clear());

let prevButtons: boolean[] = [];
let keySteer = 0;
export let padName = '';

const down = (...codes: string[]) => codes.some((c) => held.has(c));
const tapped = (...codes: string[]) => codes.some((c) => fresh.has(c));

export function readInput(dt: number): Input {
  const pad = [...(navigator.getGamepads?.() ?? [])].find((p) => p && p.connected) ?? null;
  padName = pad?.id ?? '';

  // Keyboard: ease the steering so taps don't snap the wheel.
  const target = (down('KeyD', 'ArrowRight') ? 1 : 0) - (down('KeyA', 'ArrowLeft') ? 1 : 0);
  const rate = target === 0 ? 8 : 5;
  keySteer += Math.max(-rate * dt, Math.min(rate * dt, target - keySteer));

  const input: Input = {
    throttle: down('KeyW', 'ArrowUp') ? 1 : 0,
    brake: down('KeyS', 'ArrowDown') ? 1 : 0,
    steer: keySteer,
    handbrake: down('Space', 'ShiftLeft'),
    confirm: tapped('Enter', 'Space'),
    pause: tapped('Escape', 'KeyP'),
    restart: tapped('KeyR'),
    debug: false,
  };

  if (pad) {
    const b = pad.buttons.map((x) => x.pressed);
    const edge = (i: number) => !!b[i] && !prevButtons[i];
    const sx = pad.axes[0] ?? 0;
    const stick = Math.abs(sx) < 0.12 ? 0 : Math.sign(sx) * ((Math.abs(sx) - 0.12) / 0.88);
    if (stick !== 0) input.steer = stick;
    input.throttle = Math.max(input.throttle, pad.buttons[7]?.value ?? 0);
    input.brake = Math.max(input.brake, pad.buttons[6]?.value ?? 0);
    input.handbrake ||= !!(b[1] || b[5]);
    input.confirm ||= edge(0);
    input.pause ||= edge(9);
    input.restart ||= edge(3);
    input.debug ||= edge(8);
    prevButtons = b;
  }
  fresh.clear();
  return input;
}
