import { useEffect, useId, useRef, useState, type KeyboardEvent } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '@/auth/AuthContext';
import { initials } from '@/lib/format';
import { Icon } from './Icon';

/** Profile menu: exactly two items, Profile and Log out. */
export function ProfileMenu() {
  const { user, logout } = useAuth();
  const [open, setOpen] = useState(false);
  const menuId = useId();
  const buttonRef = useRef<HTMLButtonElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const first = menuRef.current?.querySelector<HTMLElement>('[role="menuitem"]');
    first?.focus();
    const onPointer = (event: MouseEvent) => {
      if (!menuRef.current?.contains(event.target as Node) && !buttonRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', onPointer);
    return () => document.removeEventListener('mousedown', onPointer);
  }, [open]);

  if (!user) return null;

  const close = (refocus = true) => {
    setOpen(false);
    if (refocus) buttonRef.current?.focus();
  };

  const onMenuKey = (event: KeyboardEvent<HTMLDivElement>) => {
    const items = Array.from(menuRef.current?.querySelectorAll<HTMLElement>('[role="menuitem"]') ?? []);
    const index = items.indexOf(document.activeElement as HTMLElement);
    if (event.key === 'Escape') {
      event.preventDefault();
      close();
    } else if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault();
      const step = event.key === 'ArrowDown' ? 1 : -1;
      items[(index + step + items.length) % items.length]?.focus();
    } else if (event.key === 'Tab') {
      setOpen(false);
    }
  };

  const onLogout = async () => {
    setOpen(false);
    await logout(); // AppShell sees the signed-out state and redirects to /login
  };

  return (
    <div className="relative">
      <button
        ref={buttonRef}
        type="button"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={open ? menuId : undefined}
        onClick={() => setOpen((v) => !v)}
        className="flex min-h-11 items-center gap-2 rounded-full border border-ink/10 bg-white/80 py-1 pl-1 pr-3 text-sm font-medium text-ink hover:border-primary"
      >
        <span className="flex h-8 w-8 items-center justify-center rounded-full bg-ink text-xs font-semibold text-white" aria-hidden="true">
          {initials(user.full_name)}
        </span>
        <span className="hidden sm:inline">{user.full_name}</span>
        <span className="sr-only">Account menu for {user.full_name}</span>
      </button>
      {open && (
        <div
          ref={menuRef}
          id={menuId}
          role="menu"
          aria-label="Account"
          onKeyDown={onMenuKey}
          className="glass absolute right-0 z-50 mt-2 w-48 overflow-hidden rounded-xl p-1 shadow-lift"
        >
          <Link
            role="menuitem"
            to="/profile"
            onClick={() => close(false)}
            className="flex items-center gap-2 rounded-lg px-3 py-2.5 text-sm text-ink hover:bg-primary-soft focus:bg-primary-soft focus:outline-none"
          >
            <Icon name="user" className="h-4 w-4" /> Profile
          </Link>
          <button
            role="menuitem"
            type="button"
            onClick={onLogout}
            className="flex w-full items-center gap-2 rounded-lg px-3 py-2.5 text-left text-sm text-ink hover:bg-primary-soft focus:bg-primary-soft focus:outline-none"
          >
            <Icon name="logout" className="h-4 w-4" /> Log out
          </button>
        </div>
      )}
    </div>
  );
}
