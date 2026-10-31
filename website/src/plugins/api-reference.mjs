// rehype plugin: the reference pages' Markdown patterns (tools/apidoc.py) drawn the way Sphinx autodoc draws them.
//   ### `def name(args)`  + a "[source](...)" paragraph -> a signature box with the source link at its right
//   **Parameters** + a list                            -> a field list (label left, items right)
//   a table with an empty header                       -> a summary table; a word before a cell's link is its kind
//   a paragraph that is only a link to src/..., csrc/... or "source" (a class) -> small, under its heading
//   h4 entries (methods) and what follows them, up to the next h1-h3 -> indented under their class
import {visit} from 'unist-util-visit';

const FIELDS = new Set(['Parameters', 'Returns', 'Yields', 'Raises', 'Fields']);
const text = (n) => (n.type === 'text' ? n.value : (n.children || []).map(text).join(''));
const blank = (n) => n.type === 'text' && !n.value.trim();
const kids = (n) => (n.children || []).filter((c) => !blank(c));
const el = (tagName, className, children) => ({type: 'element', tagName, properties: className ? {className} : {}, children});
const t = (value) => ({type: 'text', value});
const addClass = (n, c) => { n.properties.className = [...(n.properties.className || []), c]; };
const onlyLink = (p) => p && p.tagName === 'p' && kids(p).length === 1 && kids(p)[0].tagName === 'a' ? kids(p)[0] : null;

// "static bool Solver::apply(int c) const" -> ["static bool ", "Solver::apply", "(int c) const"]
function splitSig(s) {
  let i = s.indexOf('(');
  if (i < 0) i = s.length;
  if (/operator$/.test(s.slice(0, i))) i = s.indexOf('(', i + 2);
  const head = s.slice(0, i);
  const j = head.lastIndexOf(' ', head.trimEnd().length - 1) + 1;
  return [head.slice(0, j), head.slice(j), s.slice(i)];
}

function signature(h, next) {
  const [kind, name, rest] = splitSig(text(kids(h)[0]));
  const anchors = h.children.filter((c) => c.type === 'element' && c.tagName === 'a');  // the theme's hash link, if any
  const sig = el('span', ['api-sig'], [
    ...(kind ? [el('span', ['api-kw'], [t(kind)])] : []),
    el('strong', null, [t(name)]),
    ...(rest ? [el('span', ['api-args'], [t(rest)])] : []),
  ]);
  const src = onlyLink(next);
  h.children = [sig, ...(src && text(src) === 'source' ? [{...src, properties: {...src.properties, className: ['api-src']}}] : []), ...anchors];
  addClass(h, 'api-entry');
  return src && text(src) === 'source';
}

function fieldList(p, ul) {
  return el('dl', ['api-fields'], [el('dt', null, [t(text(p))]), el('dd', null, [ul])]);
}

function summaryTable(table) {
  const head = table.children.find((c) => c.tagName === 'thead');
  if (!head || text(head).trim()) return;
  table.children = table.children.filter((c) => c !== head);
  addClass(table, 'api-summary');
  visit(table, 'element', (tr) => {
    if (tr.tagName !== 'tr') return;
    const td = kids(tr)[0];
    const first = td && td.children[0];
    if (first && first.type === 'text' && first.value.trim()) td.children[0] = el('span', ['api-chip'], [t(first.value.trim())]);
  });
}

function rewrite(parent) {
  const out = [];
  const nodes = parent.children;
  for (let i = 0; i < nodes.length; i++) {
    const n = nodes[i];
    if (n.type !== 'element') { out.push(n); continue; }
    let j = i + 1;
    while (j < nodes.length && blank(nodes[j])) j++;
    const next = nodes[j];
    if (/^h[2-4]$/.test(n.tagName) && kids(n).length >= 1 && kids(n)[0].tagName === 'code' && n.tagName !== 'h2') {
      out.push(n);
      if (signature(n, next)) i = j;
    } else if (n.tagName === 'p' && kids(n).length === 1 && kids(n)[0].tagName === 'strong' && FIELDS.has(text(n))
               && next && next.tagName === 'ul') {
      const dl = fieldList(n, next);
      const prev = out.filter((c) => c.type === 'element').at(-1);
      if (prev && prev.tagName === 'dl') prev.children.push(...dl.children);  // one grid for all of an entry's fields
      else out.push(dl);
      i = j;
    } else if (onlyLink(n) && /^(c?src\/\S+|source)$/.test(text(onlyLink(n)))) {
      addClass(n, 'api-file');
      out.push(n);
    } else {
      if (n.tagName === 'table') summaryTable(n);
      out.push(n);
    }
  }
  // methods: an h4 entry and everything after it until the next h1-h3, indented in one block
  const grouped = [];
  let block = null;
  for (const n of out) {
    if (n.type === 'element' && /^h[1-3]$/.test(n.tagName)) block = null;
    else if (n.type === 'element' && n.tagName === 'h4' && n.properties.className?.includes('api-entry') && !block) {
      block = el('div', ['api-members'], []);
      grouped.push(block);
    }
    (block ? block.children : grouped).push(n);
  }
  parent.children = grouped;
}

export default function apiReference() {
  return (tree, file) => {
    const path = (file.path || file.history?.[0] || '').replace(/\\/g, '/');
    if (!/\/docs\/(library\/python-api\.md|dev\/reference\/)/.test(path)) return;
    rewrite(tree);
  };
}
