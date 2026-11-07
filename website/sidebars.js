// Sections after Diataxis (get started, how-to guides, reference, explanation, plus contributing). Only the sections
// carry an icon in the sidebar (static/img/icons/<name>.svg); pages carry theirs on the card pages (a pm-ico-<name>
// class without pm-ico, read by theme/DocCard). Each section opens on a card page listing its pages.
const section = (label, slug, description, items, collapsed = true, icon = slug.split('/')[1]) => ({
  type: 'category', label, collapsed, className: `pm-ico pm-ico-${icon}`,
  link: {type: 'generated-index', slug, description}, items,
});
const group = (label, slug, description, items) => ({
  type: 'category', label, collapsed: true, className: `pm-ico-${slug.split('/')[2]}`, description,
  link: {type: 'generated-index', slug, description}, items,
});
const page = (id, icon, label) => ({type: 'doc', id, className: `pm-ico-${icon}`, label});

module.exports = {
  docs: [
    {type: 'doc', id: 'index', label: 'Overview'},
    section('Get started', '/start/', 'Install pencilmark, grade a first puzzle, and the everyday commands.', [
      {type: 'doc', id: 'start/first-puzzle', className: 'pm-ico-first-puzzle', label: 'Grade your first puzzle'},
      {type: 'doc', id: 'start/usage', className: 'pm-ico-usage', label: 'Usage'},
    ], false),
    section('Guides', '/guides/', 'Step by step: grading and checking puzzles, generating them, and working on the code.', [
      group('Grader', '/guides/grader/', 'Grade many puzzles, check one before publishing, write, import and draw puzzles.', [
        page('guides/grader/batch', 'batch', 'Grade many puzzles'),
        page('guides/grader/publish-checks', 'publish-checks', 'Check a puzzle before publishing'),
        page('guides/grader/variant-file', 'variant-file', 'Write a variant puzzle file'),
        page('guides/grader/import', 'import', 'Import puzzles from other apps'),
        page('guides/grader/fog', 'fog', 'Fog of war: what works'),
        page('guides/grader/draw', 'draw', 'Draw a puzzle'),
      ]),
      group('Generator', '/guides/generator/', 'Make puzzles to order: a first request, examples of every kind, puzzles for learners, and the named variants.', [
        page('guides/generator/generate', 'generate', 'Generate a puzzle'),
        page('guides/generator/generator-examples', 'spec-examples', 'Generator examples'),
        page('guides/generator/generate-for-learning', 'learning', 'Generate for learning'),
        {type: 'doc', id: 'guides/generator/variant-catalogue', className: 'pm-ico-variant-catalogue', label: 'Variant catalogue'},
      ]),
      group('Development', '/guides/development/', 'Build from source, find your way around the code, and add techniques or rules.', [
        page('guides/development/environment', 'environment', 'Development environment'),
        page('guides/development/architecture', 'architecture', 'Architecture'),
        page('guides/development/add-technique', 'add-technique', 'Add a technique'),
        page('guides/development/add-rule-kind', 'add-rule-kind', 'Add a rule kind'),
        page('guides/development/parameters', 'parameters', 'Grader parameters'),
        page('guides/development/engine-mapping', 'engine-mapping', 'Engine mapping'),
      ]),
    ]),
    section('Formats', '/formats/', 'The three formats (a puzzle, its grade card, a request to the generator) and the readers and writers of other formats.', [
      {type: 'category', label: 'Puzzle format', collapsed: true, className: 'pm-ico-puzzle-format',
        description: 'pencilmark JSON, the puzzle file: the format, complete examples and a quick reference.',
        link: {type: 'doc', id: 'formats/puzzle-format'}, items: [
        {type: 'doc', id: 'formats/examples', label: 'Examples'},
        {type: 'doc', id: 'formats/quick-reference', label: 'Quick reference'},
      ]},
      {type: 'category', label: 'Rule families', collapsed: true, className: 'pm-ico-rules',
        description: 'Every rule type of the puzzle format, family by family.', link: {type: 'generated-index', slug: '/formats/rules/',
        description: 'Every rule type of the puzzle format, family by family, with what it means and how it is drawn.'}, items: [
        page('formats/rules/houses-and-regions', 'houses', 'Houses and regions'),
        page('formats/rules/cages-and-sums', 'cages', 'Cages and sums'),
        page('formats/rules/lines-and-arrows', 'lines', 'Lines and arrows'),
        page('formats/rules/edges-and-corners', 'edges', 'Edges and corners'),
        page('formats/rules/outside-clues', 'outside', 'Outside clues'),
        page('formats/rules/whole-board-rules', 'board', 'Whole-board rules'),
        page('formats/rules/cell-clues', 'cells', 'Cell clues'),
        page('formats/rules/other', 'other', 'Other rules'),
        page('formats/rules/custom', 'custom', 'Custom rules'),
      ]},
      page('formats/grade-card', 'grade-card', 'Grade card'),
      page('formats/generator-spec', 'generator-spec', 'Generator spec'),
      page('formats/other-formats', 'other-formats', 'Readers and writers'),
    ]),
    section('Library', '/library/', 'The Python library: its public API, how it names variants, and how it draws puzzles. Internals are under Development and in the Code reference.', [
      {type: 'doc', id: 'library/python-api', className: 'pm-ico-python-api', label: 'Python API'},
      {type: 'doc', id: 'library/variant-naming', className: 'pm-ico-variant-naming', label: 'How variants are named'},
      {type: 'doc', id: 'library/drawing-style', className: 'pm-ico-drawing-style', label: 'Drawing and style'},
      {type: 'doc', id: 'library/palette', className: 'pm-ico-palette', label: 'Palette'},
    ]),
    section('How the grades work', '/grades/', 'What the numbers mean, how they are computed and measured, and what we tried on the way.', [
      {type: 'doc', id: 'grades/philosophy', className: 'pm-ico-philosophy', label: 'Philosophy'},
      {type: 'doc', id: 'grades/model', className: 'pm-ico-model', label: 'How a card is computed'},
      {type: 'doc', id: 'grades/techniques', className: 'pm-ico-techniques', label: 'Techniques'},
      {type: 'doc', id: 'grades/benchmark', className: 'pm-ico-benchmark', label: 'Benchmark'},
      {type: 'doc', id: 'grades/experiments', className: 'pm-ico-experiments', label: 'Experiment log'},
      {type: 'doc', id: 'grades/glossary', className: 'pm-ico-glossary', label: 'Glossary'},
    ]),
    section('Code reference', '/reference/', 'Every module, function and class, generated from the docstrings and the C++ header comments: the internals, for tinkering. The stable public API is Library > Python API.', [
      {type: 'category', label: 'Python', collapsed: true, description: 'The package: the card, formats, the engine interface, explanations, the generator, sources and the command line.', items: [
        {type: 'doc', id: 'reference/card', label: 'The card'},
        {type: 'doc', id: 'reference/formats', label: 'Formats'},
        {type: 'doc', id: 'reference/engine', label: 'The engine interface'},
        {type: 'doc', id: 'reference/explain', label: 'Explanations'},
        {type: 'doc', id: 'reference/fog', label: 'Fog of war'},
        {type: 'doc', id: 'reference/generator', label: 'The generator'},
        {type: 'doc', id: 'reference/sources', label: 'Puzzle sources'},
        {type: 'doc', id: 'reference/cli', label: 'The command line'},
      ]},
      {type: 'category', label: 'C++ engine', collapsed: true, description: 'The engine in csrc/: the solver, the puzzle model, n-ary constraints and utilities.', items: [
        {type: 'doc', id: 'reference/cpp-files', label: 'Source files'},
        {type: 'doc', id: 'reference/cpp-solver', label: 'The solver'},
        {type: 'doc', id: 'reference/cpp-model', label: 'The puzzle model'},
        {type: 'doc', id: 'reference/cpp-nary', label: 'N-ary constraints'},
        {type: 'doc', id: 'reference/cpp-util', label: 'Utilities'},
      ]},
    ], true, 'code-reference'),
    section('Contributing', '/dev/', 'Sending a change to pencilmark: how to propose it, the code and writing style, and releases.', [
      page('dev/contributing', 'contributing', 'Contributing'),
      page('dev/code-style', 'code-style', 'Code style'),
      page('dev/writing-style', 'writing-style', 'Writing style'),
      page('dev/release', 'release', 'Release a version'),
    ], true),
  ],
};
