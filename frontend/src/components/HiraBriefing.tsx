import { useEffect, useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { useAuth } from '@/auth/AuthContext';
import { api } from '@/lib/api';
import { assistant } from '@/lib/brand';
import { readSetting, speak, writeSetting } from '@/lib/interviews';
import type { HiraBriefing as Briefing } from '@/lib/types';
import { Dialog } from './Dialog';
import { HiraAvatar } from './HiraAvatar';
import { Icon } from './Icon';
import { Button, buttonClass } from './ui';

const MUTE_KEY = 'hira-voice-muted';

function sessionKey(userId: string) {
  return `hira-briefing-shown:${userId}`;
}

function alreadyShown(userId: string): boolean {
  try {
    return window.sessionStorage.getItem(sessionKey(userId)) === '1';
  } catch {
    return false;
  }
}

function markShown(userId: string) {
  try {
    window.sessionStorage.setItem(sessionKey(userId), '1');
  } catch {
    /* ignore */
  }
}

const COUNT_LABELS: Record<string, string> = {
  interview_scheduled: 'Interviews scheduled',
  reschedule_handled: 'Reschedules handled',
  interviewer_replaced: 'Interviewers replaced',
  scorecard_chased: 'Scorecards chased',
  reminder_sent: 'Reminders sent',
};

/** HIRA's login briefing for recruiters and HR: once per browser session. */
export function HiraBriefing() {
  const { user } = useAuth();
  const eligible = !!user && (user.role === 'recruiter' || user.role === 'hr');
  const [open, setOpen] = useState(() => eligible && !!user && !alreadyShown(user.id));
  const [muted, setMuted] = useState(() => readSetting(MUTE_KEY) === '1');
  const briefing = useQuery({
    queryKey: ['hira-briefing'],
    queryFn: () => api<Briefing>('/hira/briefing'),
    enabled: open,
    staleTime: Infinity,
  });
  const seen = useMutation({ mutationFn: () => api('/hira/briefing', { method: 'POST' }) });

  useEffect(() => {
    if (open && user) markShown(user.id);
  }, [open, user]);

  if (!eligible || !open || !briefing.data) return null;
  const data = briefing.data;

  const close = () => {
    setOpen(false);
    seen.mutate();
    if ('speechSynthesis' in window) window.speechSynthesis.cancel();
  };
  const toggleMute = () => {
    const next = !muted;
    setMuted(next);
    writeSetting(MUTE_KEY, next ? '1' : '0');
    if (next && 'speechSynthesis' in window) window.speechSynthesis.cancel();
  };
  const counts = Object.entries(COUNT_LABELS).filter(([key]) => (data.counts[key] ?? 0) > 0);

  return (
    <Dialog title={`${assistant.name} briefing`} description={assistant.display} onClose={close}>
      <div className="flex items-start gap-4">
        <HiraAvatar pose={data.needs_you_count ? 'attention' : 'welcome'} size={64} />
        <p className="text-ink" data-testid="hira-message">
          {data.message}
        </p>
      </div>
      {counts.length > 0 && (
        <dl className="mt-4 grid grid-cols-2 gap-2">
          {counts.map(([key, label]) => (
            <div key={key} className="rounded-xl bg-canvas p-3">
              <dt className="text-xs text-muted">{label}</dt>
              <dd className="font-display text-xl font-semibold text-ink">{data.counts[key]}</dd>
            </div>
          ))}
        </dl>
      )}
      {data.needs_you.length > 0 && (
        <section className="mt-4" aria-labelledby="needs-you-heading">
          <h3 id="needs-you-heading" className="text-sm font-semibold uppercase tracking-wide text-accent">
            Needs you
          </h3>
          <ul className="mt-2 space-y-2">
            {data.needs_you.map((item) => (
              <li key={item.id} className="rounded-xl border border-accent/30 bg-accent-soft/60 p-3 text-sm">
                <p className="font-semibold text-ink">{item.label}</p>
                <p className="text-ink-soft">
                  {item.candidate} · {item.job?.title} {item.round && `· ${item.round}`}
                </p>
                {item.link && (
                  <Link to={item.link} onClick={close} className="font-semibold text-primary-strong underline">
                    Open
                  </Link>
                )}
              </li>
            ))}
          </ul>
        </section>
      )}
      <div className="mt-5 flex flex-wrap items-center gap-2">
        <Link to="/hira" onClick={close} className={buttonClass('primary')}>
          Open HIRA activity
        </Link>
        <Button variant="secondary" onClick={() => speak(data.spoken)} disabled={muted} aria-label="Play spoken briefing">
          <Icon name="play" className="h-4 w-4" /> Play
        </Button>
        <Button variant="ghost" onClick={toggleMute} aria-pressed={muted}>
          <Icon name={muted ? 'volumeOff' : 'volume'} className="h-4 w-4" /> {muted ? 'Voice muted' : 'Mute voice'}
        </Button>
      </div>
    </Dialog>
  );
}
