import { Check, Copy } from 'lucide-react';
import { useState } from 'react';
import { Badge } from './ui/Badge';
import { cn } from '../lib/utils';
import { formatScore } from '../lib/format';
import { STATUS_META, severityOf } from '../lib/risk';

const BAR_TONE = { high: 'bg-risk-high', medium: 'bg-risk-medium', low: 'bg-risk-low' };

/** Fraud score as a number plus a thin severity bar; the bar is the only coloured part. */
export function RiskScore({ score, showLabel = true, className }) {
  if (score == null) return <span className="text-muted-foreground">—</span>;
  const sev = severityOf(score);
  return (
    <div className={cn('flex items-center gap-2.5', className)}>
      <div className="h-1.5 w-14 shrink-0 overflow-hidden rounded-full bg-muted" aria-hidden="true">
        <div className={cn('h-full rounded-full', BAR_TONE[sev.tone])} style={{ width: `${Math.min(score, 1) * 100}%` }} />
      </div>
      <span className="num text-xs font-medium">{formatScore(score, 3)}</span>
      {showLabel && <span className="hidden text-2xs text-muted-foreground xl:inline">{sev.label}</span>}
    </div>
  );
}

export function StatusBadge({ status }) {
  const meta = STATUS_META[status] || { label: status, tone: 'outline' };
  return (
    <Badge tone={meta.tone} dot>
      {meta.label}
    </Badge>
  );
}

/** Monospace identifier with a copy-to-clipboard button. */
export function CopyId({ value, display, className }) {
  const [copied, setCopied] = useState(false);
  const copy = async (e) => {
    e.stopPropagation();
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      setTimeout(() => setCopied(false), 1200);
    } catch {
      /* clipboard unavailable (insecure context); ignore */
    }
  };
  return (
    <span className={cn('inline-flex items-center gap-1.5', className)}>
      <span className="num" title={value}>
        {display ?? value}
      </span>
      <button
        type="button"
        onClick={copy}
        aria-label={copied ? 'Copied' : 'Copy to clipboard'}
        className="rounded p-0.5 text-muted-foreground transition-colors hover:text-foreground"
      >
        {copied ? <Check className="h-3 w-3" /> : <Copy className="h-3 w-3" />}
      </button>
    </span>
  );
}
