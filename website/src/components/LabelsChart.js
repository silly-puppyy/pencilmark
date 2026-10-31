// Other sites' difficulty labels on pencilmark's scale (docs/USAGE.mdx): one small bar chart per site, bars at the
// median difficulty, whiskers over the interquartile range where it was measured. A button switches to the table;
// with graphics hidden (navbar switch) the table shows instead of the charts.
import React, {useEffect, useRef, useState} from 'react';
import {useColorMode} from '@docusaurus/theme-common';
import * as Plot from '@observablehq/plot';

// medians (and quartiles where measured) of pencilmark's difficulty per site label; aggregates of the benchmark sets
const LABELS = [
  {site: 'fed-sudoku.eu', label: 'easy', median: 3.9, q1: 3.4, q3: 4.3},
  {site: 'fed-sudoku.eu', label: 'medium', median: 5.1, q1: 4.6, q3: 5.9},
  {site: 'fed-sudoku.eu', label: 'hard', median: 6.5, q1: 6.2, q3: 7.0},
  ...[0.6, 1.7, 2.8, 3.7, 5.2, 5.8, 6.1, 6.7, 7.3, 8.7, 11.5, 11.9].map((m, i) => (
    {site: 'sudoku.coach', label: `level ${i}`, median: m})),
  {site: 'Logic Masters', label: '1 star', median: 8.8, q1: 6.3, q3: 10.1},
  {site: 'Logic Masters', label: '2 stars', median: 11.1, q1: 10.1, q3: 12.6},
  {site: 'Logic Masters', label: '3 stars', median: 13.0, q1: 11.5, q3: 13.7},
  {site: 'Logic Masters', label: '4-5 stars', median: 13.8, q1: 12.6, q3: 14.9},
];
const NOTES = {'sudoku.coach': 'classics', 'Logic Masters': 'variants; one star is already hard'};

function SiteChart({site}) {
  const ref = useRef(null);
  const {colorMode} = useColorMode();
  useEffect(() => {
    const css = getComputedStyle(document.documentElement);
    const ink = css.getPropertyValue('--ifm-font-color-base').trim() || 'currentColor';
    const accent = css.getPropertyValue('--ifm-color-primary').trim();
    const rows = LABELS.filter((d) => d.site === site);
    const chart = Plot.plot({
      width: 640, height: 34 + 22 * rows.length, marginLeft: 80, marginRight: 40,
      style: {background: 'transparent', color: ink, fontSize: '12px'},
      x: {domain: [0, 16], grid: true, label: 'pencilmark difficulty →'},
      y: {label: null, domain: rows.map((d) => d.label)},
      marks: [
        Plot.barX(rows, {x: 'median', y: 'label', fill: accent, fillOpacity: 0.85, rx: 3,
                         title: (d) => `${d.label}: median ${d.median}` + (d.q1 ? ` (IQR ${d.q1}–${d.q3})` : '')}),
        Plot.ruleY(rows.filter((d) => d.q1), {y: 'label', x1: 'q1', x2: 'q3', stroke: ink, strokeWidth: 1.5}),
        Plot.text(rows, {x: (d) => d.q3 || d.median, y: 'label', text: (d) => d.median.toFixed(1), dx: 6,
                         textAnchor: 'start', fill: ink}),
      ],
    });
    ref.current.replaceChildren(chart);
    return () => chart.remove();
  }, [colorMode]);
  return (
    <figure className="pm-chart" style={{margin: '0 0 1rem'}}>
      <figcaption style={{fontWeight: 600, marginBottom: 2}}>{site}{NOTES[site] ? ` (${NOTES[site]})` : ''}</figcaption>
      <div ref={ref}/>
    </figure>
  );
}

function Table() {
  return (
    <table>
      <thead><tr><th>Site</th><th>Label</th><th>pencilmark difficulty: median (quartiles)</th></tr></thead>
      <tbody>
        {LABELS.map((d) => (
          <tr key={d.site + d.label}>
            <td>{d.site}</td><td>{d.label}</td>
            <td>{d.median.toFixed(1)}{d.q1 ? ` (${d.q1}–${d.q3})` : ''}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export default function LabelsChart() {
  const [table, setTable] = useState(false);
  const sites = Array.from(new Set(LABELS.map((d) => d.site)));
  return (
    <div>
      <div className={table ? 'pm-alt-hidden' : 'pm-graphic'}>
        {sites.map((s) => <SiteChart key={s} site={s}/>)}
      </div>
      <div className={table ? '' : 'pm-alt-table'}><Table/></div>
      <button type="button" className="button button--sm button--secondary pm-graphic" onClick={() => setTable(!table)}>
        {table ? 'Show the charts' : 'Show the table'}
      </button>
    </div>
  );
}
