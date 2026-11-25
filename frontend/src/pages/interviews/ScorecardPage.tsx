import { useState, type FormEvent } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link, useParams } from 'react-router-dom';
import { CardView, SummaryView } from '@/components/scorecards';
import { Button, ErrorNote, PageHeader, PageLoader, SuccessNote, TextAreaField } from '@/components/ui';
import { api, ApiError } from '@/lib/api';
import { useDocumentTitle } from '@/lib/hooks';
import { ist, istRange, RECOMMENDATIONS } from '@/lib/interviews';
import type { Criterion, Recommendation, ScorecardPage as Page } from '@/lib/types';

const SCALE = [
  { value: 1, label: 'Weak' },
  { value: 2, label: 'Below the bar' },
  { value: 3, label: 'Meets the bar' },
  { value: 4, label: 'Strong' },
  { value: 5, label: 'Exceptional' },
];

function CriterionField({
  criterion,
  rating,
  comment,
  required,
  errors,
  onRate,
  onComment,
}: {
  criterion: Criterion;
  rating: number | undefined;
  comment: string;
  required: boolean;
  errors: Record<string, string>;
  onRate: (value: number) => void;
  onComment: (value: string) => void;
}) {
  const ratingError = errors[`ratings.${criterion.key}`];
  const commentError = errors[`comments.${criterion.key}`];
  return (
    <fieldset className="rounded-xl2 border border-ink/10 bg-white/70 p-4">
      <legend className="px-1 font-semibold text-ink">
        {criterion.label}
        {criterion.kind === 'skill' && <span className="ml-2 text-xs font-normal text-muted">Required skill</span>}
      </legend>
      <div className="flex flex-wrap gap-2">
        {SCALE.map((s) => (
          <label
            key={s.value}
            className={`flex min-h-11 min-w-11 cursor-pointer items-center justify-center gap-1 rounded-xl border px-3 text-sm focus-within:ring-2 focus-within:ring-primary/40 ${
              rating === s.value ? 'border-primary bg-primary-soft font-semibold text-primary-strong' : 'border-ink/15 bg-white'
            }`}
          >
            <input
              type="radio"
              name={`rating-${criterion.key}`}
              value={s.value}
              checked={rating === s.value}
              onChange={() => onRate(s.value)}
              className="sr-only"
            />
            <span aria-hidden="true">{s.value}</span>
            <span className="sr-only">{`${s.value}: ${s.label}`}</span>
          </label>
        ))}
      </div>
      {ratingError && <p className="mt-1 text-sm font-medium text-danger">{ratingError}</p>}
      <div className="mt-3">
        <TextAreaField
          label={required ? `Comment for ${criterion.label} (required for this rating)` : `Comment for ${criterion.label} (optional)`}
          rows={2}
          maxLength={1000}
          value={comment}
          onChange={(e) => onComment(e.target.value)}
          error={commentError}
          required={required}
        />
      </div>
    </fieldset>
  );
}

