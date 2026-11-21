import {
  useId,
  type ButtonHTMLAttributes,
  type InputHTMLAttributes,
  type ReactNode,
  type SelectHTMLAttributes,
  type TextareaHTMLAttributes,
} from 'react';

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger';

const VARIANTS: Record<Variant, string> = {
  primary: 'bg-primary text-white hover:bg-primary-strong shadow-lift',
  secondary: 'bg-white/80 text-ink border border-ink/15 hover:border-primary hover:text-primary-strong',
  ghost: 'text-ink-soft hover:bg-ink/5',
  danger: 'bg-danger text-white hover:brightness-95',
};

// eslint-disable-next-line react-refresh/only-export-components -- class helper for Link buttons
export function buttonClass(variant: Variant = 'primary', extra = '') {
  return `inline-flex min-h-11 items-center justify-center gap-2 rounded-xl px-4 py-2 text-sm font-semibold transition-colors disabled:cursor-not-allowed disabled:opacity-60 ${VARIANTS[variant]} ${extra}`;
}

export function Button({
  variant = 'primary',
  className = '',
  type = 'button',
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant }) {
  return <button type={type} className={buttonClass(variant, className)} {...props} />;
}

export function Card({ children, className = '', as: As = 'section' }: { children: ReactNode; className?: string; as?: 'section' | 'div' | 'article' | 'li' }) {
  return <As className={`glass rounded-xl2 p-5 sm:p-6 ${className}`}>{children}</As>;
}

export function PageHeader({ title, intro, actions }: { title: string; intro?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
      <div>
        <h1 className="font-display text-2xl font-semibold tracking-tight text-ink sm:text-3xl">{title}</h1>
        {intro && <p className="mt-1 max-w-2xl text-muted">{intro}</p>}
      </div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </div>
  );
}

interface FieldShellProps {
  label: string;
  error?: string;
  hint?: string;
  children: (ids: { id: string; describedBy?: string; invalid: boolean }) => ReactNode;
  required?: boolean;
}

function FieldShell({ label, error, hint, children, required }: FieldShellProps) {
  const id = useId();
  const hintId = hint ? `${id}-hint` : undefined;
  const errorId = error ? `${id}-error` : undefined;
  const describedBy = [hintId, errorId].filter(Boolean).join(' ') || undefined;
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className="text-sm font-medium text-ink">
        {label}
        {required && <span className="text-danger" aria-hidden="true"> *</span>}
      </label>
      {children({ id, describedBy, invalid: Boolean(error) })}
      {hint && (
        <p id={hintId} className="text-xs text-muted">
          {hint}
        </p>
      )}
      {error && (
        <p id={errorId} className="text-sm font-medium text-danger">
          {error}
        </p>
      )}
    </div>
  );
}

const inputBase =
  'w-full rounded-xl border bg-white/90 px-3 py-2.5 text-ink placeholder:text-muted/80 focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/30';

export function TextField({
  label,
  error,
  hint,
  className = '',
  ...props
}: InputHTMLAttributes<HTMLInputElement> & { label: string; error?: string; hint?: string }) {
  return (
    <FieldShell label={label} error={error} hint={hint} required={props.required}>
      {({ id, describedBy, invalid }) => (
        <input
          id={id}
          aria-describedby={describedBy}
          aria-invalid={invalid || undefined}
          className={`${inputBase} ${invalid ? 'border-danger' : 'border-ink/15'} ${className}`}
          {...props}
        />
      )}
    </FieldShell>
  );
}

export function TextAreaField({
  label,
  error,
  hint,
  ...props
}: TextareaHTMLAttributes<HTMLTextAreaElement> & { label: string; error?: string; hint?: string }) {
  return (
    <FieldShell label={label} error={error} hint={hint} required={props.required}>
      {({ id, describedBy, invalid }) => (
        <textarea
          id={id}
          aria-describedby={describedBy}
          aria-invalid={invalid || undefined}
          className={`${inputBase} min-h-32 ${invalid ? 'border-danger' : 'border-ink/15'}`}
          {...props}
        />
      )}
    </FieldShell>
  );
}

