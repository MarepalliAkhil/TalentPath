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
// No real sockets in unit tests.
class FakeSocket {
  onmessage: ((e: MessageEvent) => void) | null = null;
  onclose: (() => void) | null = null;
  close() {}
}
Object.defineProperty(window, 'WebSocket', { writable: true, value: FakeSocket });
HTMLCanvasElement.prototype.getContext = (() => null) as unknown as HTMLCanvasElement['getContext'];
// Recharts' ResponsiveContainer needs ResizeObserver, which jsdom lacks.
class FakeResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
}
Object.defineProperty(window, 'ResizeObserver', { writable: true, value: FakeResizeObserver });
// Speech synthesis for HIRA's spoken briefing.
class FakeUtterance {
  text: string;
  lang = '';
  constructor(text: string) {
    this.text = text;
  }
}
Object.defineProperty(window, 'SpeechSynthesisUtterance', { writable: true, value: FakeUtterance });
Object.defineProperty(window, 'speechSynthesis', {
  writable: true,
  value: { speak: vi.fn(), cancel: vi.fn() },
});
document.documentElement.lang = 'en';

afterEach(() => {
  cleanup();
  window.sessionStorage.clear();
  vi.unstubAllGlobals();
  document.head.querySelectorAll('#jobposting-ld, link[rel="canonical"], meta[name="robots"]').forEach((el) => el.remove());
});
