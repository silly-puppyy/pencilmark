// A small external link to another site's explanation, shown as that site's icon with an arrow (the icons are made by
// tools/site_icons.py). Used in the rule family tables; docs/TECHNIQUES.md writes the same markup directly.
import React from 'react';
import useBaseUrl from '@docusaurus/useBaseUrl';

const SITES = {
  'sudokuvariants.com': ['sudokuvariants.com', 'sudokuvariants.png'],
  'artisanalsudoku.substack.com': ['Artisanal Sudoku', 'artisanalsudoku.png'],
  'www.sudokuwiki.org': ['sudokuwiki.org', 'sudokuwiki.png'],
  'sudoku.coach': ['sudoku.coach', 'sudokucoach.png'],
};

export default function SiteLink({href}) {
  const host = new URL(href).host;
  const [title, icon] = SITES[host] || [host, null];
  const src = useBaseUrl(`/img/sites/${icon}`);
  return (
    <a href={href} title={title} className="pm-site-link">
      {icon ? <img src={src} alt={title} className="pm-site"/> : title}
    </a>
  );
}
