import { useState } from 'react';
import {
  DndContext,
  KeyboardSensor,
  PointerSensor,
  useDraggable,
  useDroppable,
  useSensor,
  useSensors,
  type DragEndEvent,
} from '@dnd-kit/core';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useParams } from 'react-router-dom';
import { ApplicationDrawer } from '@/components/ApplicationDrawer';
import { Dialog } from '@/components/Dialog';
import { CandidateName, FitBadge } from '@/components/fit';
import { Icon } from '@/components/Icon';
import { MoveTo, RejectDialog } from '@/components/pipeline';
import { errorText, STAGE_LABELS, useMoveMutation } from '@/lib/pipeline';
import { Button, ErrorNote, PageHeader, PageLoader } from '@/components/ui';
import { api } from '@/lib/api';
import { useDocumentTitle } from '@/lib/hooks';
import type { Board, BoardColumn, StaffApplication } from '@/lib/types';
import { JobViewTabs } from './JobApplicationsPage';

const BULK_COLUMNS = new Set(['applied', 'screening']);

function Card({
  app,
  canMove,
  selected,
  onSelect,
  onMove,
  onOpen,
  busy,
}: {
  app: StaffApplication;
  canMove: boolean;
  selected: boolean;
  onSelect: (checked: boolean) => void;
  onMove: (status: string) => void;
  onOpen: () => void;
  busy: boolean;
}) {
  const draggable = canMove && app.allowed_transitions.length > 0;
  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({
    id: app.id,
    data: { app },
    disabled: !draggable,
  });
  const who = app.blind || !app.candidate.full_name ? app.candidate.code : app.candidate.full_name;
  const style = transform ? { transform: `translate3d(${transform.x}px, ${transform.y}px, 0)` } : undefined;
  return (
    <li
      ref={setNodeRef}
      style={style}
      data-testid={`card-${app.id}`}
      className={`rounded-xl border border-white/70 bg-white p-3 shadow-glass ${isDragging ? 'z-10 opacity-80 shadow-lift' : ''}`}
    >
      <div className="flex items-start gap-2">
        {draggable && (
          <button
            type="button"
            className="-ml-1 flex h-9 w-7 shrink-0 cursor-grab items-center justify-center rounded text-muted hover:bg-ink/5 active:cursor-grabbing"
            aria-label={`Drag ${who}`}
            {...listeners}
            {...attributes}
          >
            <Icon name="grip" className="h-5 w-5" />
          </button>
        )}
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-semibold text-ink">
            <CandidateName app={app} />
          </p>
          <div className="mt-1 flex flex-wrap items-center gap-1.5">
            <FitBadge fit={app.fit} size="sm" />
          </div>
        </div>
        {canMove && BULK_COLUMNS.has(app.status) && (
          <input
            type="checkbox"
            className="mt-1 h-5 w-5 accent-primary"
            checked={selected}
            onChange={(e) => onSelect(e.target.checked)}
            aria-label={`Select ${who}`}
          />
        )}
      </div>
      <div className="mt-2 flex flex-col gap-1.5">
        {canMove && <MoveTo app={app} onMove={onMove} disabled={busy} />}
        <Button variant="ghost" className="min-h-9 justify-start px-2" onClick={onOpen}>
          Details and notes<span className="sr-only"> for {who}</span>
        </Button>
      </div>
    </li>
  );
}

function Column({ column, children }: { column: BoardColumn; children: React.ReactNode }) {
  const { setNodeRef, isOver } = useDroppable({ id: column.status, disabled: !column.drop_target });
  return (
    <section
      ref={setNodeRef}
      aria-labelledby={`col-${column.status}`}
      className={`flex w-72 shrink-0 flex-col rounded-xl2 border p-3 transition-colors sm:w-64 ${
        isOver ? 'border-primary bg-primary-soft/60' : 'border-white/60 bg-white/40'
      } ${column.drop_target ? '' : 'opacity-80'}`}
    >
      <h2 id={`col-${column.status}`} className="mb-1 flex items-center justify-between text-sm font-semibold text-ink">
        {column.label}
        <span className="rounded-full bg-ink/10 px-2 text-xs tabular-nums">{column.cards.length}</span>
      </h2>
      {column.note && <p className="mb-2 text-xs text-muted">{column.note}</p>}
      <ul className="flex min-h-16 flex-col gap-2" aria-label={`${column.label} candidates`}>
        {children}
      </ul>
    </section>
  );
}

