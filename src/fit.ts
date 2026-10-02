// Sizes for small screens (a phone on its side): the HUD and menus are drawn at the
// 1280x800 design size and scaled to fit (--ui, never below 0.5 so text stays readable),
// and the touch buttons shrink with the screen height (--tbs). Only short screens use
// them (see style.css, max-height: 500px), so desktop and the Steam Deck are unchanged.
export function fitUi() {
  const root = document.documentElement.style;
  root.setProperty('--ui', Math.min(1, Math.max(0.5, Math.min(innerHeight / 800, innerWidth / 1280) * 1.45)).toFixed(3));
  root.setProperty('--tbs', Math.min(1, Math.max(0.62, innerHeight / 420)).toFixed(3));
}
addEventListener('resize', fitUi);
addEventListener('orientationchange', fitUi);
fitUi();
