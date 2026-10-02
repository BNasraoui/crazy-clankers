// Sizes for screens smaller than the 1280x800 design. The HUD and menus are drawn at the
// design size and scaled to fit:
//  --ui   phones on their side (style.css, max-height: 500px): scaled a little larger than exact
//         (x1.45), never below 0.5, so text stays readable on a small screen;
//  --uid  short desktop windows: exact scale (never below 0.55); html.scaled turns it on.
// --tbs shrinks the touch buttons with the screen height. At 1280x800 and up nothing changes.
export function fitUi() {
  const root = document.documentElement;
  const fit = Math.min(innerHeight / 800, innerWidth / 1280);
  root.style.setProperty('--ui', Math.min(1, Math.max(0.5, fit * 1.45)).toFixed(3));
  const uid = Math.min(1, Math.max(0.55, fit));
  root.style.setProperty('--uid', uid.toFixed(3));
  root.classList.toggle('scaled', uid < 0.97 && innerHeight > 500);
  root.style.setProperty('--tbs', Math.min(1, Math.max(0.62, innerHeight / 420)).toFixed(3));
}
addEventListener('resize', fitUi);
addEventListener('orientationchange', fitUi);
fitUi();
