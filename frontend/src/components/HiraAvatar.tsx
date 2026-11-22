import { useState } from 'react';
import { assistant } from '@/lib/brand';

export type HiraPose = 'welcome' | 'explain' | 'attention' | 'celebrate' | 'thinking';

/**
 * HIRA's character image from /hira/ (see docs/HIRA.md for the file slots).
 * Tries the pose file, then hira.webp, then falls back to a clean "HI" initials
 * avatar in brand colours, so a missing file never shows a broken image.
 */
export function HiraAvatar({ pose, size = 56 }: { pose?: HiraPose; size?: number }) {
  const sources = [...(pose ? [`/hira/hira-${pose}.webp`] : []), '/hira/hira.webp'];
  const [index, setIndex] = useState(0);
  const style = { width: size, height: size };
  if (index >= sources.length) {
    return (
      <span
        aria-hidden="true"
        style={style}
        className="inline-flex shrink-0 select-none items-center justify-center rounded-full bg-gradient-to-br from-primary to-primary-strong font-display font-semibold text-white shadow-lift"
      >
        <span style={{ fontSize: Math.round(size * 0.36) }}>HI</span>
      </span>
    );
  }
  return (
    <img
      src={sources[index]}
      alt=""
      aria-hidden="true"
      width={size}
      height={size}
      style={style}
      className="shrink-0 rounded-full bg-primary-soft object-cover"
      onError={() => setIndex((i) => i + 1)}
      data-testid="hira-image"
      title={assistant.display}
    />
  );
}
