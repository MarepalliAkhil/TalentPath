import type { Config } from 'tailwindcss';
import plugin from 'tailwindcss/plugin';
import brand from '../shared/brand.json';

const kebab = (key: string) => key.replace(/[A-Z]/g, (m) => `-${m.toLowerCase()}`);
const rgb = (hex: string) => {
  const n = parseInt(hex.slice(1), 16);
  return `${(n >> 16) & 255} ${(n >> 8) & 255} ${n & 255}`;
};

const entries = Object.entries(brand.colors);
const colors = Object.fromEntries(entries.map(([key]) => [kebab(key), `rgb(var(--c-${kebab(key)}) / <alpha-value>)`]));
const cssVars = Object.fromEntries(entries.map(([key, hex]) => [`--c-${kebab(key)}`, rgb(hex)]));

export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors,
      fontFamily: {
        sans: ['"Segoe UI Variable Text"', '"SF Pro Text"', 'Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        display: ['"Segoe UI Variable Display"', '"SF Pro Display"', 'Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
      },
      boxShadow: {
        glass: '0 1px 0 rgb(255 255 255 / 0.7) inset, 0 12px 40px -12px rgb(11 27 43 / 0.18)',
        lift: '0 18px 50px -20px rgb(11 27 43 / 0.35)',
      },
      borderRadius: { xl2: '1.25rem' },
      keyframes: { sheet: { from: { transform: 'translateY(16px)', opacity: '0' }, to: { transform: 'none', opacity: '1' } } },
    },
  },
  plugins: [plugin(({ addBase }) => addBase({ ':root': cssVars }))],
} satisfies Config;
