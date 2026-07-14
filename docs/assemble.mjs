// Assemble docs/docs/ from the repo's root markdown at build time, so the
// site always renders the same documents the repo ships — no second copy to
// drift. docs/docs/ is generated output and gitignored.
import {cpSync, mkdirSync, readFileSync, rmSync, writeFileSync} from 'node:fs';
import {fileURLToPath} from 'node:url';
import {join} from 'node:path';

const site = fileURLToPath(new URL('.', import.meta.url));
const root = join(site, '..');
const docs = join(site, 'docs');

const REPO = 'https://github.com/The-Knowledge-Graph-Guys/vault-ld/blob/main';

// Links to repo files that aren't pages on the site point at GitHub instead;
// README.md links resolve to the site's landing page (README is index.md).
const LINKS = {
  'README.md': 'index.md',
  'LICENSE': `${REPO}/LICENSE`,
  '.github/CHANGELOG.md': `${REPO}/.github/CHANGELOG.md`,
  'scripts/EXPORT.md': `${REPO}/scripts/EXPORT.md`,
  'scripts/INGEST.md': `${REPO}/scripts/INGEST.md`,
  'Vault-LD%20Example': `${REPO.replace('/blob/', '/tree/')}/Vault-LD%20Example`,
};

// SEO frontmatter injected per page (keyed by dest). Docusaurus can't derive
// titles/descriptions itself here — the README's h1 sits inside a raw-HTML
// <div>, so without this the homepage <title> falls back to the doc id
// ("index"). index.md hides the synthesized title because the markdown
// renders its own header block.
const META = {
  'index.md': {
    title: 'Vault-LD — Markdown notes as an RDF knowledge graph',
    hide_title: true,
    description:
      'Vault-LD is an open format for reading a vault of Markdown notes as an RDF knowledge graph: YAML-LD frontmatter becomes triples, wiki-links become typed edges, and the note body stays prose for humans and LLMs.',
    keywords: ['vault-ld', 'rdf', 'markdown', 'knowledge graph', 'linked data', 'json-ld', 'obsidian', 'sparql', 'yaml-ld'],
  },
  'SPEC.md': {
    description:
      'The normative Vault-LD specification: how Markdown notes with YAML-LD frontmatter project deterministically to an RDF graph — identity, wiki-links, contexts, and round-tripping.',
  },
  'SECURITY.md': {
    description:
      'Vault-LD security policy: how to privately report suspected vulnerabilities in the specification or the reference tools.',
  },
  'CONTRIBUTING.md': {
    description:
      'How to contribute to the Vault-LD open standard: proposing specification changes, improving the reference tools, and how releases are cut.',
  },
  'HISTORY.md': {
    description:
      'The narrative history of Vault-LD, release by release — what changed, why it changed, and what it means for implementers.',
  },
};

function assemble(src, dest) {
  let text = readFileSync(join(root, src), 'utf8');
  const meta = META[dest];
  if (meta) {
    // JSON scalars/arrays are valid YAML, so stringify each value.
    const yaml = Object.entries(meta)
      .map(([k, v]) => `${k}: ${JSON.stringify(v)}`)
      .join('\n');
    text = `---\n${yaml}\n---\n\n${text}`;
  }
  for (const [from, to] of Object.entries(LINKS)) {
    text = text.replaceAll(`](${from})`, `](${to})`).replaceAll(`](${from}#`, `](${to}#`);
  }
  // Markdown images (![](images/…)) are bundled by Docusaurus, but raw-HTML
  // <img>/<source> paths pass through untouched — point those at the copy of
  // images/ served from the static dir (see cpSync below).
  text = text.replaceAll(/(src|srcset)="images\//g, '$1="/images/');
  writeFileSync(join(docs, dest), text);
}

rmSync(docs, {recursive: true, force: true});
mkdirSync(docs, {recursive: true});

assemble('README.md', 'index.md');
for (const f of ['SPEC.md', 'SECURITY.md', 'CONTRIBUTING.md', 'HISTORY.md']) {
  assemble(f, f);
}
cpSync(join(root, 'images'), join(docs, 'images'), {recursive: true});
// Second copy under static/ (gitignored) for the raw-HTML references above.
rmSync(join(site, 'static', 'images'), {recursive: true, force: true});
cpSync(join(root, 'images'), join(site, 'static', 'images'), {recursive: true});
