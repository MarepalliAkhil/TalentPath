import { useEffect, useRef, useState } from 'react';
import { Link, Navigate, NavLink, Outlet, useLocation } from 'react-router-dom';
import { useAuth } from '@/auth/AuthContext';
import { useMediaQuery } from '@/lib/hooks';
import { useLiveInvalidation } from '@/lib/live';
import { AskHira } from './AskHira';
import { HiraBriefing } from './HiraBriefing';
import { navFor } from '@/lib/nav';
import type { User } from '@/lib/types';
import { BrandMark } from './BrandMark';
import { Icon } from './Icon';
import { NotificationBell } from './NotificationBell';
import { ProfileMenu } from './ProfileMenu';
import { PageLoader } from './ui';

function Sidebar({ user }: { user: User }) {
  const items = navFor(user.role);
  return (
    <div className="flex h-full flex-col">
      <Link to={user.dashboard} className="mb-8 rounded-lg px-2 focus-visible:outline-white">
        <BrandMark tone="light" />
      </Link>
      <nav aria-label="Main">
        <ul className="flex flex-col gap-1">
          {items.map((item) => (
            <li key={item.to}>
              <NavLink
                to={item.to}
                end
                className={({ isActive }) =>
                  `group relative flex min-h-11 items-center gap-3 rounded-xl px-3 text-sm font-medium transition-colors ${
                    isActive ? 'bg-white/10 text-white' : 'text-white/75 hover:bg-white/5 hover:text-white'
                  }`
                }
              >
                {({ isActive }) => (
                  <>
                    <span
                      aria-hidden="true"
                      className={`absolute left-0 top-2 bottom-2 w-1 rounded-full ${isActive ? 'bg-accent-soft' : 'bg-transparent'}`}
                    />
                    <Icon name={item.icon} />
                    {item.label}
                  </>
                )}
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>
      <p className="mt-auto rounded-xl bg-white/5 p-3 text-xs leading-relaxed text-white/75">
        Signed in as <span className="font-semibold text-white">{user.role_label}</span>
      </p>
    </div>
  );
}

/** One layout for every signed-in role: left sidebar, top bar with bell and profile menu. */
export function AppShell() {
  const { user, loading, signedOut } = useAuth();
  useLiveInvalidation(Boolean(user));
  const isDesktop = useMediaQuery('(min-width: 1024px)');
  const [open, setOpen] = useState(false);
  const location = useLocation();
  const closeRef = useRef<HTMLButtonElement>(null);
  const openRef = useRef<HTMLButtonElement>(null);

  useEffect(() => setOpen(false), [location.pathname]);
  useEffect(() => {
    if (!open) return;
    closeRef.current?.focus();
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setOpen(false);
        openRef.current?.focus();
      }
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [open]);

  if (loading) return <PageLoader />;
  if (!user) {
    const to = signedOut ? '/login' : `/login?next=${encodeURIComponent(location.pathname)}`;
    return <Navigate to={to} replace />;
  }

  return (
    <div className="aurora min-h-dvh">
      <a href="#main" className="skip-link">
        Skip to content
      </a>
      {isDesktop && (
        <aside className="sidebar fixed inset-y-0 left-0 z-30 w-64 p-5">
          <Sidebar user={user} />
        </aside>
      )}
      {!isDesktop && open && (
        <div className="fixed inset-0 z-40" role="dialog" aria-modal="true" aria-label="Main menu" id="mobile-nav">
          <div className="absolute inset-0 bg-ink/50" aria-hidden="true" onClick={() => setOpen(false)} />
          <div className="sidebar relative h-full w-72 max-w-[85vw] p-5 shadow-lift">
            <button
              ref={closeRef}
              type="button"
              onClick={() => setOpen(false)}
              aria-label="Close menu"
              className="absolute right-3 top-3 flex h-11 w-11 items-center justify-center rounded-full text-white/80 hover:bg-white/10"
            >
              <Icon name="close" />
            </button>
            <Sidebar user={user} />
          </div>
        </div>
      )}
      <div className={isDesktop ? 'pl-64' : ''}>
        <header className="glass-bar sticky top-0 z-20 flex items-center gap-2 px-3 py-2 sm:px-6">
          {!isDesktop && (
            <>
              <button
                ref={openRef}
                type="button"
                aria-label="Open menu"
                aria-expanded={open}
                aria-controls={open ? 'mobile-nav' : undefined}
                onClick={() => setOpen(true)}
                className="flex h-11 w-11 items-center justify-center rounded-full text-ink hover:bg-ink/5"
              >
                <Icon name="menu" />
              </button>
              <Link to={user.dashboard} className="rounded-lg">
                <BrandMark />
              </Link>
            </>
          )}
          <div className="ml-auto flex items-center gap-2">
            <NotificationBell />
            <ProfileMenu />
          </div>
        </header>
        <main id="main" tabIndex={-1} className="mx-auto w-full max-w-6xl px-4 pb-24 pt-6 focus:outline-none sm:px-6 lg:px-10 lg:pb-24 lg:pt-10">
          <Outlet />
        </main>
      </div>
      {/* Candidates ask about jobs and applications; staff also get HR answers (week 3B). */}
      <AskHira />
      {(user.role === 'recruiter' || user.role === 'hr_admin') && <HiraBriefing />}
    </div>
  );
}
