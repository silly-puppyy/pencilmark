// Six sections (after Diataxis: get started, how-to guides, reference, explanation, plus contributing), at most two
// levels deep except the rule families and the code reference. Each section opens on a card page listing its pages.
const section = (label, slug, description, items, collapsed = false) => ({
  type: 'category', label, collapsed, link: {type: 'generated-index', slug, description}, items,
});

module.exports = {
  docs: [
    {type: 'doc', id: 'index', label: 'Overview'},
    section('Get started', '/start/', 'Install pencilmark, grade a first puzzle, and the everyday commands.', [
      {type: 'doc', id: 'start/first-puzzle', label: 'Grade your first puzzle'},
      {type: 'doc', id: 'start/usage', label: 'Usage'},
    ]),
    section('Guides', '/guides/', 'Step by step: grading many puzzles, checking them, writing, generating, importing and drawing them.', [
      {type: 'doc', id: 'guides/batch', label: 'Grade many puzzles'},
      {type: 'doc', id: 'guides/publish-checks', label: 'Check a puzzle before publishing'},
      {type: 'doc', id: 'guides/variant-file', label: 'Write a variant puzzle file'},
      {type: 'doc', id: 'guides/generate', label: 'Generate a puzzle'},
      {type: 'doc', id: 'examples/specs/README', label: 'Example generator specs'},
      {type: 'doc', id: 'guides/import', label: 'Import puzzles from other apps'},
      {type: 'doc', id: 'guides/draw', label: 'Draw a puzzle'},
    ]),
    section('Formats', '/formats/', 'The three formats: a puzzle, its grade card, and a request to the generator.', [
      {type: 'doc', id: 'formats/puzzle-format', label: 'Puzzle format'},
      {type: 'category', label: 'Rule families', collapsed: true, link: {type: 'generated-index', slug: '/formats/rules/'}, items: [
        {type: 'doc', id: 'formats/rules/houses-and-regions', className: 'pm-ico pm-ico-houses', label: 'Houses and regions'},
        {type: 'doc', id: 'formats/rules/cages-and-sums', className: 'pm-ico pm-ico-cages', label: 'Cages and sums'},
        {type: 'doc', id: 'formats/rules/lines-and-arrows', className: 'pm-ico pm-ico-lines', label: 'Lines and arrows'},
        {type: 'doc', id: 'formats/rules/edges-and-corners', className: 'pm-ico pm-ico-edges', label: 'Edges and corners'},
        {type: 'doc', id: 'formats/rules/outside-clues', className: 'pm-ico pm-ico-outside', label: 'Outside clues'},
        {type: 'doc', id: 'formats/rules/whole-board-rules', className: 'pm-ico pm-ico-board', label: 'Whole-board rules'},
        {type: 'doc', id: 'formats/rules/cell-clues', className: 'pm-ico pm-ico-cells', label: 'Cell clues'},
        {type: 'doc', id: 'formats/rules/other', className: 'pm-ico pm-ico-other', label: 'Other rules'},
        {type: 'doc', id: 'formats/rules/examples', label: 'Examples'},
        {type: 'doc', id: 'formats/rules/quick-reference', label: 'Quick reference'},
      ]},
      {type: 'doc', id: 'formats/grade-card', label: 'Grade card'},
      {type: 'doc', id: 'formats/generator-spec', label: 'Generator spec'},
      {type: 'doc', id: 'formats/other-formats', label: 'Other formats'},
    ]),
    section('Library', '/library/', 'The Python library: its API, the variant names it gives, and how it draws puzzles.', [
      {type: 'doc', id: 'library/python-api', label: 'Python API'},
      {type: 'doc', id: 'library/variant-catalogue', label: 'Variant catalogue'},
      {type: 'doc', id: 'library/variant-naming', label: 'How variants are named'},
      {type: 'doc', id: 'library/drawing-style', label: 'Drawing and style'},
      {type: 'doc', id: 'library/palette', label: 'Palette'},
      {type: 'doc', id: 'library/engine-mapping', label: 'Engine mapping'},
    ]),
    section('How the grades work', '/grades/', 'What the numbers mean, how they are computed and measured, and what we tried on the way.', [
      {type: 'doc', id: 'grades/philosophy', label: 'Philosophy'},
      {type: 'doc', id: 'grades/model', label: 'How a card is computed'},
      {type: 'doc', id: 'grades/techniques', label: 'Techniques'},
      {type: 'doc', id: 'grades/benchmark', label: 'Benchmark'},
      {type: 'doc', id: 'grades/experiments', label: 'Experiment log'},
      {type: 'doc', id: 'grades/glossary', label: 'Glossary'},
    ]),
    section('Contributing', '/dev/', 'Working on pencilmark itself: set-up, architecture, how-tos for new techniques and rules, style, releases.', [
      {type: 'doc', id: 'dev/contributing', label: 'Contributing'},
      {type: 'doc', id: 'dev/environment', label: 'Development environment'},
      {type: 'doc', id: 'dev/architecture', label: 'Architecture'},
      {type: 'doc', id: 'dev/add-technique', label: 'Add a technique'},
      {type: 'doc', id: 'dev/add-rule-kind', label: 'Add a rule kind'},
      {type: 'doc', id: 'dev/parameters', label: 'Grader parameters'},
      {type: 'doc', id: 'dev/code-style', label: 'Code style'},
      {type: 'doc', id: 'dev/writing-style', label: 'Writing style'},
      {type: 'doc', id: 'dev/release', label: 'Release a version'},
      {type: 'category', label: 'Code reference', collapsed: true, link: {type: 'generated-index', slug: '/dev/reference/',
        description: 'Every module, function and class, generated from the docstrings and the C++ header comments.'}, items: [
        {type: 'category', label: 'Python', collapsed: true, items: [
          {type: 'doc', id: 'dev/reference/card', label: 'The card'},
          {type: 'doc', id: 'dev/reference/formats', label: 'Formats'},
          {type: 'doc', id: 'dev/reference/engine', label: 'The engine interface'},
          {type: 'doc', id: 'dev/reference/explain', label: 'Explanations'},
          {type: 'doc', id: 'dev/reference/generator', label: 'The generator'},
          {type: 'doc', id: 'dev/reference/sources', label: 'Puzzle sources'},
          {type: 'doc', id: 'dev/reference/cli', label: 'The command line'},
        ]},
        {type: 'category', label: 'C++ engine', collapsed: true, items: [
          {type: 'doc', id: 'dev/reference/cpp-files', label: 'Source files'},
          {type: 'doc', id: 'dev/reference/cpp-solver', label: 'The solver'},
          {type: 'doc', id: 'dev/reference/cpp-model', label: 'The puzzle model'},
          {type: 'doc', id: 'dev/reference/cpp-nary', label: 'N-ary constraints'},
          {type: 'doc', id: 'dev/reference/cpp-util', label: 'Utilities'},
        ]},
      ]},
    ], true),
  ],
};
