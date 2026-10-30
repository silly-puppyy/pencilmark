// Applies the reader's graphics choice before the page paints (stored by GraphicsToggle; default: shown).
import ExecutionEnvironment from '@docusaurus/ExecutionEnvironment';

export const KEY = 'pm-graphics';

export function graphicsOn() {
  try { return localStorage.getItem(KEY) !== 'off'; } catch (e) { return true; }
}

if (ExecutionEnvironment.canUseDOM) {
  document.documentElement.dataset.graphics = graphicsOn() ? 'on' : 'off';
}
