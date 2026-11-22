import { useEffect, useId, useRef, useState, type FormEvent } from 'react';
import { useMutation } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { useAuth } from '@/auth/AuthContext';
import { api } from '@/lib/api';
import { assistant } from '@/lib/brand';
import type { HiraReply } from '@/lib/types';
import { HrCardView } from './hr';
import { Icon } from './Icon';
import { errorText } from '@/lib/pipeline';
import { Button } from './ui';

type Turn = { id: number; from: 'you' | 'hira'; text: string; reply?: HiraReply };

const START_CHIPS_PUBLIC = ['Find React jobs in Hyderabad', 'How does matching work?', 'Is the screening fair?'];
const START_CHIPS_CANDIDATE = ['What is my application status?', 'Jobs that match my skills', 'Talk to a recruiter'];
const START_CHIPS_STAFF = ['My leave balance', 'Apply casual leave next Friday', 'Upcoming holidays'];

function RecruiterMessage({ reply, onSent }: { reply: HiraReply; onSent: (text: string) => void }) {
  const id = useId();
  const [application, setApplication] = useState(reply.applications[0]?.id ?? '');
  const [message, setMessage] = useState('');
  const send = useMutation({
    mutationFn: () => api<{ detail: string }>('/hira/message', { method: 'POST', body: { application, message } }),
    onSuccess: (data) => onSent(data.detail),
  });
  return (
    <form
      className="mt-2 flex flex-col gap-2 rounded-xl bg-white p-3"
      onSubmit={(e) => {
        e.preventDefault();
        if (message.trim()) send.mutate();
      }}
    >
      <label htmlFor={`${id}-app`} className="text-xs font-semibold text-ink">
        Application
      </label>
      <select id={`${id}-app`} value={application} onChange={(e) => setApplication(e.target.value)} className="min-h-10 rounded-lg border border-ink/15 px-2 text-sm">
        {reply.applications.map((a) => (
          <option key={a.id} value={a.id}>
            {a.title} ({a.status_label})
          </option>
        ))}
      </select>
      <label htmlFor={`${id}-msg`} className="text-xs font-semibold text-ink">
        Message for the recruiter
      </label>
      <textarea id={`${id}-msg`} rows={2} maxLength={1000} value={message} onChange={(e) => setMessage(e.target.value)} className="rounded-lg border border-ink/15 p-2 text-sm" />
      {send.isError && <p className="text-xs text-danger">{errorText(send.error)}</p>}
      <Button type="submit" className="min-h-9 self-start px-3" disabled={!message.trim() || send.isPending}>
        Send to recruiter
      </Button>
    </form>
  );
}

