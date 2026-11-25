/// <reference types="vitest/config" />
import { copyFileSync, existsSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import react from '@vitejs/plugin-react';
import { defineConfig, type Plugin } from 'vite';
import brand from '../shared/brand.json';
import { collectRepoFacts } from './build/repoFacts';
import { readVercelConfig, vercelConfigProblems, websocketOrigin } from './build/vercelConfig';

const vercel = readVercelConfig(fileURLToPath(new URL('./vercel.json', import.meta.url)));

/** Fills %BRAND_*% placeholders in index.html from shared/brand.json. */
function brandHtml(): Plugin {
  return {
    name: 'brand-html',
    transformIndexHtml(html) {
      return html
        .replaceAll('%BRAND_NAME%', brand.name)
        .replaceAll('%BRAND_TAGLINE%', brand.tagline)
        .replaceAll('%BRAND_PRIMARY%', brand.colors.primary);
    },
  };
}

/** `virtual:repo-facts`: test counts, permissions and measured evaluation results read from the repo. */
function repoFacts(): Plugin {
  const id = 'virtual:repo-facts';
  const root = fileURLToPath(new URL('..', import.meta.url));
  return {
    name: 'repo-facts',
    resolveId(source) {
      return source === id ? `\0${id}` : null;
    },
    load(resolved) {
      if (resolved !== `\0${id}`) return null;
      return `export default ${JSON.stringify(collectRepoFacts(root))};`;
    },
  };
}

/**
 * Deployment guard and real 404s:
 * - on Vercel (VERCEL=1) the build fails while vercel.json still names the placeholder Render URL;
 * - dist/404.html is a copy of index.html, so unknown paths get a real 404 status and the app's
 *   own "page not found" screen.
 */
function deployment(): Plugin {
  let outDir = 'dist';
  return {
    name: 'talentpath-deployment',
    apply: 'build',
    configResolved(config) {
      outDir = config.build.outDir;
    },
    buildStart() {
      const problems = vercelConfigProblems(vercel);
      if (!problems.length) return;
      if (process.env.VERCEL === '1') this.error(problems.join(' '));
      this.warn(`Not deployable yet: ${problems.join(' ')}`);
    },
    closeBundle() {
      const index = join(outDir, 'index.html');
      if (existsSync(index)) copyFileSync(index, join(outDir, '404.html'));
    },
  };
}

const backend = process.env.VITE_API_PROXY ?? 'http://localhost:8000';

export default defineConfig({
  plugins: [react(), brandHtml(), repoFacts(), deployment()],
  define: {
    // Live updates connect straight to Render (Vercel cannot proxy WebSockets). Derived from the
    // single Render URL in vercel.json; VITE_WS_URL still wins when set.
    __RENDER_WS_ORIGIN__: JSON.stringify(websocketOrigin(vercel)),
  },
  build: {
    sourcemap: false, // never ship source maps to production
  },
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
      '@shared': fileURLToPath(new URL('../shared', import.meta.url)),
    },
  },
  server: {
    port: 5173,
    fs: { allow: ['..'] },
    proxy: {
      '/api': { target: backend, changeOrigin: false },
      '/sitemap.xml': { target: backend, changeOrigin: false },
      '/robots.txt': { target: backend, changeOrigin: false },
      // Live board and bell updates (runserver serves WebSockets via daphne).
      '/ws': { target: backend.replace(/^http/, 'ws'), ws: true, changeOrigin: false },
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
    include: ['src/**/*.test.{ts,tsx}'],
    css: false,
  },
});
