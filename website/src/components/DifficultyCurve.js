// Chart of the difficulty map (src/pencilmark/card_score.py): difficulty against effort per empty cell (linear axis), from the
// shipped parameters (data/card_score.json "map"). Drawn with Observable Plot in the site's colours; redrawn when the
// colour mode changes. The page shows the same numbers in text, so the chart is optional (.pm-graphic).
import React, {useEffect, useRef} from 'react';
import {useColorMode} from '@docusaurus/theme-common';
import * as Plot from '@observablehq/plot';

const A = 0.8257774766330751;
const R0 = 2.117172767264659;
const W = 0.3;

const softplus = (r) => A * W * (Math.log1p(Math.exp(-Math.abs((r - R0) / W))) + Math.max((r - R0) / W, 0));

// r where the softplus reaches 2, by bisection (the same rule as card_score._r_at)
function rAt(score) {
  let lo = R0 - 50, hi = R0 + 50;
  for (let i = 0; i < 100; i++) {
    const mid = (lo + hi) / 2;
    if (softplus(mid) < score) lo = mid; else hi = mid;
  }
  return (lo + hi) / 2;
}

const R2 = rAt(2);
export const difficulty = (r) => (softplus(r) >= 2 ? softplus(r) : 2 * Math.exp((A * (r - R2)) / 2));

export default function DifficultyCurve() {
  const ref = useRef(null);
  const {colorMode} = useColorMode();
  useEffect(() => {
    const css = getComputedStyle(document.documentElement);
    const ink = css.getPropertyValue('--ifm-font-color-base').trim() || 'currentColor';
    const accent = css.getPropertyValue('--ifm-color-primary').trim();
    // x: effort per empty cell, as a multiple of the effort at difficulty 2 (linear, so the curve shows its real shape);
    // up to difficulty 8, where one point already costs 2.6 times the effort
    const pts = [];
    for (let r = R2 - 8; difficulty(r) <= 8; r += 0.01) {
      pts.push({x: 5 ** ((r - R2) / 2), y: difficulty(r)});
    }
    const chart = Plot.plot({
      width: 640, height: 300, marginLeft: 44, marginBottom: 40,
      style: {background: 'transparent', color: ink, fontSize: '12px'},
      x: {label: 'effort per empty cell (1 = the effort of a difficulty 2 puzzle) →', grid: true},
      y: {label: '↑ difficulty', domain: [0, 8], grid: true},
      marks: [
        Plot.ruleY([2], {stroke: ink, strokeOpacity: 0.35, strokeDasharray: '4 3'}),
        Plot.line(pts, {x: 'x', y: 'y', stroke: accent, strokeWidth: 2.5}),
        Plot.tip(pts, Plot.pointerX({x: 'x', y: 'y', title: (d) => `difficulty ${d.y.toFixed(2)}\neffort ×${d.x.toPrecision(2)}`})),
      ],
    });
    ref.current.replaceChildren(chart);
    return () => chart.remove();
  }, [colorMode]);
  return <figure className="pm-graphic pm-chart" ref={ref} aria-label="Difficulty against effort per empty cell" />;
}
