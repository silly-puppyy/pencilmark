// Charts for docs/grades/benchmark.mdx. The numbers are the page's own tables (aggregates of the frozen benchmark); every chart
// sits next to its table, so hiding graphics loses nothing. pencilmark in the site accent, other graders in grey.
import React, {useEffect, useRef} from 'react';
import {reserve} from './reserve';
import {useColorMode} from '@docusaurus/theme-common';
import * as Plot from '@observablehq/plot';

// One data set per docs version (a frozen version's page passes version="1.1"; the current docs use the latest)
const ACCURACY_BY = {'1.1': [  // within-group Spearman of difficulty against human times. With a ceiling: the
  // noise-ceiling table's values (the puzzles where players could be split) and its share of the ceiling
  {source: 'sudoku.coach', rho: 0.765, ceiling: 0.98, share: 0.78},
  {source: 'grandgames.net', rho: 0.755, ceiling: 0.97, share: 0.78},
  {source: 'logic-masters.de', rho: 0.721, ceiling: null, share: null},
  {source: 'fed-sudoku.eu', rho: 0.66, ceiling: 0.99, share: 0.67},
  {source: 'Wang 2024', rho: 0.663, ceiling: null, share: null},
  {source: 'sudoku.today', rho: 0.597, ceiling: 0.75, share: 0.87},
], '1.2': [
  {source: 'sudoku.coach', rho: 0.774, ceiling: 0.98, share: 0.79},
  {source: 'grandgames.net', rho: 0.769, ceiling: 0.97, share: 0.79},
  {source: 'logic-masters.de', rho: 0.713, ceiling: null, share: null},
  {source: 'fed-sudoku.eu', rho: 0.697, ceiling: 0.99, share: 0.70},
  {source: 'Wang 2024', rho: 0.653, ceiling: null, share: null},
  {source: 'sudoku.today', rho: 0.611, ceiling: 0.75, share: 0.81},
]};

const graders = (fed, wang, today) => [  // same puzzles, within-group Spearman (the page's comparison table)
  ...[['pencilmark', fed], ['Andrew Stuart', 0.594], ['Rangsk', 0.357], ['HoDoKu', 0.326], ['Sudoku Explainer', 0.291]]
    .map(([grader, rho]) => ({set: 'fed-sudoku.eu classics', grader, rho})),
  ...[['pencilmark', wang], ['Andrew Stuart', 0.498], ['Rangsk', 0.347], ['HoDoKu', 0.403], ['Sudoku Explainer', 0.475]]
    .map(([grader, rho]) => ({set: 'Wang 2024 classics', grader, rho})),
  ...[['pencilmark', today], ['Rangsk', 0.676]].map(([grader, rho]) => ({set: 'sudoku.today variants', grader, rho})),
];
const GRADERS_BY = {'1.1': graders(0.67, 0.663, 0.699), '1.2': graders(0.709, 0.653, 0.722)};
const LATEST = '1.2';

function colours() {
  const css = getComputedStyle(document.documentElement);
  return {
    ink: css.getPropertyValue('--ifm-font-color-base').trim() || 'currentColor',
    accent: css.getPropertyValue('--ifm-color-primary').trim(),
    grey: css.getPropertyValue('--ifm-color-emphasis-500').trim() || '#999',
  };
}

function Chart({build, label, height}) {
  const ref = useRef(null);
  const {colorMode} = useColorMode();
  useEffect(() => {
    const chart = build(colours());
    ref.current.replaceChildren(chart);
    return () => chart.remove();
  }, [colorMode]);
  return <figure className="pm-graphic pm-chart" ref={ref} aria-label={label} style={reserve(height)} />;
}

const base = (ink) => ({style: {background: 'transparent', color: ink, fontSize: '12px'}, width: 640});

export function AccuracyChart({version = LATEST}) {
  // bullet chart: the light bar is the source's ceiling (the best any grader can reach), the dark bar pencilmark
  const rows = ACCURACY_BY[version];
  return <Chart label="pencilmark's rank correlation with human solve times per source, against each source's ceiling" height={310}
    build={({ink, accent, grey}) => Plot.plot({
      ...base(ink), height: 270, marginLeft: 120, marginRight: 150, marginBottom: 40,
      x: {domain: [0, 1], grid: true, labelOffset: 34, label: 'Spearman with human times (within groups) →'},
      y: {label: null, domain: rows.map((d) => d.source), padding: 0.25},
      marks: [
        Plot.barX(rows.filter((d) => d.ceiling), {x: 'ceiling', y: 'source', fill: grey, fillOpacity: 0.28, rx: 3,
                                                  title: (d) => `ceiling ${d.ceiling}`}),
        Plot.barX(rows, {x: 'rho', y: 'source', fill: accent, insetTop: 5, insetBottom: 5, rx: 2,
                         title: (d) => `${d.source}: ${d.rho}` + (d.ceiling ? ` of a possible ${d.ceiling}` : '')}),
        Plot.text(rows, {x: 1, y: 'source', dx: 8, textAnchor: 'start', fill: ink,
                         text: (d) => (d.share ? `${d.rho.toFixed(2)} · ${Math.round(100 * d.share)}% of ceiling` : `${d.rho.toFixed(2)} · no ceiling`)}),
      ],
      caption: 'Narrow bar: pencilmark. Wide pale bar: the ceiling, the best any grader can reach on that source, where players can be split in two; the share is averaged over groups.',
    })} />;
}

export function GradersChart({version = LATEST}) {
  const GRADERS = GRADERS_BY[version];
  // lollipops, one row per grader inside each puzzle set; pencilmark in the accent; every value written beside its dot
  const sets = ['fed-sudoku.eu classics', 'Wang 2024 classics', 'sudoku.today variants'];
  const order = ['pencilmark', 'Andrew Stuart', 'Sudoku Explainer', 'HoDoKu', 'Rangsk'];
  const fill = (accent, grey) => (d) => (d.grader === 'pencilmark' ? accent : grey);
  return <Chart label="pencilmark against other graders on the same puzzles" height={430} build={({ink, accent, grey}) =>
    Plot.plot({
      ...base(ink), height: 430, marginLeft: 120, marginRight: 50, marginTop: 24, marginBottom: 40,
      x: {domain: [0, 0.8], grid: true, labelOffset: 34, label: 'Spearman with human times (within groups) →'},
      fy: {domain: sets, label: null, padding: 0.22, axis: null},
      y: {domain: order, label: null},
      marks: [
        Plot.text(sets, {fy: (d) => d, text: (d) => d, frameAnchor: 'top-right', dy: -12, fontWeight: 650, fill: ink}),
        Plot.ruleY(GRADERS, {fy: 'set', y: 'grader', x1: 0, x2: 'rho', stroke: fill(accent, grey), strokeOpacity: 0.6}),
        Plot.dot(GRADERS, {fy: 'set', y: 'grader', x: 'rho', r: 5, fill: fill(accent, grey), stroke: 'none', tip: true,
                           title: (d) => `${d.grader}, ${d.set}: ${d.rho}`}),
        Plot.text(GRADERS, {fy: 'set', y: 'grader', x: 'rho', text: (d) => d.rho.toFixed(2), dx: 9, textAnchor: 'start',
                            fill: ink, fontWeight: (d) => (d.grader === 'pencilmark' ? 650 : 400)}),
      ],
    })} />;
}