export function ScorecardPage() {
  const { id = '' } = useParams();
  const client = useQueryClient();
  const page = useQuery({ queryKey: ['scorecards', id], queryFn: () => api<Page>(`/interviews/${id}/scorecards`) });
  useDocumentTitle('Interview scorecard');
  const [ratings, setRatings] = useState<Record<string, number>>({});
  const [comments, setComments] = useState<Record<string, string>>({});
  const [recommendation, setRecommendation] = useState<Recommendation | ''>('');
  const [summary, setSummary] = useState('');
  const submit = useMutation({
    mutationFn: () => api(`/interviews/${id}/scorecards`, { method: 'POST', body: { ratings, comments, recommendation, summary } }),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ['scorecards', id] });
      void client.invalidateQueries({ queryKey: ['assigned-interviews'] });
    },
  });

  if (page.isPending) return <PageLoader />;
  if (page.isError || !page.data) return <ErrorNote>We could not load this interview.</ErrorNote>;
  const data = page.data;
  const interview = data.interview;
  const who = interview.candidate?.full_name ?? interview.candidate?.code ?? 'Candidate';
  const errors = submit.error instanceof ApiError ? submit.error.fieldErrors : {};
  const canSubmit = !!interview.can_submit_scorecard && !data.mine;
  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    submit.mutate();
  };

  return (
    <>
      <PageHeader
        title={`Scorecard: ${who}`}
        intro={`${interview.job.title} · ${interview.round.name} · ${istRange(interview.starts_at, interview.ends_at)}`}
        actions={
          <Link to="/interviews" className="text-sm font-semibold text-primary-strong underline">
            Back to my interviews
          </Link>
        }
      />
      {submit.isSuccess && <SuccessNote>Thank you. Your scorecard is in, and you can now read the other feedback.</SuccessNote>}
      {canSubmit && (
        <form onSubmit={onSubmit} className="flex flex-col gap-4" aria-label="Scorecard">
          <p className="text-sm text-muted">
            Rate each area from 1 to 5. Ratings of 1, 2 and 5 need a short comment. Others' feedback stays hidden until you submit, so your
            view is your own. {interview.scorecard_due_at && <>Due {ist(interview.scorecard_due_at)}.</>}
          </p>
          {data.template.map((c) => (
            <CriterionField
              key={c.key}
              criterion={c}
              rating={ratings[c.key]}
              comment={comments[c.key] ?? ''}
              required={data.comment_required_for.includes(ratings[c.key] ?? 0)}
              errors={errors}
              onRate={(value) => setRatings({ ...ratings, [c.key]: value })}
              onComment={(value) => setComments({ ...comments, [c.key]: value })}
            />
          ))}
          <fieldset className="rounded-xl2 border border-ink/10 bg-white/70 p-4">
            <legend className="px-1 font-semibold text-ink">Overall recommendation</legend>
            <div className="flex flex-wrap gap-2">
              {RECOMMENDATIONS.map((r) => (
                <label
                  key={r.value}
                  className={`flex min-h-11 cursor-pointer items-center gap-2 rounded-xl border px-3 text-sm ${recommendation === r.value ? 'border-primary bg-primary-soft font-semibold' : 'border-ink/15 bg-white'}`}
                >
                  <input
                    type="radio"
                    name="recommendation"
                    value={r.value}
                    checked={recommendation === r.value}
                    onChange={() => setRecommendation(r.value)}
                    className="h-4 w-4 accent-primary"
                  />
                  {r.label}
                </label>
              ))}
            </div>
            {errors.recommendation && <p className="mt-1 text-sm font-medium text-danger">{errors.recommendation}</p>}
          </fieldset>
          <TextAreaField
            label="Summary (optional)"
            rows={3}
            maxLength={2000}
            value={summary}
            onChange={(e) => setSummary(e.target.value)}
          />
          {submit.isError && <ErrorNote>{submit.error instanceof ApiError ? submit.error.message : 'Could not submit.'}</ErrorNote>}
          <Button type="submit" className="self-start" disabled={submit.isPending}>
            Submit scorecard
          </Button>
        </form>
      )}
      {data.mine && (
        <section className="mt-6" aria-labelledby="mine-heading">
          <h2 id="mine-heading" className="mb-2 font-display text-xl font-semibold text-ink">
            Your feedback
          </h2>
          <CardView card={data.mine} heading="You" />
        </section>
      )}
      <section className="mt-6" aria-labelledby="others-heading">
        <h2 id="others-heading" className="mb-2 font-display text-xl font-semibold text-ink">
          Other interviewers
        </h2>
        {data.others_hidden ? (
          <p className="rounded-xl bg-primary-soft px-3 py-2 text-sm text-primary-strong">
            Hidden until you submit your own scorecard. This keeps each interviewer's view independent.
          </p>
        ) : data.others.length ? (
          <div className="grid gap-3 md:grid-cols-2">
            {data.others.map((card) => (
              <CardView key={card.id} card={card} heading={card.interviewer.name} />
            ))}
          </div>
        ) : (
          <p className="text-sm text-muted">No other scorecards yet.</p>
        )}
      </section>
      <section className="mt-6" aria-labelledby="summary-heading">
        <h2 id="summary-heading" className="mb-2 font-display text-xl font-semibold text-ink">
          Summary
        </h2>
        <SummaryView summary={data.summary} />
      </section>
    </>
  );
}
