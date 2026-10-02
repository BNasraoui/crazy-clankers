import { CABS } from './models';
import { glyph, key, keycap, phrase, type Act } from './prompts';
import { lang, t, type Key } from './i18n';
import { levelFill, levelOf, progressOf } from './progress';

// Title screen and cab picker overlays (the 3D taxi rank sits behind them).

// stats: [label key, cells 0..6, value key]. Every word is in i18n.ts under cab.<id>.*
interface CabCard { stats: [Key, number, Key][]; perk?: boolean }
const STATS: Key[] = ['stat.lidar', 'stat.apology', 'stat.speed'];
const stats = (id: string, cells: number[]) => cells.map((n, k) => [STATS[k], n, `cab.${id}.stat${k}` as Key] as [Key, number, Key]);
const CARDS: Record<string, CabCard> = {
  wayfarer: { perk: true, stats: stats('wayfarer', [6, 6, 3]) },
  cybercab: { perk: true, stats: stats('cybercab', [0, 1, 6]) },
  zoox: { perk: true, stats: stats('zoox', [4, 3, 3]) },
  apollo: { perk: true, stats: stats('apollo', [5, 0, 4]) },
};
const cabText = (id: string, field: 'name' | 'tagline' | 'perk' | 'price' | 'eta') => t(`cab.${id}.${field}` as Key);

const btn = (act: Act, text: string) => `<span class="prompt">${key(act)}${text}</span>`;

// A sticker button for touch screens; tapping it acts like the pad button it stands for.
export const tapButton = (action: 'confirm' | 'back' | 'alt' | 'restart' | 'board', text: string, kind = '') =>
  `<button type="button" class="tap-btn ${kind}" data-tap="${action}">${text}</button>`;

// The logo stays English; in Chinese a subtitle sits under it.
const logo = () => `<h1 class="logo">CRAZY<span>CLANKERS</span></h1>${t('logo.sub') ? `<div class="logo-sub">${t('logo.sub')}</div>` : ''}`;

// Painted key art behind the title, a different one each visit.
const KEYART = ['jump', 'rank', 'chaos'];
let keyartIndex = 0; // the boot screen (index.html) shows 'jump', so the first title matches it

export function titleHTML(padName: string) {
  const art = KEYART[keyartIndex++ % KEYART.length];
  return `
    <div class="menu title-screen">
      <img class="keyart" src="/keyart/${art}.avif" alt="">
      <div class="logo-block">${logo()}<div class="tag">${t('tagline')}</div></div>
      <div class="press-start" data-tap="confirm">${phrase(t('title.pressPad', { a: glyph('a', 'A') }), t('title.pressKb', { key: keycap('Enter') }), t('title.tap'))}</div>
      <button class="radio-menu-button" data-radio-open>${key('radio')} ${t('menu.radio')}</button>
      <div class="lang-switch" data-lang role="button" aria-label="Language / 语言"><b class="${lang() === 'en' ? 'on' : ''}">EN</b><b class="${lang() === 'zh' ? 'on' : ''}">中文</b><span class="k-kb">${keycap('L')}</span></div>
      <div class="corner-prompts pad-only">${btn('board', t('title.board'))}${btn('alt', t('title.howTo'))}${btn('back', t('title.options'))}</div>
      <div class="corner-prompts tap-row touch-only">${tapButton('board', t('title.board'))}${tapButton('alt', t('title.howTo'))}${tapButton('back', t('title.options'))}</div>
      <div class="pad-note">${padName ? `🎮 ${padName}` : t('title.padNote')}</div>
    </div>`;
}

export { btn };

export function howToHTML() {
  return `
    <div class="howto" data-tap="back">
      <b>${t('how.title')}</b>
      <div class="pad-only">${t('how.pad1')}</div>
      <div class="pad-only">${t('how.pad2')}</div>
      <div class="pad-only">${t('how.pad3')}</div>
      <div class="pad-only">${t('how.pad4')}</div>
      <div class="touch-only">${t('how.touch1')}</div>
      <div class="touch-only">${t('how.touch2')}</div>
      <div class="touch-only">${t('how.touch3')}</div>
      <div>${t('how.rings')}</div>
      <div>${t('how.wants')}</div>
    </div>`;
}

export function pickerHTML(selected: number, thumbs: Record<string, string>) {
  const rows = CABS.map((c, i) => {
    const card = CARDS[c.id];
    const sel = i === selected;
    return `
      <div class="cab-row${sel ? ' selected' : ''}" data-cab="${i}">
        ${sel ? `<span class="sel-tab">${t('picker.selected')}</span><i class="xpbar" style="--fill: ${levelFill(progressOf(c.id).xp)}"></i>` : ''}
        <img src="${thumbs[c.id] ?? ''}" alt="">
        <div class="cab-info">
          <div class="cab-line"><b>${cabText(c.id, 'name')}</b><span class="lv">${t('picker.level', { n: levelOf(progressOf(c.id).xp) })}</span><span class="price">${cabText(c.id, 'price')}</span><span class="eta">${cabText(c.id, 'eta')}</span></div>
          ${sel ? `<div class="cab-tagline">${cabText(c.id, 'tagline')}</div>` : ''}
          ${sel && card.perk ? `<div class="cab-perk">★ ${cabText(c.id, 'perk')}</div>` : ''}
        </div>
      </div>`;
  }).join('');
  const card = CARDS[CABS[selected].id];
  const statRows = card.stats.map(([label, n, value], k) => `
      <div class="stat"><span class="stat-label">${t(label)}</span>
        <span class="cells c${k}">${Array.from({ length: 6 }, (_, i) => `<i class="${i < n ? 'on' : ''}"></i>`).join('')}</span>
        <span class="stat-value">${t(value)}</span></div>`).join('');
  return `
    <div class="menu picker-screen">
      <div class="logo-block small">${logo()}</div>
      <div class="inspect-tag pad-only">${t('picker.inspect')}</div>
      <div class="picker-panel">
        <div class="surge">${t('picker.surge')}<b>3.2x</b></div>
        <h2>${t('picker.title')}</h2>
        <div class="cab-list">${rows}</div>
        <div class="stats">${statRows}</div>
        <div class="confirm" data-tap="confirm"><span class="pad-only">${btn('confirm', t('picker.confirm'))}</span><span class="touch-only prompt">${t('picker.driveTap')}</span></div>
      </div>
      ${tapButton('back', t('picker.backTap'), 'corner-back touch-only')}
      <div class="prompt-strip pad-only">${btn('choose', t('picker.choose'))}${btn('confirm', t('picker.drive'))}${btn('back', t('picker.back'))}</div>
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
