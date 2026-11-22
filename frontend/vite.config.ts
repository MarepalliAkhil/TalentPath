/// <reference types="vitest/config" />
import { fileURLToPath } from 'node:url';
import react from '@vitejs/plugin-react';
import { defineConfig, type Plugin } from 'vite';
import brand from '../shared/brand.json';

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

const backend = process.env.VITE_API_PROXY ?? 'http://localhost:8000';

export default defineConfig({
  plugins: [react(), brandHtml()],
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