export function SelectField({
  label,
  error,
  hint,
  children,
  ...props
}: SelectHTMLAttributes<HTMLSelectElement> & { label: string; error?: string; hint?: string }) {
  return (
    <FieldShell label={label} error={error} hint={hint} required={props.required}>
      {({ id, describedBy, invalid }) => (
        <select
          id={id}
          aria-describedby={describedBy}
          aria-invalid={invalid || undefined}
          className={`${inputBase} ${invalid ? 'border-danger' : 'border-ink/15'}`}
          {...props}
        >
          {children}
        </select>
      )}
    </FieldShell>
  );
}

const STATUS_STYLES: Record<string, string> = {
  applied: 'bg-primary-soft text-primary-strong',
  screening: 'bg-warning-soft text-warning',
  interview: 'bg-accent-soft text-accent',
  offer: 'bg-success-soft text-success',
  hired: 'bg-success-soft text-success',
  rejected: 'bg-canvas-deep text-muted',
  withdrawn: 'bg-canvas-deep text-muted',
  draft: 'bg-canvas-deep text-ink-soft',
  open: 'bg-success-soft text-success',
  closed: 'bg-canvas-deep text-muted',
};

export function StatusBadge({ status, label }: { status: string; label: string }) {
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold ${STATUS_STYLES[status] ?? 'bg-canvas-deep text-ink'}`}>
      {label}
    </span>
  );
}

export function Chip({ children }: { children: ReactNode }) {
  return (
    <span className="inline-flex items-center rounded-full border border-ink/10 bg-white/70 px-2.5 py-1 text-xs font-medium text-ink-soft">
      {children}
    </span>
  );
}

export function PageLoader({ label = 'Loading' }: { label?: string }) {
  return (
    <div role="status" className="flex min-h-40 items-center justify-center gap-3 text-muted">
      <span className="h-5 w-5 animate-spin rounded-full border-2 border-primary border-t-transparent motion-reduce:animate-none" aria-hidden="true" />
      <span>{label}…</span>
    </div>
  );
}

export function ErrorNote({ children }: { children: ReactNode }) {
  return (
    <div role="alert" className="rounded-xl border border-danger/30 bg-danger-soft px-4 py-3 text-sm text-danger">
      {children}
    </div>
  );
}

export function SuccessNote({ children }: { children: ReactNode }) {
  return (
    <div role="status" className="rounded-xl border border-success/30 bg-success-soft px-4 py-3 text-sm text-success">
      {children}
    </div>
  );
}

export function EmptyState({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="glass rounded-xl2 px-6 py-10 text-center">
      <p className="font-display text-lg font-semibold text-ink">{title}</p>
      {children && <div className="mt-2 text-muted">{children}</div>}
    </div>
  );
}

export function Pager({
  page,
  hasNext,
  hasPrevious,
  onChange,
}: {
  page: number;
  hasNext: boolean;
  hasPrevious: boolean;
  onChange: (page: number) => void;
}) {
  if (!hasNext && !hasPrevious) return null;
  return (
    <nav aria-label="Pagination" className="mt-6 flex items-center justify-between">
      <Button variant="secondary" disabled={!hasPrevious} onClick={() => onChange(page - 1)}>
        Previous
      </Button>
      <span className="text-sm text-muted">Page {page}</span>
      <Button variant="secondary" disabled={!hasNext} onClick={() => onChange(page + 1)}>
        Next
      </Button>
    </nav>
  );
}

export function StatTile({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="glass rounded-xl2 p-4">
      <p className="text-sm text-muted">{label}</p>
      <p className="mt-1 font-display text-3xl font-semibold text-ink">{value}</p>
    </div>
  );
}
