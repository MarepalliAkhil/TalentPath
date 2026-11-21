import { Link } from 'react-router-dom';
import { buttonClass } from '@/components/ui';
import { useDocumentTitle, useNoIndex } from '@/lib/hooks';

export function NotFoundPage() {
  useDocumentTitle('Page not found');
  useNoIndex();
  return (
    <section className="mx-auto max-w-xl py-10 text-center">
      <p className="font-display text-7xl font-semibold text-primary/30" aria-hidden="true">
        404
      </p>
      <h1 className="mt-2 font-display text-3xl font-semibold text-ink">Page not found</h1>
      <p className="mt-3 text-muted">
        This path leads nowhere. The job may have closed, or the link may be mistyped.
      </p>
      <div className="mt-6 flex flex-wrap justify-center gap-2">
        <Link to="/jobs" className={buttonClass('primary')}>
          Browse open jobs
        </Link>
        <Link to="/" className={buttonClass('secondary')}>
          Go home
        </Link>
      </div>
    </section>
  );
}
