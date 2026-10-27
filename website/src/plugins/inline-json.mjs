// rehype plugin: colour inline code that is JSON (`{"type": "cage"}`, `[1, 2]`, `"key": value`) with the code theme's tokens.
import {visit} from 'unist-util-visit';
import {refractor} from 'refractor/lib/core.js';
import json from 'refractor/lang/json.js';

refractor.register(json);
const looksJson = (s) => /^\s*[[{]/.test(s) || /^"[^"\n]+"\s*:/.test(s);
const text = (n) => (n.type === 'text' ? n.value : (n.children || []).map(text).join(''));

export default function inlineJson() {
  return (tree) => {
    visit(tree, 'element', (node, _i, parent) => {
      if (node.tagName !== 'code' || (parent && parent.tagName === 'pre')) return;
      const s = text(node);
      if (!looksJson(s)) return;
      node.children = refractor.highlight(s, 'json').children;
      node.tagName = 'span';      // a code element with markup inside would be rendered as a code block
      node.properties = {...node.properties, className: [...(node.properties?.className || []), 'inline-json']};
    });
  };
}
