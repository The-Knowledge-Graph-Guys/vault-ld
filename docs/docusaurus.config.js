// @ts-check
import {themes as prismThemes} from 'prism-react-renderer';

// The spec site carries its own schema.org JSON-LD — a linked-data spec
// should be discoverable as linked data (and it signals the project's
// nature to search engines).
const jsonLd = [
  // WebSite record: tells search engines the site's canonical name and the
  // spellings people search by ("vault ld" without the hyphen).
  {
    '@context': 'https://schema.org',
    '@type': 'WebSite',
    name: 'Vault-LD',
    alternateName: ['Vault LD', 'VaultLD', 'vault-ld', 'vld', 'vault ld'],
    url: 'https://vault-ld.org/',
  },
  {
    '@context': 'https://schema.org',
    '@type': 'TechArticle',
    name: 'Vault-LD Specification',
    headline:
      'Vault-LD: an open format for reading a vault of Markdown notes as an RDF graph',
    url: 'https://vault-ld.org/',
    license: 'https://www.apache.org/licenses/LICENSE-2.0',
    author: {
      '@type': 'Organization',
      name: 'The Knowledge Graph Guys',
      url: 'https://github.com/The-Knowledge-Graph-Guys',
    },
    publisher: {
      '@type': 'Organization',
      name: 'The Knowledge Graph Guys',
      url: 'https://github.com/The-Knowledge-Graph-Guys',
    },
  },
  {
    '@context': 'https://schema.org',
    '@type': 'SoftwareSourceCode',
    name: 'Vault-LD reference tools',
    codeRepository: 'https://github.com/The-Knowledge-Graph-Guys/vault-ld',
    programmingLanguage: 'Python',
    license: 'https://www.apache.org/licenses/LICENSE-2.0',
  },
];

/** @type {import('@docusaurus/types').Config} */
const config = {
  title: 'Vault-LD',
  tagline:
    'An open format for knowledge two very different readers can share at once: a person editing notes, and a machine reasoning over a graph.',
  favicon: 'img/favicon.svg',

  url: 'https://vault-ld.org',
  baseUrl: '/',
  organizationName: 'The-Knowledge-Graph-Guys',
  projectName: 'vault-ld',

  // The docs are the repo's own markdown (see assemble.mjs); links to repo
  // files that aren't part of the site (LICENSE, scripts/…) should warn,
  // not break the build.
  onBrokenLinks: 'warn',
  markdown: {
    // .md renders as CommonMark (so prose like <angle brackets> in the spec
    // never trips the MDX parser); .mdx opts into MDX for custom pages.
    format: 'detect',
    hooks: {
      onBrokenMarkdownLinks: 'warn',
    },
  },
  headTags: jsonLd.map((data) => ({
    tagName: 'script',
    attributes: {type: 'application/ld+json'},
    innerHTML: JSON.stringify(data),
  })),

  presets: [
    [
      'classic',
      /** @type {import('@docusaurus/preset-classic').Options} */
      ({
        docs: {
          path: 'docs',
          routeBasePath: '/',
          sidebarPath: './sidebars.js',
          editUrl:
            'https://github.com/The-Knowledge-Graph-Guys/vault-ld/tree/main/',
          // Released versions are committed snapshots (versioned_docs/),
          // cut with `npm run snapshot -- X.Y.Z` as part of the release
          // ritual (CONTRIBUTING.md). The latest snapshot serves at the
          // site root; main's live state is browsable as the version below.
          // noIndex keeps near-identical copies of the docs (unreleased
          // main, superseded releases) out of search engines so ranking
          // signal concentrates on the latest release at the site root.
          // When cutting a new snapshot, add the now-superseded version
          // here.
          versions: {
            current: {label: 'Next (unreleased)', noIndex: true},
            '0.3.0': {noIndex: true},
            '0.4.0': {noIndex: true},
          },
        },
        blog: false,
        pages: false,
        theme: {
          customCss: './src/css/custom.css',
        },
      }),
    ],
  ],

  themeConfig:
    /** @type {import('@docusaurus/preset-classic').ThemeConfig} */
    ({
      // Social card for link previews (og:image / twitter:image).
      image: 'img/social-card.png',
      metadata: [{property: 'og:site_name', content: 'Vault-LD'}],
      colorMode: {
        respectPrefersColorScheme: true,
      },
      navbar: {
        title: 'Vault-LD',
        items: [
          {type: 'doc', docId: 'SPEC', label: 'Specification', position: 'left'},
          {type: 'doc', docId: 'SECURITY', label: 'Security', position: 'left'},
          {type: 'doc', docId: 'HISTORY', label: 'History', position: 'left'},
          {type: 'docsVersionDropdown', position: 'right'},
          {
            href: 'https://github.com/The-Knowledge-Graph-Guys/vault-ld',
            label: 'GitHub',
            position: 'right',
          },
        ],
      },
      footer: {
        style: 'dark',
        copyright: `Apache-2.0 — The Knowledge Graph Guys`,
      },
      prism: {
        theme: prismThemes.github,
        darkTheme: prismThemes.dracula,
        additionalLanguages: ['turtle', 'yaml', 'json', 'python', 'bash'],
      },
    }),
};

export default config;
