import facts from 'virtual:repo-facts';
import { Link } from 'react-router-dom';
import { DemoButtons, useDemoConfig } from '@/components/growth';
import { buttonClass } from '@/components/ui';
import { brand } from '@/lib/brand';
import { useSeo } from '@/lib/hooks';
import type { Score } from '../../../build/repoFacts';

const SEO = {
  title: `For recruiters | ${brand.name}`,
  description: `${brand.name}, a portfolio project: hire to onboard with explainable matching, blind screening, interview scheduling, offers and leave, on synthetic data.`,
};

/** Companies named in plain text only: no logos, no brand colours, no claims about their internal systems. */
const COMPANIES = [
  {
    name: 'Phenom',
    area: 'Public product area: talent experience, such as AI-assisted career sites, career paths and internal mobility.',
    built: [
      'A career site with job search, clean job pages and structured data for search engines',
      'A skill-gap career map: "Jobs you\'re closest to", with an ordered learning path',
      'Internal mobility: internal jobs with a match, one-click apply and a clear manager-notice rule',
      'Ask HIRA, a rule-based assistant for candidates and employees',
    ],
  },
  {
    name: 'TurboHire',
    area: 'Public product area: AI-assisted candidate screening and recruiting automation.',
    built: [
      'Explainable matching: a 0-100 fit score with reason chips and "what would raise this score"',
      'Blind screening that hides identity until the Interview stage',
      'A counterfactual fairness test that changes only personal details and checks the score does not move',
      'HIRA scheduling: slots from interviewers\' free time, holds, reminders, reschedules and replacements',
    ],
  },
  {
    name: 'Darwinbox',
    area: 'Public product area: an HR platform that covers the employee lifecycle, from hiring to onboarding and beyond.',
    built: [
      'One connected flow from offer approval to employee record',
      'One-click hire to onboard: employee ID, checklist, buddy and first-week plan in one transaction',
      'An HR assistant that answers leave, holiday and onboarding questions from the employee\'s own data',
      'Hiring and people analytics with a table view and CSV export for every chart',
    ],
  },
  {
    name: 'Keka',
    area: 'Public product area: HR software that includes leave and attendance management.',
    built: [
      'A leave policy engine configured as data per location (no payroll here)',
      'Approvals by the reporting line, with delegation and escalation after 48 hours',
      'A team calendar with clash warnings that inform but never block',
      'Web attendance with late and early flags and regularisation',
    ],
  },
];

function score(s: Score | null): string {
  return s ? `${s.correct} / ${s.total}` : 'see the docs';
}

function num(n: number | null): string {
  return n === null ? 'see the repository' : String(n);
}

