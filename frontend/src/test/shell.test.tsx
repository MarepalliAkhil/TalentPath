import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it } from 'vitest';
import { ROLES } from '@/lib/policy';
import { EXPECTED_NAV, signedInApi } from './fixtures';
import { axeViolations, mockApi, renderApp, setViewport } from './utils';

describe('shared sidebar layout', () => {
  beforeEach(() => {
    mockApi(signedInApi);
    setViewport(1280);
  });

  it.each([...ROLES])('shows the right sidebar for %s', async (role) => {
    renderApp(`/${{ candidate: 'candidate', recruiter: 'recruiter', hiring_manager: 'manager', employee: 'employee', hr_admin: 'admin' }[role]}`, role);
    const nav = await screen.findByRole('navigation', { name: 'Main' });
    const labels = within(nav).getAllByRole('link').map((a) => a.textContent?.trim());
    expect(labels).toEqual(EXPECTED_NAV[role]);
    expect(screen.getAllByRole('heading', { level: 1 })).toHaveLength(1);
  });

  it('profile menu has exactly Profile and Log out', async () => {
    renderApp('/employee', 'employee');
    await userEvent.click(screen.getByRole('button', { name: /account menu/i }));
    const menu = screen.getByRole('menu', { name: 'Account' });
    expect(within(menu).getAllByRole('menuitem').map((i) => i.textContent?.trim())).toEqual(['Profile', 'Log out']);
    await userEvent.keyboard('{Escape}');
    expect(screen.queryByRole('menu')).not.toBeInTheDocument();
  });

  it('redirects a role away from another role’s area', async () => {
    renderApp('/admin', 'candidate');
    expect(await screen.findByRole('heading', { level: 1, name: 'My applications' })).toBeInTheDocument();
  });

  it('sends anonymous visitors to sign in', async () => {
    renderApp('/recruiter', null);
    expect(await screen.findByRole('heading', { level: 1, name: 'Sign in' })).toBeInTheDocument();
  });

  it('is axe clean on desktop', async () => {
    renderApp('/recruiter', 'recruiter');
    await screen.findByRole('heading', { level: 1 });
    expect(await axeViolations()).toEqual([]);
  });
});

describe('mobile at 390 px', () => {
  beforeEach(() => {
    mockApi(signedInApi);
    setViewport(390);
  });

  it('hides the sidebar behind a menu button and opens it as a dialog', async () => {
    renderApp('/candidate', 'candidate');
    await screen.findByRole('heading', { level: 1, name: 'My applications' });
    expect(screen.queryByRole('navigation', { name: 'Main' })).not.toBeInTheDocument();
    const toggle = screen.getByRole('button', { name: 'Open menu' });
    expect(toggle).toHaveAttribute('aria-expanded', 'false');
    await userEvent.click(toggle);
    const dialog = screen.getByRole('dialog', { name: 'Main menu' });
    expect(within(dialog).getByRole('link', { name: /Browse jobs/ })).toBeInTheDocument();
    expect(await axeViolations()).toEqual([]);
    await userEvent.click(within(dialog).getByRole('button', { name: 'Close menu' }));
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('public pages are axe clean at 390 px', async () => {
    renderApp('/', null);
    await screen.findByRole('heading', { level: 1 });
    expect(await axeViolations()).toEqual([]);
  });
});
