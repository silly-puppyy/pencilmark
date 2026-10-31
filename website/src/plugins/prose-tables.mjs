// rehype plugin: a table whose last column is prose (on average several times longer than every other column) gets the
// class pm-prose-table, and custom.css gives that column the room, so short key / type columns stop taking half the
// width; short cells of the other columns (14 characters or fewer) stay on one line. Other tables keep the browser's
// layout.
import {visit} from 'unist-util-visit';

const text = (n) => (n.type === 'text' ? n.value : (n.children || []).map(text).join(''));
const cells = (tr) => (tr.children || []).filter((c) => c.tagName === 'td' || c.tagName === 'th');

export default function proseTables() {
  return (tree) => {
    visit(tree, 'element', (table) => {
      if (table.tagName !== 'table') return;
      const rows = [];
      visit(table, 'element', (tr) => { if (tr.tagName === 'tr') rows.push(cells(tr).map((c) => text(c).trim().length)); });
      const n = rows[0]?.length || 0;
      if (n < 3 || rows.length < 3) return;
      const mean = Array.from({length: n}, (_, i) => rows.reduce((s, r) => s + (r[i] || 0), 0) / rows.length);
      const last = mean[n - 1];
      if (last < 60 || mean.slice(0, -1).some((m) => m * 3 > last)) return;
      table.properties.className = [...(table.properties.className || []), 'pm-prose-table'];
      visit(table, 'element', (tr) => {  // short cells of the other columns stay on one line
        if (tr.tagName !== 'tr') return;
        cells(tr).slice(0, -1).forEach((c) => {
          if (text(c).trim().length <= 14) c.properties.className = [...(c.properties.className || []), 'pm-short'];
        });
      });
    });
  };
}
