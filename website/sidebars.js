module.exports = {
  docs: [
    {type: 'doc', id: 'index', label: 'Overview'},
    {type: 'doc', id: 'USAGE', label: 'Usage'},
    {type: 'doc', id: 'PHILOSOPHY', label: 'Philosophy'},
    {type: 'category', label: 'Formats', collapsed: false, items: [
      {type: 'doc', id: 'FORMAT', label: 'Puzzle format'},
      {type: 'doc', id: 'GRADE', label: 'Grade card'},
      {type: 'doc', id: 'SPEC', label: 'Generator spec'},
      {type: 'doc', id: 'examples/specs/README', label: 'Example generator specs'},
      {type: 'doc', id: 'INTEROP', label: 'Other formats'},
    ]},
    {type: 'category', label: 'Library', collapsed: false, items: [
      {type: 'doc', id: 'STYLE', label: 'Drawing and style'},
      {type: 'doc', id: 'NAMING', label: 'Variant names'},
      {type: 'doc', id: 'ENGINE', label: 'Engine mapping'},
      {type: 'doc', id: 'api', label: 'Python API'},
    ]},
  ],
};
