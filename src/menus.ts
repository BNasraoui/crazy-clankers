import { CABS } from './models';
import { glyph, key, keycap, phrase, type Act } from './prompts';

// Title screen and cab picker overlays (the 3D taxi rank sits behind them).

interface CabCard { price: string; eta: string; stats: [string, number, string][]; perk?: string } // stats: [label, cells 0..6, value]
const CARDS: Record<string, CabCard> = {
  cab: { price: '$14.20', eta: '2 min', stats: [['LIDAR COUNT', 3, '1 puck'], ['APOLOGY RATE', 2, '3 / min'], ['TOP SPEED', 4, 'brisk']] },
  wayfarer: { perk: 'SEES WHAT FARES WANT · 1.3× PAY', price: '$31.80', eta: '4 min', stats: [['LIDAR COUNT', 6, '29'], ['APOLOGY RATE', 6, '12 / min'], ['TOP SPEED', 3, 'polite']] },
  cybercab: { perk: 'FASTEST CAB IN TOWN', price: '$9.99', eta: 'ETA: TBC', stats: [['LIDAR COUNT', 0, 'cameras only'], ['APOLOGY RATE', 1, 'never'], ['TOP SPEED', 6, 'next year']] },
  zoox: { perk: 'CARPOOL: 3 FARES AT ONCE', price: '$22.00', eta: '3 min, either way', stats: [['LIDAR COUNT', 4, '4 corners'], ['APOLOGY RATE', 3, 'both ends'], ['TOP SPEED', 3, 'toasty']] },
  apollo: { perk: 'BULLDOZER: TRAFFIC BOUNCES OFF', price: '$4.80', eta: '1 min', stats: [['LIDAR COUNT', 5, 'a crown'], ['APOLOGY RATE', 0, 'n/a'], ['TOP SPEED', 4, 'relentless']] },
};

const btn = (act: Act, text: string) => `<span class="prompt">${key(act)}${text}</span>`;

// A sticker button for touch screens; tapping it acts like the pad button it stands for.
export const tapButton = (action: 'confirm' | 'back' | 'alt' | 'restart', text: string, kind = '') =>
  `<button type="button" class="tap-btn ${kind}" data-tap="${action}">${text}</button>`;

const LOGO = `<h1 class="logo">CRAZY<span>CLANKERS</span></h1>`;

// Painted key art behind the title, a different one each visit.
const KEYART = ['jump', 'rank', 'chaos'];
let keyartIndex = 0; // the boot screen (index.html) shows 'jump', so the first title matches it

export function titleHTML(padName: string) {
  const art = KEYART[keyartIndex++ % KEYART.length];
  return `
    <div class="menu title-screen">
      <img class="keyart" src="/keyart/${art}.avif" alt="">
      <div class="logo-block">${LOGO}<div class="tag">You are AGI. Drive like it.</div></div>
      <div class="press-start" data-tap="confirm">${phrase(`PRESS ${glyph('a', 'A')} TO START`, `PRESS ${keycap('Enter')} TO START`, 'TAP TO START')}</div>
      <button class="radio-menu-button" data-radio-open>${key('radio')} Radio</button>
      <div class="corner-prompts pad-only">${btn('alt', 'HOW TO PLAY')}${btn('back', 'OPTIONS')}</div>
      <div class="corner-prompts tap-row touch-only">${tapButton('alt', 'HOW TO PLAY')}${tapButton('back', 'OPTIONS')}</div>
      <div class="pad-note">${padName ? `🎮 ${padName}` : 'Press any button on a controller to use it.'}</div>
    </div>`;
}

export { btn };

