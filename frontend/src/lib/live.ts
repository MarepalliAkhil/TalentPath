import { useEffect, useRef } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { api } from './api';

export type LiveEvent =
  | { type: 'board'; event: string; job: string; application: string; status: string }
  | { type?: undefined; id: string; title: string; kind: string };

/**
 * One WebSocket per signed-in session. Gets a single-use ticket first (Vercel
 * cannot proxy sockets, so production connects straight to the Render host from
 * vercel.json, or VITE_WS_URL when set). Reconnects quietly; pages also poll, so nothing breaks
 * when sockets are unavailable.
 */
export function useLiveEvents(onEvent: (event: LiveEvent) => void, enabled = true): void {
  const handler = useRef(onEvent);
  handler.current = onEvent;
  useEffect(() => {
    if (!enabled || typeof WebSocket === 'undefined') return;
    let socket: WebSocket | null = null;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let stopped = false;
    const connect = async () => {
      try {
        const { ticket } = await api<{ ticket: string }>('/realtime/ticket', { method: 'POST' });
        if (stopped) return;
        const base =
          (import.meta.env.VITE_WS_URL as string | undefined) ||
          (import.meta.env.PROD ? __RENDER_WS_ORIGIN__ : '') ||
          `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.host}`;
        socket = new WebSocket(`${base}/ws/notifications?ticket=${encodeURIComponent(ticket)}`);
        socket.onmessage = (message) => {
          try {
            handler.current(JSON.parse(String(message.data)) as LiveEvent);
          } catch {
            /* ignore malformed frames */
          }
        };
        socket.onclose = () => {
          if (!stopped) timer = setTimeout(connect, 5_000);
        };
      } catch {
        if (!stopped) timer = setTimeout(connect, 20_000);
      }
    };
    void connect();
    return () => {
      stopped = true;
      clearTimeout(timer);
      socket?.close();
    };
  }, [enabled]);
}

/** Mounted once in the app shell: turns live events into cache refreshes. */
export function useLiveInvalidation(enabled: boolean): void {
  const client = useQueryClient();
  useLiveEvents((event) => {
    if (event.type === 'board') {
      void client.invalidateQueries({ queryKey: ['board', event.job] });
      void client.invalidateQueries({ queryKey: ['job-applications', event.job] });
      void client.invalidateQueries({ queryKey: ['application', event.application] });
    } else {
      void client.invalidateQueries({ queryKey: ['notifications'] });
    }
  }, enabled);
}
