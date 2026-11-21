import '@testing-library/jest-dom/vitest';
import { afterEach, vi } from 'vitest';
import { cleanup } from '@testing-library/react';

// matchMedia that honours "(min-width: Npx)" against window.innerWidth.
function matchMedia(query: string): MediaQueryList {
  const min = /min-width:\s*(\d+)px/.exec(query);
  const matches = min ? window.innerWidth >= Number(min[1]) : false;
  return {
    matches,
    media: query,
    onchange: null,
    addEventListener: () => undefined,
    removeEventListener: () => undefined,
    addListener: () => undefined,
    removeListener: () => undefined,
    dispatchEvent: () => false,
  } as MediaQueryList;
}

Object.defineProperty(window, 'matchMedia', { writable: true, value: matchMedia });
window.scrollTo = () => undefined;
// jsdom has no canvas; axe only uses it to detect icon fonts.
HTMLCanvasElement.prototype.getContext = (() => null) as unknown as HTMLCanvasElement['getContext'];
document.documentElement.lang = 'en';

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  document.head.querySelectorAll('#jobposting-ld, link[rel="canonical"], meta[name="robots"]').forEach((el) => el.remove());
});
