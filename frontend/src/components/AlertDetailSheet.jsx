import { useState } from 'react';
import { Check, Clipboard, Loader2 } from 'lucide-react';
import { Sheet } from './ui/Sheet';
import { Button } from './ui/Button';
import { Badge } from './ui/Badge';
import { ErrorBanner } from './ui/Feedback';
import { CopyId, RiskScore, StatusBadge } from './AlertParts';
import ShapBreakdown from './ShapBreakdown';
import { cn } from '../lib/utils';
import { STATUS_META, STATUS_ORDER, severityOf } from '../lib/risk';
import { formatCurrency, formatDateTime, formatScore, formatTimeAgo } from '../lib/format';

function Fact({ label, children, title }) {
  return (
    <div className="min-w-0 px-4 py-3" title={title}>
      <dt className="text-2xs uppercase tracking-wider text-muted-foreground">{label}</dt>
      <dd className="mt-1 truncate text-sm">{children}</dd>
    </div>
  );
}

function Section({ title, description, children }) {
  return (
    <section className="border-t px-5 py-5">
      <h3 className="text-sm font-medium">{title}</h3>
      {description && <p className="mt-1 text-xs text-muted-foreground">{description}</p>}
      <div className="mt-4">{children}</div>
    </section>
  );
}

export default function AlertDetailSheet({ alert, onClose, onStatusChange, canModify, updating, error }) {
  const [copied, setCopied] = useState(false);

  if (!alert) return <Sheet open={false} onClose={onClose} />;

  const sev = severityOf(alert.fraud_score);

  const copyJson = async () => {
    try {
      await navigator.clipboard.writeText(JSON.stringify(alert, null, 2));
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* clipboard unavailable */
    }
  };

  return (
    <Sheet
      open
      onClose={onClose}
      title={alert.external_id ? `Alert · ${alert.external_id}` : `Alert · ${alert.alert_id.slice(0, 8)}`}
      description={`Detected ${formatTimeAgo(alert.created_at)}`}
    >
      {/* Headline */}
      <div className="flex flex-wrap items-center justify-between gap-3 px-5 py-5">
        <div>
          <p className="text-2xs uppercase tracking-wider text-muted-foreground">Fraud score</p>
          <p className="num mt-1 text-3xl font-semibold tracking-tight">{formatScore(alert.fraud_score, 4)}</p>
        </div>
        <div className="flex flex-col items-end gap-2">
          <div className="flex items-center gap-2">
            <Badge tone={sev.tone}>{sev.label} severity</Badge>
            <StatusBadge status={alert.status} />
          </div>
          <RiskScore score={alert.fraud_score} showLabel={false} />
        </div>
      </div>

      {/* Facts */}
      <dl className="grid grid-cols-2 divide-x divide-y border-t [&>*:nth-child(odd)]:border-l-0">
        <Fact label="Amount">
          <span className="num font-medium">{formatCurrency(alert.amount)}</span>
        </Fact>
        <Fact label="Transaction time" title={alert.transaction_time || ''}>
          <span className="num">{formatDateTime(alert.transaction_time)}</span>
        </Fact>
        <Fact label="Reference" title={alert.external_id || ''}>
          <span className="num">{alert.external_id || '—'}</span>
        </Fact>
        <Fact label="Detected" title={alert.created_at || ''}>
          <span className="num">{formatDateTime(alert.created_at)}</span>
        </Fact>
        <Fact label="Transaction ID">
          <CopyId value={alert.tx_id} display={alert.tx_id.slice(0, 13) + '…'} className="text-xs" />
        </Fact>
        <Fact label="Alert ID">
          <CopyId value={alert.alert_id} display={alert.alert_id.slice(0, 13) + '…'} className="text-xs" />
        </Fact>
      </dl>

      {/* Triage */}
      <Section
        title="Triage"
        description={canModify ? 'Change the review status. This is saved immediately and recorded in the API log.' : 'Your role is read-only, so the status cannot be changed.'}
      >
        <ErrorBanner error={error} className="mb-3" />
        <div className="grid grid-cols-2 gap-2">
          {STATUS_ORDER.map((status) => {
            const active = alert.status === status;
            return (
              <button
                key={status}
                type="button"
                disabled={!canModify || updating || active}
                onClick={() => onStatusChange(alert, status)}
                aria-pressed={active}
                className={cn(
                  'flex h-9 items-center justify-center gap-2 rounded-md border px-3 text-xs font-medium transition-colors',
                  active ? 'border-ring bg-accent text-foreground' : 'text-muted-foreground hover:bg-accent hover:text-foreground',
                  'disabled:cursor-not-allowed',
                  !active && 'disabled:opacity-50',
                )}
              >
                {active && updating ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : active ? <Check className="h-3.5 w-3.5" /> : null}
                {STATUS_META[status].label}
              </button>
            );
          })}
        </div>
      </Section>

      {/* Explainability */}
      <Section
        title="Model explanation"
        description="Why the XGBoost model scored this transaction as high risk (TreeSHAP)."
      >
        <ShapBreakdown reasons={alert.shap_reasons} />
      </Section>

      <div className="border-t px-5 py-4">
        <Button variant="outline" size="sm" onClick={copyJson}>
          {copied ? <Check className="h-3.5 w-3.5" /> : <Clipboard className="h-3.5 w-3.5" />}
          {copied ? 'Copied' : 'Copy alert as JSON'}
        </Button>
      </div>
    </Sheet>
  );
}
