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
};

function assemble(src, dest) {
  let text = readFileSync(join(root, src), 'utf8');
  for (const [from, to] of Object.entries(LINKS)) {
    text = text.replaceAll(`](${from})`, `](${to})`).replaceAll(`](${from}#`, `](${to}#`);
  }
  writeFileSync(join(docs, dest), text);
}

rmSync(docs, {recursive: true, force: true});
mkdirSync(docs, {recursive: true});

assemble('README.md', 'index.md');
for (const f of ['SPEC.md', 'SECURITY.md', 'CONTRIBUTING.md', 'HISTORY.md']) {
  assemble(f, f);
}
cpSync(join(root, 'images'), join(docs, 'images'), {recursive: true});
