/**
 * Numbers for the "For recruiters" page, read from the repository at build (and dev/test) time.
 * Nothing here is typed in by hand: tests are counted in the test files, permissions come from
 * shared/policy.json and evaluation results are parsed from the docs where they were measured.
 * If a number cannot be found it is null, and the page says "see the docs" instead of guessing.
 */
import { existsSync, readdirSync, readFileSync, statSync } from 'node:fs';
import { join } from 'node:path';

export interface Score {
  correct: number;
  total: number;
}

export interface RepoFacts {
  generatedAt: string;
  tests: { backend: number | null; frontendUnit: number | null; endToEnd: number | null };
  policy: { actions: number | null; roles: string[]; routes: number | null };
  apiRoutes: number | null;
  evaluations: {
    matching: { tune: Score | null; holdout: Score | null };
    askHira: { tune: Score | null; holdout: Score | null };
    hrAssistant: { tune: Score | null; holdout: Score | null };
  };
}

function files(dir: string, match: (name: string) => boolean): string[] {
  if (!existsSync(dir)) return [];
  const out: string[] = [];
  for (const name of readdirSync(dir)) {
    if (name === 'node_modules' || name.startsWith('.') || name === '__pycache__') continue;
    const full = join(dir, name);
    if (statSync(full).isDirectory()) out.push(...files(full, match));
    else if (match(name)) out.push(full);
  }
  return out;
}

function count(paths: string[], pattern: RegExp): number | null {
  if (!paths.length) return null;
  return paths.reduce((sum, p) => sum + (readFileSync(p, 'utf-8').match(pattern)?.length ?? 0), 0);
}

function read(path: string): string | null {
  return existsSync(path) ? readFileSync(path, 'utf-8') : null;
}

/** The bold "**a / b" figure on the first table row whose label matches. */
export function boldScore(doc: string | null, label: RegExp): Score | null {
  if (!doc) return null;
  for (const line of doc.split('\n')) {
    if (!line.trim().startsWith('|')) continue;
    const cells = line.split('|').map((c) => c.trim());
    if (!label.test(cells[1] ?? '')) continue;
    const m = line.match(/\*\*(\d+)\s*\/\s*(\d+)/);
    if (m) return { correct: Number(m[1]), total: Number(m[2]) };
  }
  return null;
}

export function collectRepoFacts(root: string): RepoFacts {
  const policyText = read(join(root, 'shared', 'policy.json'));
  const policy = policyText ? (JSON.parse(policyText) as { actions: object; roles: string[]; routes: object }) : null;
  const backendTests = files(join(root, 'backend', 'tests'), (n) => n.startsWith('test_') && n.endsWith('.py'));
  const unitTests = files(join(root, 'frontend', 'src'), (n) => /\.test\.tsx?$/.test(n));
  const e2e = files(join(root, 'frontend', 'e2e'), (n) => n.endsWith('.spec.ts'));
  const urls = files(join(root, 'backend'), (n) => /^urls(_\w+)?\.py$/.test(n));
  const matching = read(join(root, 'docs', 'MATCHING.md'));
  const askHira = read(join(root, 'docs', 'ASK_HIRA.md'));
  const hr = read(join(root, 'docs', 'HR.md'));
  return {
    generatedAt: new Date().toISOString().slice(0, 10),
    tests: {
      backend: count(backendTests, /^\s*def test_/gm),
      frontendUnit: count(unitTests, /^\s*it\(/gm),
      endToEnd: count(e2e, /^\s*test\(/gm),
    },
    policy: {
      actions: policy ? Object.keys(policy.actions).length : null,
      roles: policy?.roles ?? [],
      routes: policy ? Object.keys(policy.routes).length : null,
    },
    apiRoutes: count(urls, /^\s*path\((?![^)]*include\()/gm),
    evaluations: {
      matching: { tune: boldScore(matching, /^Tune/), holdout: boldScore(matching, /^Holdout/) },
      askHira: { tune: boldScore(askHira, /^Tune/), holdout: boldScore(askHira, /^Holdout/) },
      hrAssistant: { tune: boldScore(hr, /^Tuning/), holdout: boldScore(hr, /^Holdout/) },
    },
  };
}
