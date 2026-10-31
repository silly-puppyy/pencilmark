// Tomorrow and Tomorrow Night (Chris Kempson's palettes) as one prism-react-renderer theme whose colours are CSS
// variables (set per theme in custom.css). Code is rendered on the server before the reader's theme is known: with
// literal colours a dark page painted light code blocks until the scripts ran; with variables the first paint is right.
const v = (name) => `var(--pm-code-${name})`;
const tomorrowVars = {
  plain: {color: v('fg'), backgroundColor: v('bg')},
  styles: [
    {types: ['comment', 'prolog', 'doctype', 'cdata'], style: {color: v('comment'), fontStyle: 'italic'}},
    {types: ['punctuation'], style: {color: v('fg')}},
    {types: ['property', 'tag', 'constant', 'symbol', 'deleted', 'variable'], style: {color: v('red')}},
    {types: ['boolean', 'number'], style: {color: v('orange')}},
    {types: ['attr-name', 'class-name', 'builtin'], style: {color: v('yellow')}},
    {types: ['string', 'char', 'inserted', 'attr-value'], style: {color: v('green')}},
    {types: ['operator', 'entity', 'url', 'regex'], style: {color: v('aqua')}},
    {types: ['function', 'selector'], style: {color: v('blue')}},
    {types: ['keyword', 'atrule', 'important'], style: {color: v('purple')}},
  ],
};

module.exports = {tomorrowVars};
