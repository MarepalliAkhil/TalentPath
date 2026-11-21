import type { ReactNode } from 'react';

export function AuthCard({ title, intro, children, footer }: { title: string; intro?: ReactNode; children: ReactNode; footer?: ReactNode }) {
  return (
    <div className="mx-auto w-full max-w-md">
      <div className="glass rounded-xl2 p-6 sm:p-8">
        <h1 className="font-display text-2xl font-semibold tracking-tight text-ink">{title}</h1>
        {intro && <p className="mt-1 text-muted">{intro}</p>}
        <div className="mt-6">{children}</div>
      </div>
      {footer && <div className="mt-4 text-center text-sm text-muted">{footer}</div>}
    </div>
  );
}
