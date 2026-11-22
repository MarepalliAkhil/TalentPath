import type { Fit, FitChip } from '@/lib/types';
import { Icon } from './Icon';

const BAND_STYLE: Record<string, string> = {
  strong: 'bg-success-soft text-success border-success/30',
  good: 'bg-primary-soft text-primary-strong border-primary/30',
  partial: 'bg-warning-soft text-warning border-warning/30',
  low: 'bg-canvas-deep text-ink-soft border-ink/15',
};

export function FitBadge({ fit, size = 'md' }: { fit: Fit | null; size?: 'sm' | 'md' }) {
  if (!fit) return <span className="text-xs text-muted">Not scored yet</span>;
  const pad = size === 'sm' ? 'px-2 py-0.5 text-xs' : 'px-2.5 py-1 text-sm';
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full border font-semibold ${pad} ${BAND_STYLE[fit.band]}`}>
      <span className="tabular-nums">{fit.score}</span>
      <span aria-hidden="true">·</span>
      {fit.band_label}
      <span className="sr-only"> fit</span>
    </span>
  );
}

const CHIP_STYLE: Record<FitChip['kind'], string> = {
  positive: 'border-success/30 bg-success-soft text-success',
  gap: 'border-danger/30 bg-danger-soft text-danger',
  bonus: 'border-primary/30 bg-primary-soft text-primary-strong',
  info: 'border-ink/15 bg-white/70 text-ink-soft',
};
const CHIP_PREFIX: Record<FitChip['kind'], string> = { positive: '✓', gap: '✕', bonus: '+', info: 'i' };

export function ReasonChips({ chips, limit }: { chips: FitChip[]; limit?: number }) {
  const shown = limit ? chips.slice(0, limit) : chips;
  return (
    <ul className="flex flex-wrap gap-1.5" aria-label="Reasons for this score">
      {shown.map((chip) => (
        <li key={chip.label} className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-xs font-medium ${CHIP_STYLE[chip.kind]}`}>
          <span aria-hidden="true">{CHIP_PREFIX[chip.kind]}</span>
          {chip.label}
        </li>
      ))}
      {limit && chips.length > limit && <li className="px-1 py-1 text-xs text-muted">+{chips.length - limit} more</li>}
    </ul>
  );
}

export function FitBreakdown({ fit }: { fit: Fit }) {
  const labels: Record<string, string> = {
    required: 'Required skills',
    nice: 'Nice-to-have skills',
    evidence: 'Evidence strength',
    experience: 'Experience fit',
  };
  return (
    <ul className="space-y-2" aria-label="Score breakdown">
      {fit.explanation.breakdown.map((row) => {
        const max = (row.weight * 100) / fit.explanation.breakdown.reduce((sum, r) => sum + r.weight, 0);
        const pct = max ? Math.round((row.points / max) * 100) : 0;
        return (
          <li key={row.component}>
            <div className="flex justify-between text-sm">
              <span className="text-ink-soft">{labels[row.component] ?? row.component}</span>
              <span className="font-semibold tabular-nums text-ink">
                {row.points} of {Math.round(max)} points
              </span>
            </div>
            <div className="mt-1 h-1.5 rounded-full bg-ink/10" aria-hidden="true">
              <div className="h-1.5 rounded-full bg-primary" style={{ width: `${pct}%` }} />
            </div>
          </li>
        );
      })}
    </ul>
  );
}

export function CandidateName({ app }: { app: { blind: boolean; candidate: { code: string; full_name: string | null } } }) {
  if (app.blind || !app.candidate.full_name) {
    return (
      <span className="inline-flex items-center gap-1.5">
        <Icon name="lock" className="h-4 w-4 text-muted" />
        {app.candidate.code}
        <span className="sr-only">(identity hidden during blind screening)</span>
      </span>
    );
  }
  return <span>{app.candidate.full_name}</span>;
}
