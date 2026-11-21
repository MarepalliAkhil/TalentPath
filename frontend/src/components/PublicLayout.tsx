import { Link, NavLink, Outlet } from 'react-router-dom';
import { useAuth } from '@/auth/AuthContext';
import { brand } from '@/lib/brand';
import { BrandMark } from './BrandMark';
import { buttonClass } from './ui';

export function PublicLayout() {
  const { user } = useAuth();
  return (
    <div className="aurora flex min-h-dvh flex-col">
      <a href="#main" className="skip-link">
        Skip to content
      </a>
      <header className="glass-bar sticky top-0 z-20">
        <div className="mx-auto flex w-full max-w-6xl items-center gap-3 px-4 py-2 sm:px-6">
          <Link to="/" className="rounded-lg" aria-label={`${brand.name} home`}>
            <BrandMark />
          </Link>
          <nav aria-label="Site" className="ml-auto flex items-center gap-1 sm:gap-2">
            <NavLink
              to="/jobs"
              className={({ isActive }) =>
                `rounded-xl px-3 py-2 text-sm font-semibold ${isActive ? 'text-primary-strong' : 'text-ink-soft hover:text-ink'}`
              }
            >
              Jobs
            </NavLink>
            {user ? (
              <Link to={user.dashboard} className={buttonClass('primary', 'px-3')}>
                Dashboard
              </Link>
            ) : (
              <>
                <Link to="/login" className="rounded-xl px-3 py-2 text-sm font-semibold text-ink-soft hover:text-ink">
                  Sign in
                </Link>
                <Link to="/register" className={buttonClass('primary', 'hidden px-3 min-[400px]:inline-flex')}>
                  Create account
                </Link>
              </>
            )}
          </nav>
        </div>
      </header>
      <main id="main" tabIndex={-1} className="mx-auto w-full max-w-6xl flex-1 px-4 py-8 focus:outline-none sm:px-6 lg:py-12">
        <Outlet />
      </main>
      <footer className="border-t border-ink/10 bg-white/40">
        <div className="mx-auto flex max-w-6xl flex-col gap-2 px-4 py-6 text-sm text-muted sm:flex-row sm:justify-between sm:px-6">
          <p>
            {brand.name} · {brand.tagline}
          </p>
          <p>All people, companies and jobs here are fictional demo data.</p>
        </div>
      </footer>
    </div>
  );
}
