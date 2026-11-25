import { useMutation } from '@tanstack/react-query';
import { Button, Card, ErrorNote, PageHeader, StatTile } from '@/components/ui';
import { api } from '@/lib/api';
import { useDocumentTitle } from '@/lib/hooks';
import type { FairnessResult } from '@/lib/types';

export function FairnessPage() {
  useDocumentTitle('Fairness check');
  const run = useMutation({ mutationFn: () => api<FairnessResult>('/fairness/check?limit=40') });
  const r = run.data;
  return (
    <>
      <PageHeader
        title="Fairness check"
        intro="Re-scores current applications after changing only the name, gendered words, college and city. A fair scorer gives identical results."
        actions={
          <Button onClick={() => run.mutate()} disabled={run.isPending}>
            {run.isPending ? 'Running…' : 'Run the check'}
          </Button>
        }
      />
      {run.isError && <ErrorNote>The check could not run. Please try again.</ErrorNote>}
      {r && (
        <section aria-labelledby="fairness-result" className="mb-6">
          <h2 id="fairness-result" className={`font-display text-2xl font-semibold ${r.passed ? 'text-success' : 'text-danger'}`}>
            {r.summary}
          </h2>
          <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-3">
            <StatTile label="Applications checked" value={r.applications} />
            <StatTile label="Variants tested" value={r.variants} />
            <StatTile label="Score changes" value={r.changes} />
          </div>
          {r.examples.length > 0 && (
            <Card className="mt-4">
              <h3 className="font-semibold text-ink">Changes found</h3>
              <ul className="mt-2 text-sm text-ink-soft">
                {r.examples.map((e) => (
                  <li key={`${e.application}-${e.variant}`}>
                    {e.application}: {e.original} → {e.variant_score} ({e.variant} variant)
                  </li>
                ))}
              </ul>
            </Card>
          )}
        </section>
      )}
      <Card>
        <h2 className="font-display text-lg font-semibold text-ink">What this proves, and what it does not</h2>
        <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-ink-soft">
          <li>Each resume is copied in memory with a different name, gender words and pronouns, college and city. Nothing is stored.</li>
          <li>Every copy goes through the same extractor and scorer. Score, band and explanation must not change.</li>
          <li>
            It proves the scorer ignores these details. It does not prove that a job's requirements are fair, or catch bias in what people
            write about themselves.
          </li>
          <li>The same check runs automatically in CI on synthetic resumes for every demo job.</li>
        </ul>
      </Card>
    </>
  );
}