export function ForRecruitersPage() {
  useSeo(SEO);
  const config = useDemoConfig();
  const author = brand.author;
  const e = facts.evaluations;
  return (
    <div className="mx-auto max-w-4xl">
      <h1 className="font-display text-3xl font-semibold tracking-tight text-ink sm:text-4xl">For recruiters</h1>
      <section aria-labelledby="intro-heading" className="mt-4 space-y-2 text-ink-soft">
        <h2 id="intro-heading" className="sr-only">
          About this project
        </h2>
        <p>
          {brand.name} is an independent portfolio project by {author.name}, {author.education}. It follows one path from a
          candidate's first job search to an employee's first day, then leave, attendance and analytics.
        </p>
        <p>
          All people, companies and data here are synthetic. This project is not affiliated with, endorsed by or connected to
          any company named on this page.
        </p>
      </section>

      <section aria-labelledby="try-heading" className="glass mt-8 rounded-xl2 p-5">
        <h2 id="try-heading" className="font-display text-xl font-semibold text-ink">
          Try it in 60 seconds
        </h2>
        {config.data?.demo_mode ? (
          <div className="mt-3">
            <DemoButtons heading="Pick a role and you are signed in with demo data:" />
          </div>
        ) : (
          <p className="mt-2 text-sm text-ink-soft">
            One-click demo sign-in is switched off on this server.{' '}
            <Link to="/login" className="font-semibold text-primary-strong underline">
              Sign in
            </Link>{' '}
            with a demo account from the project's START_HERE guide, or{' '}
            <Link to="/jobs" className="font-semibold text-primary-strong underline">
              browse the career site
            </Link>
            .
          </p>
        )}
      </section>

      {COMPANIES.map((c) => (
        <section key={c.name} aria-labelledby={`co-${c.name}`} className="mt-8">
          <h2 id={`co-${c.name}`} className="font-display text-xl font-semibold text-ink">
            {c.name}
          </h2>
          <p className="mt-1 text-sm text-muted">{c.area}</p>
          <p className="mt-2 text-sm font-semibold text-ink">Built in {brand.name} for this area:</p>
          <ul className="mt-1 list-disc space-y-1 pl-5 text-ink-soft">
            {c.built.map((b) => (
              <li key={b}>{b}</li>
            ))}
          </ul>
        </section>
      ))}

      <section aria-labelledby="built-heading" className="mt-10">
        <h2 id="built-heading" className="font-display text-xl font-semibold text-ink">
          How it is built
        </h2>
        <ul className="mt-2 list-disc space-y-1 pl-5 text-ink-soft">
          <li>React 18, Vite, TypeScript, Tailwind and TanStack Query on the front; Django 5.2 and Django REST framework on the back; PostgreSQL.</li>
          <li>
            One permission file, deny by default: {num(facts.policy.actions)} actions across {facts.policy.roles.length} roles (
            {facts.policy.roles.join(', ')}), checked with allowed and denied tests for every endpoint.
          </li>
          <li>Personal data encrypted at rest (AES-GCM), HttpOnly cookie sessions with CSRF, rate limits and an audit log.</li>
          <li>The AI is rule based and explainable. No language model is used; if one is ever added, it stays optional and off by default.</li>
        </ul>
        <dl className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3" aria-label="Numbers from the repository">
          {[
            ['Backend test functions', num(facts.tests.backend)],
            ['Frontend unit tests', num(facts.tests.frontendUnit)],
            ['End-to-end tests', num(facts.tests.endToEnd)],
            ['API routes', num(facts.apiRoutes)],
            ['Permission actions', num(facts.policy.actions)],
            ['Roles', String(facts.policy.roles.length)],
          ].map(([label, value]) => (
            <div key={label} className="glass rounded-xl2 p-4">
              <dt className="text-sm text-muted">{label}</dt>
              <dd className="mt-1 font-display text-2xl font-semibold text-ink" data-testid={`fact-${label}`}>
                {value}
              </dd>
            </div>
          ))}
        </dl>
        <div className="mt-4 overflow-x-auto" role="region" aria-label="Measured evaluation results" tabIndex={0}>
          <table className="w-full text-left text-sm">
            <caption className="mb-1 text-left text-sm font-semibold text-ink">Measured evaluation results (from the project docs)</caption>
            <thead>
              <tr className="border-b border-ink/10 text-muted">
                <th scope="col" className="py-2 pr-3">Evaluation</th>
                <th scope="col" className="py-2 pr-3">Tuning set</th>
                <th scope="col" className="py-2 pr-3">Held-out set</th>
              </tr>
            </thead>
            <tbody>
              {[
                ['Matching (fit band)', e.matching],
                ['Ask HIRA for candidates (intent)', e.askHira],
                ['HR assistant for employees (intent)', e.hrAssistant],
              ].map(([label, s]) => {
                const pair = s as { tune: Score | null; holdout: Score | null };
                return (
                  <tr key={label as string} className="border-b border-ink/5">
                    <th scope="row" className="py-1.5 pr-3 font-medium text-ink">
                      {label as string}
                    </th>
                    <td className="py-1.5 pr-3 tabular-nums">{score(pair.tune)}</td>
                    <td className="py-1.5 pr-3 tabular-nums">{score(pair.holdout)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          <p className="mt-1 text-xs text-muted">
            Counted from the repository when this page was built ({facts.generatedAt}). Held-out questions were never used for tuning.
          </p>
        </div>
      </section>

      <section aria-labelledby="limits-heading" className="mt-10">
        <h2 id="limits-heading" className="font-display text-xl font-semibold text-ink">
          Honest limits
        </h2>
        <ul className="mt-2 list-disc space-y-1 pl-5 text-ink-soft">
          <li>All data is synthetic: no real candidates, employees or companies.</li>
          <li>Emails and meeting links are simulated; nothing is sent to a real inbox or calendar.</li>
          <li>No payroll and no payments; loss of pay is recorded, never calculated.</li>
          <li>No real calendar integration: interviewer free time comes from hours set in the app.</li>
          <li>It runs on free hosting, so the first request after a quiet spell can take a while to wake up.</li>
          <li>The AI is rule based and deterministic: no language model is used, so answers are predictable but narrower than a chatbot's.</li>
        </ul>
      </section>

      <section aria-labelledby="about-heading" className="glass mt-10 rounded-xl2 p-5">
        <h2 id="about-heading" className="font-display text-xl font-semibold text-ink">
          About me
        </h2>
        <p className="mt-1 text-ink-soft">
          {author.name}, {author.education}.
        </p>
        <ul className="mt-2 flex flex-wrap gap-3">
          <li>
            <a href={author.github} className={buttonClass('secondary')} rel="noopener noreferrer" target="_blank">
              GitHub<span className="sr-only"> (opens in a new tab)</span>
            </a>
          </li>
          <li>
            <a href={author.linkedin} className={buttonClass('secondary')} rel="noopener noreferrer" target="_blank">
              LinkedIn<span className="sr-only"> (opens in a new tab)</span>
            </a>
          </li>
        </ul>
      </section>
    </div>
  );
}