function ReplyBody({ reply, onChip, onSent }: { reply: HiraReply; onChip: (text: string) => void; onSent: (t: string) => void }) {
  return (
    <>
      {reply.jobs.length > 0 && (
        <ul className="mt-2 space-y-1.5" aria-label="Jobs">
          {reply.jobs.map((job) => (
            <li key={job.slug}>
              <Link to={`/jobs/${job.slug}`} className="block rounded-lg bg-white px-3 py-2 text-sm hover:ring-2 hover:ring-primary/30">
                <span className="font-semibold text-ink">{job.title}</span>
                <span className="block text-xs text-muted">
                  {job.location.name} · {job.work_mode_label}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
      {reply.applications.length > 0 && !reply.action && (
        <ul className="mt-2 space-y-1 text-sm" aria-label="Your applications">
          {reply.applications.map((a) => (
            <li key={a.id} className="flex justify-between gap-2 rounded-lg bg-white px-3 py-1.5">
              <span className="text-ink">{a.title}</span>
              <span className="font-semibold text-primary-strong">{a.status_label}</span>
            </li>
          ))}
        </ul>
      )}
      {reply.action?.type === 'message_recruiter' && <RecruiterMessage reply={reply} onSent={onSent} />}
      {reply.card && <HrCardView card={reply.card} onSent={onSent} />}
      {reply.link && (
        <Link to={reply.link} className="mt-2 inline-block text-sm font-semibold text-primary-strong underline">
          {reply.needs_sign_in ? 'Sign in' : 'Open'}
        </Link>
      )}
      <div className="mt-2 flex flex-wrap gap-1.5">
        {reply.chips.slice(0, 3).map((chip) => (
          <button key={chip} type="button" onClick={() => onChip(chip)} className="rounded-full border border-primary/30 bg-white px-2.5 py-1 text-xs font-medium text-primary-strong hover:bg-primary-soft">
            {chip}
          </button>
        ))}
      </div>
    </>
  );
}

export function AskHira() {
  const { user } = useAuth();
  const [open, setOpen] = useState(false);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [text, setText] = useState('');
  const counter = useRef(0);
  const launcher = useRef<HTMLButtonElement>(null);
  const input = useRef<HTMLInputElement>(null);
  const log = useRef<HTMLDivElement>(null);
  const titleId = useId();
  const isCandidate = user?.role === 'candidate';
  const isStaff = Boolean(user && user.role !== 'candidate');

  const ask = useMutation({
    mutationFn: (message: string) => api<HiraReply>('/hira/ask', { method: 'POST', body: { message } }),
    onSuccess: (reply) => add({ from: 'hira', text: reply.answer, reply }),
    onError: (e) => add({ from: 'hira', text: errorText(e) }),
  });

  function add(turn: Omit<Turn, 'id'>) {
    counter.current += 1;
    setTurns((t) => [...t, { ...turn, id: counter.current }]);
  }

  const send = (message: string) => {
    const clean = message.trim();
    if (!clean || ask.isPending) return;
    add({ from: 'you', text: clean });
    setText('');
    ask.mutate(clean);
  };

  useEffect(() => {
    if (open) input.current?.focus();
  }, [open]);
  useEffect(() => {
    // Keep the newest message in view (scrollTop works in every browser and in jsdom).
    if (log.current) log.current.scrollTop = log.current.scrollHeight;
  }, [turns]);
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setOpen(false);
        launcher.current?.focus();
      }
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [open]);

  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    send(text);
  };
  const starters = isCandidate ? START_CHIPS_CANDIDATE : isStaff ? START_CHIPS_STAFF : START_CHIPS_PUBLIC;

  return (
    <>
      <button
        ref={launcher}
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-controls={open ? `${titleId}-panel` : undefined}
        className="fixed bottom-4 right-4 z-40 inline-flex min-h-12 items-center gap-2 rounded-full bg-ink px-4 font-semibold text-white shadow-lift hover:bg-ink-soft"
      >
        <Icon name="chat" /> Ask {assistant.name}
      </button>
      {open && (
        <div
          id={`${titleId}-panel`}
          role="dialog"
          aria-labelledby={titleId}
          className="fixed inset-x-0 bottom-0 z-50 flex max-h-[85dvh] flex-col rounded-t-xl2 border border-white/70 bg-canvas shadow-lift motion-safe:animate-[sheet_200ms_ease-out] sm:inset-x-auto sm:bottom-20 sm:right-4 sm:w-96 sm:rounded-xl2"
        >
          <div className="flex items-start justify-between gap-2 border-b border-ink/10 p-4">
            <div>
              <h2 id={titleId} className="font-display text-lg font-semibold text-ink">
                Ask {assistant.name}
              </h2>
              <p className="text-xs text-muted">{assistant.fullName}</p>
            </div>
            <button
              type="button"
              aria-label={`Close Ask ${assistant.name}`}
              onClick={() => {
                setOpen(false);
                launcher.current?.focus();
              }}
              className="flex h-11 w-11 items-center justify-center rounded-full text-ink-soft hover:bg-ink/5"
            >
              <Icon name="close" />
            </button>
          </div>
          <div ref={log} role="log" aria-live="polite" aria-label="Conversation" className="flex-1 space-y-3 overflow-y-auto p-4">
            {turns.length === 0 && (
              <div className="rounded-xl bg-primary-soft p-3 text-sm text-primary-strong">
                {isStaff ? (
                  <>Hi, I am {assistant.name}. Ask about your leave, holidays, attendance, onboarding or HR policies. I only ever show your own data.</>
                ) : (
                  <>
                    Hi, I am {assistant.name}. Ask about jobs, how matching works
                    {isCandidate ? ' or where your applications stand.' : '. Sign in to check your applications.'}
                  </>
                )}
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {starters.map((chip) => (
                    <button key={chip} type="button" onClick={() => send(chip)} className="rounded-full border border-primary/30 bg-white px-2.5 py-1 text-xs font-medium hover:bg-primary-soft">
                      {chip}
                    </button>
                  ))}
                </div>
              </div>
            )}
            {turns.map((turn) => (
              <div key={turn.id} className={turn.from === 'you' ? 'ml-8 text-right' : 'mr-4'}>
                <p className="sr-only">{turn.from === 'you' ? 'You said:' : `${assistant.name} said:`}</p>
                <div className={`inline-block rounded-xl px-3 py-2 text-left text-sm ${turn.from === 'you' ? 'bg-ink text-white' : 'bg-white/80 text-ink'}`}>
                  {turn.text}
                  {turn.reply && <ReplyBody reply={turn.reply} onChip={send} onSent={(t) => add({ from: 'hira', text: t })} />}
                </div>
              </div>
            ))}
            {ask.isPending && <p className="text-sm text-muted">{assistant.name} is thinking…</p>}
          </div>
          <form onSubmit={onSubmit} className="flex gap-2 border-t border-ink/10 p-3">
            <label htmlFor={`${titleId}-input`} className="sr-only">
              Your question
            </label>
            <input
              ref={input}
              id={`${titleId}-input`}
              value={text}
              maxLength={500}
              autoComplete="off"
              onChange={(e) => setText(e.target.value)}
              placeholder="Type your question"
              className="min-h-11 flex-1 rounded-xl border border-ink/15 bg-white px-3 text-sm focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/30"
            />
            <button type="submit" aria-label="Send" disabled={!text.trim() || ask.isPending} className="flex h-11 w-11 items-center justify-center rounded-xl bg-primary text-white disabled:opacity-50">
              <Icon name="send" />
            </button>
          </form>
        </div>
      )}
    </>
  );
}
