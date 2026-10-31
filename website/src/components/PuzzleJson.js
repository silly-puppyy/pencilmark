// A puzzle drawn next to its JSON (docs/examples/<name>.json, drawn by tools/gen_swatches.py with row / column numbers).
// Hover a rule's line in the JSON and its drawing stands out on the board; hover a drawn rule and its line lights up.
// Every element the renderer draws for rules[i] carries data-rule="i", and the canonical JSON has one rule per line in
// the same order, so the two map by index.
import React, {useEffect, useMemo, useRef, useState} from 'react';
import {useColorMode} from '@docusaurus/theme-common';
import useBaseUrl from '@docusaurus/useBaseUrl';

// line number -> rule index, for the canonical pretty text (one rule per line after "rules": [)
function ruleLines(text) {
  const map = {};
  let inRules = false;
  let k = 0;
  text.split('\n').forEach((line, i) => {
    if (line.includes('"rules": [')) { inRules = true; return; }
    if (inRules && line.trimStart().startsWith('{')) map[i] = k++;
  });
  return map;
}

export default function PuzzleJson({name, caption}) {
  const {colorMode} = useColorMode();
  const [svg, setSvg] = useState({light: '', dark: ''});
  const [text, setText] = useState('');
  const [active, setActive] = useState(null);
  const id = useRef(`pj-${name.replace(/\W/g, '')}`).current;
  const base = useBaseUrl(`/img/swatches/example-${name}`);
  useEffect(() => {
    Promise.all([`${base}-board.svg`, `${base}-board-dark.svg`, `${base}.json`].map((u) => fetch(u).then((r) => r.text())))
      .then(([light, dark, json]) => { setSvg({light, dark}); setText(json); })
      .catch(() => {});
  }, [base]);
  const lines = useMemo(() => text.split('\n'), [text]);
  const map = useMemo(() => ruleLines(text), [text]);
  const onBoard = (e) => {
    const el = e.target.closest && e.target.closest('[data-rule]');
    setActive(el ? Number(el.getAttribute('data-rule')) : null);
  };
  const css = active === null ? '' : `#${id} [data-rule]:not([data-rule="${active}"]) { opacity: 0.18; }
    #${id} [data-rule="${active}"] { filter: drop-shadow(0 0 2px var(--ifm-color-primary)); }`;
  return (
    <figure className="pm-puzzle-json" id={id}>
      <style>{css}</style>
      <div className="pm-graphic pm-puzzle-json-board" onMouseMove={onBoard} onMouseLeave={() => setActive(null)}
           dangerouslySetInnerHTML={{__html: colorMode === 'dark' ? svg.dark : svg.light}}/>
      <pre className="pm-puzzle-json-text">
        {lines.map((line, i) => (
          <span key={i} className={map[i] !== undefined && map[i] === active ? 'pm-pj-line pm-pj-on' : 'pm-pj-line'}
                onMouseEnter={() => setActive(map[i] !== undefined ? map[i] : null)}
                onMouseLeave={() => setActive(null)}>{line + '\n'}</span>
        ))}
      </pre>
      {caption && <figcaption>{caption}</figcaption>}
    </figure>
  );
}
