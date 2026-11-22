import { formatDate } from '@/lib/format';
import type { OfferTerms } from '@/lib/types';

export function TermsList({ terms }: { terms: OfferTerms }) {
  const rows: [string, string][] = [
    ['Designation', terms.designation],
    ['Department', terms.department],
    ['Location', terms.location],
    ['Reporting manager', terms.reporting_manager_name],
    ['Joining date', formatDate(terms.joining_date)],
    ['Fixed pay (annual)', terms.display.fixed_pay],
    ['Variable pay (annual, target)', terms.display.variable_pay],
  ];
  if (terms.joining_bonus) rows.push(['Joining bonus (one time)', terms.display.joining_bonus]);
  rows.push(['Total annual compensation', terms.display.total]);
  return (
    <dl className="divide-y divide-ink/10">
      {rows.map(([label, value]) => (
        <div key={label} className="grid grid-cols-1 gap-1 py-2 sm:grid-cols-3">
          <dt className="text-sm text-muted">{label}</dt>
          <dd className="text-sm font-semibold text-ink sm:col-span-2">{value}</dd>
        </div>
      ))}
    </dl>
  );
}
