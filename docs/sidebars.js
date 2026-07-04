// Explicit order — the repo's documents, most important first.
/** @type {import('@docusaurus/plugin-content-docs').SidebarsConfig} */
const sidebars = {
  docs: [
    {type: 'doc', id: 'index', label: 'Overview'},
    {type: 'doc', id: 'SPEC', label: 'Specification'},
    {type: 'doc', id: 'SECURITY', label: 'Security'},
    {type: 'doc', id: 'CONTRIBUTING', label: 'Contributing'},
    {type: 'doc', id: 'HISTORY', label: 'History'},
  ],
};

export default sidebars;
