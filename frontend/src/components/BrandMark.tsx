import { brand } from '@/lib/brand';

export function BrandMark({ tone = 'dark' }: { tone?: 'dark' | 'light' }) {
  const text = tone === 'light' ? 'text-white' : 'text-ink';
  return (
    <span className={`inline-flex items-center gap-2 font-display text-lg font-semibold tracking-tight ${text}`}>
      <svg viewBox="0 0 32 32" className="h-7 w-7" aria-hidden="true" focusable="false">
        <rect width="32" height="32" rx="9" className="fill-primary" />
        <path d="M7 22c5 0 6-12 11-12s4 7 7 7" fill="none" stroke="white" strokeWidth="3" strokeLinecap="round" />
        <circle cx="7" cy="22" r="2.6" className="fill-accent-soft" />
      </svg>
      {brand.name}
    </span>
  );
}
