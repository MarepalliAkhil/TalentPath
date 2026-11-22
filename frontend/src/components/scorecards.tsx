import { RECOMMENDATIONS } from '@/lib/interviews';
import type { ScorecardItem, ScorecardSummary } from '@/lib/types';

/** Average per criterion and recommendation counts (a list, readable without colour). */
export function SummaryView({ summary }: { summary: ScorecardSummary }) {
  if (summary.hidden) {
    return <p className="text-sm text-muted">Other interviewers' feedback stays hidden until you submit your own.</p>;
  }
  if (!summary.submitted) {
    return <p className="text-sm text-muted">No scorecards submitted yet ({summary.expected} expected).</p>;
  }
  return (
    <div className="space-y-2 text-sm">
      <p className="text-muted">
        {summary.submitted} of {summary.expected} scorecards in.
      </p>
      <ul className="grid gap-1 sm:grid-cols-2" aria-label="Average rating per criterion">
        {summary.criteria.map((c) => (
          <li key={c.key} className="flex items-center justify-between gap-2 rounded-lg bg-canvas px-3 py-1.5">
            <span className="text-ink-soft">{c.label}</span>
            <span className="font-semibold text-ink">
              {c.average.toFixed(1)}
              <span className="sr-only"> out of 5</span>
              <span aria-hidden="true">/5</span>
            </span>
          </li>
        ))}
      </ul>
      <p className="text-ink-soft">
        Recommendations:{' '}
        {RECOMMENDATIONS.filter((r) => summary.recommendations[r.value])
          .map((r) => `${r.label} ${summary.recommendations[r.value]}`)
          .join(', ')}
      </p>
    </div>
  );
}

export function CardView({ card, heading }: { card: ScorecardItem; heading: string }) {
  return (
    <article className="rounded-xl2 border border-ink/10 bg-white/80 p-4">
      <h3 className="font-semibold text-ink">
        {heading} · <span className="text-primary-strong">{card.recommendation_label}</span>
      </h3>
      <ul className="mt-2 space-y-1 text-sm">
        {card.criteria.map((c) => (
          <li key={c.key}>
            <span className="text-ink-soft">{c.label}:</span> <span className="font-semibold text-ink">{c.rating}/5</span>
            {c.comment && <span className="block text-muted">“{c.comment}”</span>}
          </li>
        ))}
      </ul>
      {card.summary && <p className="mt-2 text-sm text-ink-soft">{card.summary}</p>}
    </article>
  );
}
