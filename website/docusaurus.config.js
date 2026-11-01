// Docusaurus site for pencilmark. Pages live in ../docs (readable on GitHub too); plain .md is parsed as Markdown, not MDX.
const {tomorrowVars} = require('./src/prism-tomorrow');

const GH = 'https://github.com/silly-puppyy/pencilmark';

module.exports = async function createConfig() {
  const remarkMath = (await import('remark-math')).default;
  const rehypeKatex = (await import('rehype-katex')).default;
  const inlineJson = (await import('./src/plugins/inline-json.mjs')).default;
  const apiReference = (await import('./src/plugins/api-reference.mjs')).default;
  const proseTables = (await import('./src/plugins/prose-tables.mjs')).default;
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
  // the reader's graphics choice, set before the first paint (as the theme sets data-theme): set only by the client
  // module above, graphics a reader turned off would flash in on every page load until the scripts ran
  headTags: [{tagName: 'script', attributes: {}, innerHTML:
    "try{document.documentElement.dataset.graphics=localStorage.getItem('pm-graphics')==='off'?'off':'on'}" +
    "catch(e){document.documentElement.dataset.graphics='on'}"}],
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
        // "Edit this page": copies point to their source at the repository root; generated pages (tools/gen_*.py) have
        // no link, since an edit there is overwritten
        editUrl: ({docPath}) => {
          const copies = {'index.md': 'README.md', 'guides/development/architecture.md': 'ARCHITECTURE.md',
                          'dev/contributing.md': 'CONTRIBUTING.md'};
          const generated = ['library/python-api.md', 'grades/techniques.md', 'library/palette.md', 'guides/development/parameters.md'];
          if (generated.includes(docPath) || docPath.startsWith('reference/')) return undefined;
          return `${GH}/edit/main/${copies[docPath] || 'docs/' + docPath}`;
        },
        exclude: ['**/*.json'],
        remarkPlugins: [remarkMath],
        rehypePlugins: [rehypeKatex, apiReference, proseTables, inlineJson],
      },
      blog: false,
      theme: {customCss: require.resolve('./src/css/custom.css')},
    }],
  ],
  themeConfig: {
    // link previews and search: the social card (static/img/social-card.png) and page keywords
    image: 'img/social-card.png',
    metadata: [{name: 'keywords', content: 'sudoku, sudoku difficulty, sudoku grader, variant sudoku, killer sudoku, ' +
      'sudoku solver, sudoku generator, solve time, python'}],
    colorMode: {respectPrefersColorScheme: true},
    navbar: {
      title: 'pencilmark',
      logo: {alt: 'pencilmark', src: 'img/favicon.svg'},
      items: [
        {to: '/start/usage/', label: 'Usage', position: 'left'},
        {to: '/formats/puzzle-format/', label: 'Puzzle format', position: 'left'},
        {to: '/formats/grade-card/', label: 'Grade card', position: 'left'},
        {to: '/library/python-api/', label: 'Python API', position: 'left'},
        {href: 'https://pypi.org/project/pencilmark/', position: 'right', className: 'pm-nav-icon pm-nav-pypi',
         'aria-label': 'pencilmark on PyPI', title: 'PyPI'},
        {href: GH, position: 'right', className: 'pm-nav-icon pm-nav-github', 'aria-label': 'GitHub repository',
         title: 'GitHub'},
        {type: 'custom-graphicsToggle', position: 'right'},  // last: right before the theme switch
      ],
    },
    footer: {
      style: 'dark',
      links: [
        {title: 'Docs', items: [{label: 'Usage', to: '/start/usage/'}, {label: 'Puzzle format', to: '/formats/puzzle-format/'},
                                {label: 'Grade card', to: '/formats/grade-card/'}, {label: 'Generator spec', to: '/formats/generator-spec/'},
                                {label: 'Drawing and style', to: '/library/drawing-style/'}, {label: 'Engine', to: '/library/engine-mapping/'}]},
        {title: 'Schemas', items: [{label: 'sudoku-puzzle', href: 'pathname:///pencilmark/schema/sudoku-puzzle-1.json'},
                                   {label: 'sudoku-grade', href: 'pathname:///pencilmark/schema/sudoku-grade-1.json'}]},
        {title: 'Project', items: [{label: 'GitHub', href: GH}, {label: 'PyPI', href: 'https://pypi.org/project/pencilmark/'}]},
      ],
      copyright: 'MIT licensed',
    },
    prism: {theme: tomorrowVars, darkTheme: tomorrowVars, additionalLanguages: ['json', 'python', 'bash']},
    tableOfContents: {minHeadingLevel: 2, maxHeadingLevel: 3},
    mermaid: {theme: {light: 'neutral', dark: 'dark'}, options: {securityLevel: 'loose'}},  // loose: diagram boxes can link to sections
  },
};
};