export function howToHTML() {
  return `
    <div class="howto" data-tap="back">
      <b>HOW TO PLAY</b>
      <div class="pad-only"><b>Gas</b> RT / W · <b>Brake / reverse</b> LT / S · <b>Steer</b> stick / A D</div>
      <div class="pad-only"><b>Drift</b> B or RB / Space (hold) · <b>Hop</b> A / E · <b>Pause</b> Start / Esc</div>
      <div class="pad-only"><b>Radio</b> T / LB: next station · N / X: skip track · M / X in menus: stations</div>
      <div class="pad-only"><b>Launch Mode</b> hold handbrake + gas (stopped or drifting), release the handbrake</div>
      <div class="touch-only"><b>Steer</b> drag sideways on the left · <b>Gas · Brake · Drift · Hop</b> on the right</div>
      <div class="touch-only"><b>Radio</b> tap the station sticker: next · hold it, drag to a station, let go</div>
      <div class="touch-only"><b>Launch Mode</b> hold DRIFT + GAS (stopped or drifting), let go of DRIFT</div>
      <div>Stop in a ring to pick up. Stop in the beam to drop off.</div>
      <div>Every passenger wants something: speed, air, drifts, close calls, chaos or a smooth ride. Give it to them for up to five stars. Stars set your tip and your <b>rating</b>; so do crashes. Below 4.00 you're deactivated.</div>
    </div>`;
}

export function pickerHTML(selected: number, thumbs: Record<string, string>) {
  const rows = CABS.map((c, i) => {
    const card = CARDS[c.id];
    const sel = i === selected;
    return `
      <div class="cab-row${sel ? ' selected' : ''}" data-cab="${i}">
        ${sel ? '<span class="sel-tab">SELECTED</span>' : ''}
        <img src="${thumbs[c.id] ?? ''}" alt="">
        <div class="cab-info">
          <div class="cab-line"><b>${c.name}</b><span class="price">${card.price}</span><span class="eta">${card.eta}</span></div>
          ${sel ? `<div class="cab-tagline">${c.tagline}</div>` : ''}
          ${sel && card.perk ? `<div class="cab-perk">★ ${card.perk}</div>` : ''}
        </div>
      </div>`;
  }).join('');
  const card = CARDS[CABS[selected].id];
  const stats = card.stats.map(([label, n, value], k) => `
      <div class="stat"><span class="stat-label">${label}</span>
        <span class="cells c${k}">${Array.from({ length: 6 }, (_, i) => `<i class="${i < n ? 'on' : ''}"></i>`).join('')}</span>
        <span class="stat-value">${value}</span></div>`).join('');
  return `
    <div class="menu picker-screen">
      <div class="logo-block small">${LOGO}</div>
      <div class="inspect-tag pad-only">(R-STICK) INSPECT</div>
      <div class="picker-panel">
        <div class="surge">SURGE<b>3.2x</b></div>
        <h2>CHOOSE YOUR AUTONOMOUS VEHICLE</h2>
        <div class="cab-list">${rows}</div>
        <div class="stats">${stats}</div>
        <div class="confirm" data-tap="confirm"><span class="pad-only">${btn('confirm', 'CONFIRM CAB')}</span><span class="touch-only prompt">DRIVE ▶</span></div>
      </div>
      ${tapButton('back', '◀ BACK', 'corner-back touch-only')}
      <div class="prompt-strip pad-only">${btn('choose', 'CHOOSE')}${btn('confirm', 'DRIVE')}${btn('back', 'BACK')}</div>
    </div>`;
}

// Manga speed-line burst when you commit to a cab.
export function burst() {
  const el = document.createElement('div');
  el.className = 'burst';
  document.body.appendChild(el);
  setTimeout(() => el.remove(), 700);
}

// Fit the picker panel to the screen: measure how tall its content really is, and if that's
// more than the room available, scale the whole panel down just enough (any screen, any perk
// text, any language). Phones held sideways (max-height: 500px) have their own layout.
export function fitPicker() {
  const panel = document.querySelector<HTMLElement>('.picker-panel');
  if (!panel) return;
  panel.style.removeProperty('--pfit');
  panel.style.removeProperty('height');
  panel.style.removeProperty('bottom');
  if (matchMedia('(max-height: 500px)').matches) return;
  panel.classList.add('measure');
  const need = panel.scrollHeight + 16; // plus a little for margins the measure misses
  panel.classList.remove('measure');
  const room = innerHeight * 0.86; // top 4%, bottom 10%
  if (need <= room) return;
  const fit = Math.max(0.55, room / need);
  panel.style.setProperty('--pfit', fit.toFixed(3));
  panel.style.height = `${room / fit}px`;
  panel.style.bottom = 'auto';
}
