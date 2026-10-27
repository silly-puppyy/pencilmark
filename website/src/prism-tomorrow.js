// Tomorrow and Tomorrow Night (Chris Kempson's palettes) as prism-react-renderer themes.
function theme(c) {
  return {
    plain: {color: c.fg, backgroundColor: c.bg},
    styles: [
      {types: ['comment', 'prolog', 'doctype', 'cdata'], style: {color: c.comment, fontStyle: 'italic'}},
      {types: ['punctuation'], style: {color: c.fg}},
      {types: ['property', 'tag', 'constant', 'symbol', 'deleted', 'variable'], style: {color: c.red}},
      {types: ['boolean', 'number'], style: {color: c.orange}},
      {types: ['attr-name', 'class-name', 'builtin'], style: {color: c.yellow}},
      {types: ['string', 'char', 'inserted', 'attr-value'], style: {color: c.green}},
      {types: ['operator', 'entity', 'url', 'regex'], style: {color: c.aqua}},
      {types: ['function', 'selector'], style: {color: c.blue}},
      {types: ['keyword', 'atrule', 'important'], style: {color: c.purple}},
    ],
  };
}

const tomorrowNight = theme({bg: '#23201d', fg: '#c5c8c6', comment: '#969896', red: '#cc6666', orange: '#de935f',
  yellow: '#f0c674', green: '#b5bd68', aqua: '#8abeb7', blue: '#81a2be', purple: '#b294bb'});
const tomorrow = theme({bg: '#f6f2ea', fg: '#4d4d4c', comment: '#8e908c', red: '#c82829', orange: '#f5871f',
  yellow: '#c18401', green: '#718c00', aqua: '#3e999f', blue: '#4271ae', purple: '#8959a8'});

module.exports = {tomorrow, tomorrowNight};