export function PipelineBoardPage() {
  const { id = '' } = useParams();
  const client = useQueryClient();
  const board = useQuery({
    queryKey: ['board', id],
    queryFn: () => api<Board>(`/jobs/${id}/board`),
    refetchInterval: 20_000, // live updates arrive over the socket; this is the fallback
  });
  useDocumentTitle(board.data ? `Board · ${board.data.job.title}` : 'Pipeline board');
  const move = useMoveMutation(id);
  const [announcement, setAnnouncement] = useState('');
  const [rejecting, setRejecting] = useState<string[] | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [confirmBulk, setConfirmBulk] = useState(false);
  const [openId, setOpenId] = useState<string | null>(null);
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 6 } }), useSensor(KeyboardSensor));

  const bulk = useMutation({
    mutationFn: (body: { ids: string[]; status: string; reason?: string; note?: string }) =>
      api<{ moved: number }>(`/jobs/${id}/applications/bulk-status`, { method: 'POST', body }),
    onSuccess: (data, vars) => {
      setSelected(new Set());
      setConfirmBulk(false);
      setRejecting(null);
      setAnnouncement(`${data.moved} moved to ${STAGE_LABELS[vars.status]}.`);
      void client.invalidateQueries({ queryKey: ['board', id] });
      void client.invalidateQueries({ queryKey: ['job-applications', id] });
    },
  });

  const all = board.data?.columns.flatMap((c) => c.cards) ?? [];
  const byId = new Map(all.map((a) => [a.id, a]));
  const label = (app: StaffApplication) => (app.blind || !app.candidate.full_name ? app.candidate.code : app.candidate.full_name);

  const doMove = (app: StaffApplication, status: string) => {
    if (!app.allowed_transitions.includes(status)) {
      setAnnouncement(`${label(app)} cannot move from ${STAGE_LABELS[app.status]} to ${STAGE_LABELS[status] ?? status}.`);
      return;
    }
    if (status === 'rejected') {
      setRejecting([app.id]);
      return;
    }
    move.mutate({ id: app.id, status }, { onSuccess: () => setAnnouncement(`${label(app)} moved to ${STAGE_LABELS[status]}.`) });
  };

  const onDragEnd = (event: DragEndEvent) => {
    const app = byId.get(String(event.active.id));
    const target = event.over ? String(event.over.id) : null;
    if (!app || !target || target === app.status) return;
    doMove(app, target);
  };

  if (board.isPending) return <PageLoader />;
  if (board.isError || !board.data) return <ErrorNote>We could not load the board.</ErrorNote>;
  const data = board.data;
  const selectedIds = [...selected];
  const allScreening = selectedIds.every((sid) => byId.get(sid)?.allowed_transitions.includes('screening'));

  return (
    <>
      <PageHeader
        title={`Pipeline · ${data.job.title}`}
        intro={
          data.can_move
            ? 'Drag a card by its handle, or use “Move to” on any card. Moves are checked on the server and audited.'
            : 'You can read every card and add notes. Recruiters move candidates between stages.'
        }
      />
      <JobViewTabs jobId={id} current="board" />
      <p role="status" aria-live="polite" className="mb-2 min-h-6 text-sm font-medium text-ink-soft">
        {announcement}
      </p>
      {move.isError && <ErrorNote>{errorText(move.error)}</ErrorNote>}
      {bulk.isError && <ErrorNote>{errorText(bulk.error)}</ErrorNote>}
      {data.can_move && selectedIds.length > 0 && (
        <div
          className="glass sticky top-16 z-10 mb-3 flex flex-wrap items-center gap-2 rounded-xl2 p-3"
          role="region"
          aria-label="Bulk actions"
        >
          <span className="text-sm font-semibold text-ink">{selectedIds.length} selected</span>
          <Button disabled={!allScreening} onClick={() => setConfirmBulk(true)}>
            Move to Screening
          </Button>
          <Button variant="danger" onClick={() => setRejecting(selectedIds)}>
            Not selected…
          </Button>
          <Button variant="ghost" onClick={() => setSelected(new Set())}>
            Clear
          </Button>
        </div>
      )}
      <DndContext
        sensors={sensors}
        onDragEnd={onDragEnd}
        accessibility={{
          screenReaderInstructions: {
            draggable:
              'Press space to pick up the card, arrow keys to move it, space to drop, escape to cancel. You can also use the Move to menu on each card.',
          },
        }}
      >
        <div
          role="region"
          className="relative -mx-4 overflow-x-auto px-4 pb-4 sm:-mx-6 sm:px-6"
          tabIndex={0}
          aria-label="Pipeline columns, scroll sideways for more"
        >
          <div className="flex gap-3">
            {data.columns.map((column) => (
              <Column key={column.status} column={column}>
                {column.cards.map((app) => (
                  <Card
                    key={app.id}
                    app={app}
                    canMove={data.can_move}
                    busy={move.isPending}
                    selected={selected.has(app.id)}
                    onSelect={(checked) =>
                      setSelected((prev) => {
                        const next = new Set(prev);
                        if (checked) next.add(app.id);
                        else next.delete(app.id);
                        return next;
                      })
                    }
                    onMove={(status) => doMove(app, status)}
                    onOpen={() => setOpenId(app.id)}
                  />
                ))}
              </Column>
            ))}
          </div>
        </div>
      </DndContext>
      {confirmBulk && (
        <Dialog title={`Move ${selectedIds.length} candidates to Screening?`} onClose={() => setConfirmBulk(false)}>
          <div className="flex gap-2">
            <Button onClick={() => bulk.mutate({ ids: selectedIds, status: 'screening' })} disabled={bulk.isPending}>
              Yes, move them
            </Button>
            <Button variant="ghost" onClick={() => setConfirmBulk(false)}>
              Cancel
            </Button>
          </div>
        </Dialog>
      )}
      {rejecting && (
        <RejectDialog
          count={rejecting.length}
          reasons={data.rejection_reasons}
          busy={move.isPending || bulk.isPending}
          error={bulk.isError ? errorText(bulk.error) : undefined}
          onClose={() => setRejecting(null)}
          onConfirm={(reason, note) => {
            if (rejecting.length === 1) {
              const app = byId.get(rejecting[0]);
              move.mutate(
                { id: rejecting[0], status: 'rejected', reason, note },
                {
                  onSuccess: () => {
                    setRejecting(null);
                    if (app) setAnnouncement(`${label(app)} marked as not selected.`);
                  },
                },
              );
            } else {
              bulk.mutate({ ids: rejecting, status: 'rejected', reason, note });
            }
          }}
        />
      )}
      {openId && <ApplicationDrawer id={openId} jobId={id} onClose={() => setOpenId(null)} />}
    </>
  );
}
