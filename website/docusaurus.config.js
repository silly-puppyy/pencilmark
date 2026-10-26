// Docusaurus site for pencilmark. Pages live in ../docs (readable on GitHub too); plain .md is parsed as Markdown, not MDX.
const {themes} = require('prism-react-renderer');

const GH = 'https://github.com/silly-puppyy/pencilmark';

module.exports = {
  title: 'pencilmark',
  tagline: 'Human-like difficulty grader, solver and generator for classic and variant sudoku',
  url: 'https://silly-puppyy.github.io',
  baseUrl: '/pencilmark/',
  favicon: 'img/favicon.svg',
  organizationName: 'silly-puppyy',
  projectName: 'pencilmark',
  trailingSlash: true,
  onBrokenLinks: 'throw',
  markdown: {format: 'detect', hooks: {onBrokenMarkdownLinks: 'throw'}},
  presets: [
    ['classic', {
      docs: {
        path: '../docs',
        routeBasePath: '/',
        sidebarPath: require.resolve('./sidebars.js'),
        editUrl: `${GH}/edit/main/`,
        exclude: ['**/*.json'],
      },
      blog: false,
      theme: {customCss: require.resolve('./src/css/custom.css')},
    }],
  ],
  themeConfig: {
    colorMode: {respectPrefersColorScheme: true},
    navbar: {
      title: 'pencilmark',
      logo: {alt: 'pencilmark', src: 'img/favicon.svg'},
      items: [
        {to: '/USAGE/', label: 'Usage', position: 'left'},
        {to: '/FORMAT/', label: 'Format', position: 'left'},
        {to: '/api/', label: 'Python API', position: 'left'},
        {href: 'https://pypi.org/project/pencilmark/', label: 'PyPI', position: 'right'},
        {href: GH, label: 'GitHub', position: 'right'},
      ],
    },
    footer: {
      style: 'dark',
      links: [
        {title: 'Docs', items: [{label: 'Usage', to: '/USAGE/'}, {label: 'Puzzle format', to: '/FORMAT/'},
                                {label: 'Engine', to: '/ENGINE/'}]},
        {title: 'Schemas', items: [{label: 'sudoku-puzzle', href: 'pathname:///pencilmark/schema/sudoku-puzzle-1.json'},
                                   {label: 'sudoku-grade', href: 'pathname:///pencilmark/schema/sudoku-grade-1.json'}]},
        {title: 'Project', items: [{label: 'GitHub', href: GH}, {label: 'PyPI', href: 'https://pypi.org/project/pencilmark/'}]},
      ],
      copyright: 'MIT licensed',
    },
    prism: {theme: themes.github, darkTheme: themes.vsDark, additionalLanguages: ['json', 'python', 'bash']},
    tableOfContents: {minHeadingLevel: 2, maxHeadingLevel: 3},
  },
};
