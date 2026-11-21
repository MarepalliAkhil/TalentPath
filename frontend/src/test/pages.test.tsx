import { screen } from '@testing-library/react';
import { beforeEach, describe, expect, it } from 'vitest';
import { job, publicApi } from './fixtures';
import { axeViolations, mockApi, renderApp, setViewport } from './utils';

describe('public pages', () => {
  beforeEach(() => {
    mockApi(publicApi);
    setViewport(390);
  });

  it('home renders one h1, latest jobs and is axe clean', async () => {
    renderApp('/');
    expect(screen.getAllByRole('heading', { level: 1 })).toHaveLength(1);
    expect(await screen.findByRole('link', { name: 'Backend Engineer' })).toBeInTheDocument();
    expect(await axeViolations()).toEqual([]);
  });

  it('job search lists results with a live count', async () => {
    renderApp('/jobs?skill=Py');
    expect(screen.getByRole('heading', { level: 1, name: 'Open roles' })).toBeInTheDocument();
    expect(await screen.findByText('1 role found')).toBeInTheDocument();
    expect(screen.getByLabelText('Skill')).toHaveValue('Py');
    expect(await axeViolations()).toEqual([]);
  });

  it('job detail sets title, meta description, canonical and JSON-LD', async () => {
    renderApp(`/jobs/${job.slug}`);
    expect(await screen.findByRole('heading', { level: 1, name: job.title })).toBeInTheDocument();
    expect(document.title).toBe(job.seo?.title);
    expect(document.head.querySelector('meta[name="description"]')).toHaveAttribute('content', job.seo?.description);
    expect(document.head.querySelector('link[rel="canonical"]')).toHaveAttribute('href', job.seo?.canonical);
    const ld = JSON.parse(document.getElementById('jobposting-ld')?.textContent ?? '{}');
    expect(ld['@type']).toBe('JobPosting');
    expect(screen.getAllByRole('heading', { level: 1 })).toHaveLength(1);
    expect(await axeViolations()).toEqual([]);
  });

  it('unknown paths get a real 404 page marked noindex', async () => {
    renderApp('/definitely/not/here');
    expect(screen.getByRole('heading', { level: 1, name: 'Page not found' })).toBeInTheDocument();
    expect(document.head.querySelector('meta[name="robots"]')).toHaveAttribute('content', 'noindex');
    expect(await axeViolations()).toEqual([]);
  });

  it('unknown job slugs show the 404 page', async () => {
    renderApp('/jobs/no-such-job');
    expect(await screen.findByRole('heading', { level: 1, name: 'Page not found' })).toBeInTheDocument();
  });

  it.each(['/login', '/register', '/forgot-password', '/reset-password?uid=a&token=b', '/demo-inbox'])(
    '%s has exactly one h1 and no axe violations',
    async (path) => {
      renderApp(path);
      expect(screen.getAllByRole('heading', { level: 1 })).toHaveLength(1);
      expect(await axeViolations()).toEqual([]);
    },
  );
});
