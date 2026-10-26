module.exports = {
  docs: [
    {type: 'doc', id: 'index', label: 'Overview'},
    {type: 'doc', id: 'USAGE', label: 'Usage'},
    {type: 'category', label: 'Formats', collapsed: false, items: [
      {type: 'doc', id: 'FORMAT', label: 'Puzzle, card and spec format'},
      {type: 'doc', id: 'INTEROP', label: 'Other formats'},
      {type: 'doc', id: 'examples/specs/README', label: 'Example generator specs'},
    ]},
    {type: 'doc', id: 'ENGINE', label: 'Engine mapping'},
    {type: 'doc', id: 'api', label: 'Python API'},
  ],
};
