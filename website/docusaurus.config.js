// Docusaurus site for pencilmark. Pages live in ../docs (readable on GitHub too); plain .md is parsed as Markdown, not MDX.
const {tomorrow, tomorrowNight} = require('./src/prism-tomorrow');

const GH = 'https://github.com/silly-puppyy/pencilmark';

module.exports = async function createConfig() {
  const remarkMath = (await import('remark-math')).default;
  const rehypeKatex = (await import('rehype-katex')).default;
  const inlineJson = (await import('./src/plugins/inline-json.mjs')).default;
  return {
  title: 'pencilmark',
  tagline: 'Human-like difficulty grader, solver and generator for classic and variant sudoku',
  url: 'https://silly-puppyy.github.io',
  baseUrl: '/pencilmark/',
  favicon: 'img/favicon.svg',
  organizationName: 'silly-puppyy',
  projectName: 'pencilmark',
  trailingSlash: true,
  onBrokenLinks: 'throw',
  markdown: {format: 'detect', mermaid: true, hooks: {onBrokenMarkdownLinks: 'throw'}},
  clientModules: [require.resolve('./src/clientModules/graphics.js')],
  themes: [
    '@docusaurus/theme-mermaid',
    ['@easyops-cn/docusaurus-search-local', {hashed: true, docsDir: '../docs', docsRouteBasePath: '/', indexBlog: false, highlightSearchTermsOnTargetPage: true}],
  ],
  presets: [
    ['classic', {
      docs: {
        path: '../docs',
        routeBasePath: '/',
        sidebarPath: require.resolve('./sidebars.js'),
        editUrl: `${GH}/edit/main/`,
        exclude: ['**/*.json'],
        remarkPlugins: [remarkMath],
        rehypePlugins: [rehypeKatex, inlineJson],
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
        {to: '/FORMAT/', label: 'Puzzle format', position: 'left'},
        {to: '/GRADE/', label: 'Grade card', position: 'left'},
        {to: '/api/', label: 'Python API', position: 'left'},
        {type: 'custom-graphicsToggle', position: 'right'},
        {href: 'https://pypi.org/project/pencilmark/', label: 'PyPI', position: 'right'},
        {href: GH, label: 'GitHub', position: 'right'},
      ],
    },
    footer: {
      style: 'dark',
      links: [
        {title: 'Docs', items: [{label: 'Usage', to: '/USAGE/'}, {label: 'Puzzle format', to: '/FORMAT/'},
                                {label: 'Grade card', to: '/GRADE/'}, {label: 'Generator spec', to: '/SPEC/'},
                                {label: 'Drawing and style', to: '/STYLE/'}, {label: 'Engine', to: '/ENGINE/'}]},
        {title: 'Schemas', items: [{label: 'sudoku-puzzle', href: 'pathname:///pencilmark/schema/sudoku-puzzle-1.json'},
                                   {label: 'sudoku-grade', href: 'pathname:///pencilmark/schema/sudoku-grade-1.json'}]},
        {title: 'Project', items: [{label: 'GitHub', href: GH}, {label: 'PyPI', href: 'https://pypi.org/project/pencilmark/'}]},
      ],
      copyright: 'MIT licensed',
    },
    prism: {theme: tomorrow, darkTheme: tomorrowNight, additionalLanguages: ['json', 'python', 'bash']},
    tableOfContents: {minHeadingLevel: 2, maxHeadingLevel: 3},
    mermaid: {theme: {light: 'neutral', dark: 'dark'}, options: {securityLevel: 'loose'}},  // loose: diagram boxes can link to sections
  },
};
};
