// The reader's graphics choice (stored by GraphicsToggle; default: shown). An inline script in the page head
// (docusaurus.config.js headTags) applies it before the first paint; this keeps it applied after client navigation.
import ExecutionEnvironment from '@docusaurus/ExecutionEnvironment';

export const KEY = 'pm-graphics';

export function graphicsOn() {
  try { return localStorage.getItem(KEY) !== 'off'; } catch (e) { return true; }
}

if (ExecutionEnvironment.canUseDOM) {
  document.documentElement.dataset.graphics = graphicsOn() ? 'on' : 'off';
}
