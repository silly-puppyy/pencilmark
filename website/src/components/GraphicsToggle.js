// Navbar switch that hides optional graphics (figures and graphic-only table columns marked .pm-graphic) on reference
// pages. Tutorials mark their figures .pm-figure, which stay visible. The choice is kept per reader in localStorage.
import React, {useEffect, useState} from 'react';
import {KEY, graphicsOn} from '@site/src/clientModules/graphics';

export default function GraphicsToggle() {
  const [on, setOn] = useState(true);
  useEffect(() => setOn(graphicsOn()), []);
  const flip = () => {
    const next = !on;
    setOn(next);
    document.documentElement.dataset.graphics = next ? 'on' : 'off';
    try { localStorage.setItem(KEY, next ? 'on' : 'off'); } catch (e) { /* private window: not remembered */ }
  };
  const label = on ? 'Hide graphics' : 'Show graphics';
  return (
    <button type="button" className="clean-btn pm-graphics-toggle" onClick={flip} title={label} aria-label={label}
            aria-pressed={!on}>
      <svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true">
        <rect x="3.5" y="3.5" width="17" height="17" rx="2" fill="none" stroke="currentColor" strokeWidth="1.6"/>
        <path d="M3.5 9.2h17M3.5 14.8h17M9.2 3.5v17M14.8 3.5v17" stroke="currentColor" strokeWidth="1"/>
        {!on && <path d="M4 20 20 4" stroke="currentColor" strokeWidth="1.8"/>}
      </svg>
    </button>
  );
}
