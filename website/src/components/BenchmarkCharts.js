// Charts for docs/BENCHMARK.mdx. The numbers are the page's own tables (aggregates of the frozen benchmark); every chart
// sits next to its table, so hiding graphics loses nothing. pencilmark in the site accent, other graders in grey.
import React, {useEffect, useRef} from 'react';
import {useColorMode} from '@docusaurus/theme-common';
import * as Plot from '@observablehq/plot';

const ACCURACY = [  // within-group Spearman of difficulty; ceiling = best any grader can reach (where measured)
  {source: 'sudoku.coach', rho: 0.799, ceiling: 0.98},
  {source: 'grandgames.net', rho: 0.752, ceiling: 0.97},
  {source: 'logic-masters.de', rho: 0.721, ceiling: null},
  {source: 'fed-sudoku.eu', rho: 0.67, ceiling: 0.99},
  {source: 'Wang 2024', rho: 0.663, ceiling: null},
  {source: 'sudoku.today', rho: 0.608, ceiling: 0.75},
];

const GRADERS = [  // same puzzles, within-group Spearman
  ...[['pencilmark', 0.67], ['Andrew Stuart', 0.594], ['Rangsk', 0.357], ['HoDoKu', 0.326], ['Sudoku Explainer', 0.291]]
    .map(([grader, rho]) => ({set: 'fed-sudoku.eu classics', grader, rho})),
  ...[['pencilmark', 0.663], ['Andrew Stuart', 0.498], ['Rangsk', 0.347], ['HoDoKu', 0.403], ['Sudoku Explainer', 0.475]]
    .map(([grader, rho]) => ({set: 'Wang 2024 classics', grader, rho})),
];

const COVERAGE = [[10, 93.9], [30, 96.4], [60, 97.4], [120, 98.2], [300, 98.8]].map(([s, pct]) => ({s, pct}));

function colours() {
  const css = getComputedStyle(document.documentElement);
  return {
    ink: css.getPropertyValue('--ifm-font-color-base').trim() || 'currentColor',
    accent: css.getPropertyValue('--ifm-color-primary').trim(),
    grey: css.getPropertyValue('--ifm-color-emphasis-500').trim() || '#999',
  };
}

function Chart({build, label}) {
  const ref = useRef(null);
  const {colorMode} = useColorMode();
  useEffect(() => {
    const chart = build(colours());
    ref.current.replaceChildren(chart);
    return () => chart.remove();
  }, [colorMode]);
  return <figure className="pm-graphic pm-chart" ref={ref} aria-label={label} />;
}

const base = (ink) => ({style: {background: 'transparent', color: ink, fontSize: '12px'}, width: 640});

export function AccuracyChart() {
  return <Chart label="Within-group rank correlation of difficulty with human solve times, per source" build={({ink, accent}) =>
    Plot.plot({
      ...base(ink), height: 240, marginLeft: 120, marginBottom: 40,
      x: {domain: [0, 1], labelOffset: 36, label: 'Spearman with human times (within groups) →', grid: true},
      y: {label: null, domain: ACCURACY.map((d) => d.source)},
      marks: [
        Plot.barX(ACCURACY, {x: 'rho', y: 'source', fill: accent, tip: true}),
        Plot.tickX(ACCURACY.filter((d) => d.ceiling), {x: 'ceiling', y: 'source', stroke: ink, strokeWidth: 2}),
        Plot.text(ACCURACY, {x: 'rho', y: 'source', text: (d) => d.rho.toFixed(2), dx: -16, fill: 'white'}),
      ],
      caption: 'Bars: pencilmark. Black ticks: noise ceiling, the best any grader can reach on that source.',
    })} />;
}

export function GradersChart() {
  return <Chart label="pencilmark against other graders on the same classics" build={({ink, accent, grey}) =>
    Plot.plot({
      ...base(ink), height: 260, marginLeft: 120, marginRight: 150,
      fy: {label: null}, y: {label: null, domain: ['pencilmark', 'Andrew Stuart', 'Sudoku Explainer', 'HoDoKu', 'Rangsk']},
      x: {domain: [0, 0.8], label: 'Spearman with human times (within groups) →', grid: true},
      marks: [
        Plot.ruleY(GRADERS, {y: 'grader', fy: 'set', x1: 0, x2: 'rho', stroke: grey, strokeOpacity: 0.5}),
        Plot.dot(GRADERS, {x: 'rho', y: 'grader', fy: 'set', r: 5, tip: true,
                           fill: (d) => (d.grader === 'pencilmark' ? accent : grey)}),
      ],
    })} />;
}

export function CoverageChart() {
  return <Chart label="Share of puzzles graded within a time limit" build={({ink, accent}) =>
    Plot.plot({
      ...base(ink), height: 220,
      x: {type: 'log', label: 'time limit (s, log scale) →', ticks: [10, 30, 60, 120, 300]},
      y: {domain: [90, 100], label: '↑ graded within the limit (%)', grid: true},
      marks: [
        Plot.line(COVERAGE, {x: 's', y: 'pct', stroke: accent, strokeWidth: 2.5}),
        Plot.dot(COVERAGE, {x: 's', y: 'pct', fill: accent, r: 4, tip: true}),
        Plot.text(COVERAGE, {x: 's', y: 'pct', text: (d) => `${d.pct}%`, dy: -12, fill: ink}),
      ],
    })} />;
}
