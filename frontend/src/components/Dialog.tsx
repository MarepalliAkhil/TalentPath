import { useEffect, useId, useRef, type ReactNode } from 'react';
import { Icon } from './Icon';

// Only the topmost open dialog reacts to Escape.
const openDialogs: string[] = [];

/** Modal dialog: labelled, traps nothing fancy but moves focus in, Esc closes, focus returns. */
export function Dialog({
  title,
  onClose,
  children,
  variant = 'center',
  description,
}: {
  title: string;
  onClose: () => void;
  children: ReactNode;
  variant?: 'center' | 'drawer';
  description?: string;
}) {
  const id = useId();
  const panel = useRef<HTMLDivElement>(null);
  const opener = useRef<Element | null>(null);
  const close = useRef(onClose);
  close.current = onClose;

  useEffect(() => {
    opener.current = document.activeElement;
    const first = panel.current?.querySelector<HTMLElement>('[data-autofocus], button, select, input, textarea, a[href]');
    first?.focus();
    openDialogs.push(id);
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && openDialogs[openDialogs.length - 1] === id) {
        event.preventDefault();
        close.current();
      }
    };
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('keydown', onKey);
      openDialogs.splice(openDialogs.indexOf(id), 1);
      if (opener.current instanceof HTMLElement) opener.current.focus();
    };
  }, [id]);

  const layout =
    variant === 'drawer'
      ? 'fixed inset-y-0 right-0 w-full max-w-2xl overflow-y-auto rounded-none sm:rounded-l-xl2'
      : 'relative mx-auto mt-[8vh] max-h-[84vh] w-[calc(100%-2rem)] max-w-lg overflow-y-auto rounded-xl2';

  return (
    <div className="fixed inset-0 z-50">
      <div className="absolute inset-0 bg-ink/50" aria-hidden="true" onClick={onClose} />
      <div
        ref={panel}
        role="dialog"
        aria-modal="true"
        aria-labelledby={`${id}-title`}
        aria-describedby={description ? `${id}-desc` : undefined}
        className={`glass bg-white p-5 shadow-lift sm:p-6 ${layout}`}
      >
        <div className="mb-4 flex items-start justify-between gap-3">
          <div>
            <h2 id={`${id}-title`} className="font-display text-xl font-semibold text-ink">
              {title}
            </h2>
            {description && (
              <p id={`${id}-desc`} className="mt-1 text-sm text-muted">
                {description}
              </p>
            )}
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full text-ink-soft hover:bg-ink/5"
          >
            <Icon name="close" />
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}
