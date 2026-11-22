import { StatusBadge } from './ui';

const BADGE: Record<string, string> = {
  draft: 'draft',
  pending_approval: 'screening',
  approved: 'applied',
  sent: 'interview',
  accepted: 'offer',
  declined: 'rejected',
  expired: 'closed',
  revoked: 'withdrawn',
  rejected: 'rejected',
};

export function OfferBadge({ offer }: { offer: { status: string; status_label: string; approval_step_label?: string } }) {
  const label =
    offer.status === 'pending_approval' && offer.approval_step_label ? `Waiting for ${offer.approval_step_label}` : offer.status_label;
  return <StatusBadge status={BADGE[offer.status] ?? 'draft'} label={label} />;
}
