import type { IconName } from '@/lib/nav';

const PATHS: Record<
  IconName | 'menu' | 'close' | 'pin' | 'clock' | 'arrow' | 'check' | 'logout' | 'user' | 'chat' | 'lock' | 'grip' | 'thumbUp' | 'thumbDown' | 'send' | 'columns' | 'play' | 'volumeOff' | 'volume' | 'download',
  string
> = {
  home: 'M3 10.5 12 3l9 7.5V20a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z',
  briefcase: 'M9 6V4.5A1.5 1.5 0 0 1 10.5 3h3A1.5 1.5 0 0 1 15 4.5V6m-12 3h18v10a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2zm0 0a2 2 0 0 1 2-3h14a2 2 0 0 1 2 3M3 13h18',
  search: 'M11 4a7 7 0 1 0 0 14 7 7 0 0 0 0-14zm9 16-4.2-4.2',
  bell: 'M6 9a6 6 0 1 1 12 0c0 6 2.5 7.5 2.5 7.5h-17S6 15 6 9zm4 11a2 2 0 0 0 4 0',
  users: 'M16 19v-1a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v1m7-9a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7zm13 9v-1a4 4 0 0 0-3-3.9M16 3.1a3.5 3.5 0 0 1 0 6.8',
  building: 'M4 21V5a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v16m0-10h2a2 2 0 0 1 2 2v8M2 21h20M8 7h4M8 11h4M8 15h4',
  shield: 'M12 3 4 6v6c0 5 3.5 8 8 9 4.5-1 8-4 8-9V6zm-3 9 2 2 4-4',
  mail: 'M3 6h18v12H3zm0 0 9 7 9-7',
  layers: 'M12 3 2 8l10 5 10-5zM2 13l10 5 10-5',
  menu: 'M4 6h16M4 12h16M4 18h16',
  close: 'M6 6l12 12M18 6 6 18',
  pin: 'M12 21s-7-6.2-7-11.5a7 7 0 0 1 14 0C19 14.8 12 21 12 21zm0-9a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5z',
  clock: 'M12 7v5l3 2m6-2a9 9 0 1 1-18 0 9 9 0 0 1 18 0z',
  arrow: 'M5 12h14m-6-6 6 6-6 6',
  check: 'm5 12 4.5 4.5L19 7',
  logout: 'M15 4h3a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2h-3M10 16l-4-4 4-4m-4 4h12',
  user: 'M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8zm-7 9a7 7 0 0 1 14 0',
  scale: 'M12 3v18m-7 0h14M5 7h14M5 7l-3 7a3 3 0 0 0 6 0zm14 0-3 7a3 3 0 0 0 6 0z',
  chat: 'M4 5h16v11H9l-5 4zM8 9h8M8 12h5',
  lock: 'M6 11h12v9H6zm2 0V8a4 4 0 0 1 8 0v3',
  grip: 'M9 6h.01M15 6h.01M9 12h.01M15 12h.01M9 18h.01M15 18h.01',
  thumbUp: 'M7 11v9H4v-9zm0 0 4-7a2 2 0 0 1 2 2v3h5a2 2 0 0 1 2 2l-1.5 7a2 2 0 0 1-2 1.6H7',
  thumbDown: 'M17 13V4h3v9zm0 0-4 7a2 2 0 0 1-2-2v-3H6a2 2 0 0 1-2-2l1.5-7A2 2 0 0 1 7.5 4H17',
  send: 'm4 12 16-8-6 16-2-7z',
  columns: 'M4 5h4v14H4zm6 0h4v14h-4zm6 0h4v14h-4z',
  calendar: 'M7 3v3m10-3v3M4 8h16M5 5h14a1 1 0 0 1 1 1v13a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1zm3 7h2m4 0h2m-8 4h2',
  sparkle: 'M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8zM19 15l.8 2.2L22 18l-2.2.8L19 21l-.8-2.2L16 18l2.2-.8z',
  document: 'M7 3h7l5 5v12a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1zm7 0v5h5M9 13h6m-6 4h6',
  play: 'M7 5v14l11-7z',
  volumeOff: 'M4 9h4l5-4v14l-5-4H4zm12 0 5 6m0-6-5 6',
  volume: 'M4 9h4l5-4v14l-5-4H4zm12-1a5 5 0 0 1 0 8m2-11a9 9 0 0 1 0 14',
  download: 'M12 4v11m-5-5 5 5 5-5M5 20h14',
  sun: 'M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8zm0-5v2m0 14v2M3 12h2m14 0h2M5.6 5.6 7 7m10 10 1.4 1.4M5.6 18.4 7 17M17 7l1.4-1.4',
  clipboard: 'M9 4h6v3H9zM8 5H6a1 1 0 0 0-1 1v14a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V6a1 1 0 0 0-1-1h-2M9 13l2 2 4-4',
};

export type AnyIcon = keyof typeof PATHS;

export function Icon({ name, className = 'h-5 w-5' }: { name: AnyIcon; className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.8}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden="true"
      focusable="false"
    >
      <path d={PATHS[name]} />
    </svg>
  );
}
