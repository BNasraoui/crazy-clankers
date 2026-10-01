import { CABS } from './models';

// Title screen and cab picker overlays (the 3D taxi rank sits behind them).

interface CabCard { price: string; eta: string; stats: [string, number, string][] } // [label, cells 0..6, value]
const CARDS: Record<string, CabCard> = {
  cab: { price: '$14.20', eta: '2 min', stats: [['LIDAR COUNT', 3, '1 puck'], ['APOLOGY RATE', 2, '3 / min'], ['TOP SPEED', 4, 'brisk']] },
  wayfarer: { price: '$31.80', eta: '4 min', stats: [['LIDAR COUNT', 6, '29'], ['APOLOGY RATE', 6, '12 / min'], ['TOP SPEED', 3, 'polite']] },
  cybercab: { price: '$9.99', eta: 'ETA: TBC', stats: [['LIDAR COUNT', 0, 'cameras only'], ['APOLOGY RATE', 1, 'never'], ['TOP SPEED', 6, 'next year']] },
  zoox: { price: '$22.00', eta: '3 min, either way', stats: [['LIDAR COUNT', 4, '4 corners'], ['APOLOGY RATE', 3, 'both ends'], ['TOP SPEED', 3, 'toasty']] },
  apollo: { price: '$4.80', eta: '1 min', stats: [['LIDAR COUNT', 5, 'a crown'], ['APOLOGY RATE', 0, 'n/a'], ['TOP SPEED', 4, 'relentless']] },
};

const btn = (k: 'A' | 'B' | 'Y' | 'pad', text: string) =>
  `<span class="prompt"><i class="glyph ${k === 'pad' ? 'pad' : k.toLowerCase()}">${k === 'pad' ? '✚' : k}</i>${text}</span>`;

const LOGO = `<h1 class="logo">CRAZY<span>CLANKERS</span></h1>`;

// Painted key art behind the title, a different one each visit.
const KEYART = ['jump', 'rank', 'chaos'];
let keyartIndex = Math.floor(Math.random() * KEYART.length);

export function titleHTML(padName: string) {
  const art = KEYART[keyartIndex++ % KEYART.length];
  return `
    <div class="menu title-screen">
      <img class="keyart" src="/keyart/${art}.jpg" alt="">
      <div class="logo-block">${LOGO}<div class="tag">You are AGI. Drive like it.</div></div>
      <div class="press-start">PRESS <i class="glyph a">A</i> TO START</div>
      <div class="corner-prompts">${btn('Y', 'HOW TO PLAY')}${btn('B', 'OPTIONS')}</div>
      <div class="pad-note">${padName ? `🎮 ${padName}` : 'Press any button on a controller to use it.'}</div>
    </div>`;
}

export function howToHTML() {
  return `
    <div class="howto">
      <b>HOW TO PLAY</b>
      <div><b>Gas</b> RT / W · <b>Brake / reverse</b> LT / S · <b>Steer</b> stick / A D</div>
      <div><b>Drift</b> B or RB / Space (hold) · <b>Hop</b> A / E · <b>Pause</b> Start / Esc</div>
      <div><b>Launch Mode</b> hold handbrake + gas (stopped or drifting), release the handbrake</div>
      <div>Stop in a ring to pick up. Stop in the beam to drop off.</div>
      <div>Jumps, near misses, drifts and smashing junk earn tips but cost <b>rating</b>. Below 4.00 you're deactivated.</div>
    </div>`;
}

export function pickerHTML(selected: number, thumbs: Record<string, string>) {
  const rows = CABS.map((c, i) => {
    const card = CARDS[c.id];
    const sel = i === selected;
    return `
      <div class="cab-row${sel ? ' selected' : ''}">
        ${sel ? '<span class="sel-tab">SELECTED</span>' : ''}
        <img src="${thumbs[c.id] ?? ''}" alt="">
        <div class="cab-info">
          <div class="cab-line"><b>${c.name}</b><span class="price">${card.price}</span><span class="eta">${card.eta}</span></div>
          ${sel ? `<div class="cab-tagline">${c.tagline}</div>` : ''}
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
      <div class="inspect-tag">(R-STICK) INSPECT</div>
      <div class="picker-panel">
        <div class="surge">SURGE<b>3.2x</b></div>
        <h2>CHOOSE YOUR AUTONOMOUS VEHICLE</h2>
        <div class="cab-list">${rows}</div>
        <div class="stats">${stats}</div>
        <div class="confirm">${btn('A', 'CONFIRM CAB')}</div>
      </div>
      <div class="prompt-strip">${btn('pad', 'CHOOSE')}${btn('A', 'DRIVE')}${btn('B', 'BACK')}</div>
    </div>`;
}

// Manga speed-line burst when you commit to a cab.
export function burst() {
  const el = document.createElement('div');
  el.className = 'burst';
  document.body.appendChild(el);
  setTimeout(() => el.remove(), 700);
}
