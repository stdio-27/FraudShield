import { ArrowDownRight, ArrowUpRight, Minus } from 'lucide-react';
import { Card } from './ui/Card';
import { Skeleton } from './ui/Skeleton';
import { cn } from '../lib/utils';

/**
 * Change chip computed from real data (see lib/metrics.windowDelta).
 * `goodDirection` decides the colour: more flagged transactions is bad, more
 * throughput is just information.
 */
function DeltaChip({ delta, goodDirection = 'neutral', format }) {
  if (!delta) {
    return <span className="text-2xs text-muted-foreground">No recent activity</span>;
  }
  if (delta.pct == null) {
    return <span className="text-2xs text-muted-foreground">No prior period</span>;
  }

  const rounded = Math.round(delta.pct * 10) / 10;
  const dir = rounded > 0 ? 'up' : rounded < 0 ? 'down' : 'flat';
  const Icon = dir === 'up' ? ArrowUpRight : dir === 'down' ? ArrowDownRight : Minus;

  let tone = 'text-muted-foreground';
  if (dir !== 'flat' && goodDirection !== 'neutral') {
    tone = dir === goodDirection ? 'text-risk-low' : 'text-risk-high';
  }

  const fmt = format || ((v) => v);
  return (
    <span
      className={cn('inline-flex items-center gap-0.5 text-xs font-medium', tone)}
      title={`Last ${delta.spanMinutes} min: ${fmt(delta.current)} · previous ${delta.spanMinutes} min: ${fmt(delta.previous)}`}
    >
      <Icon className="h-3.5 w-3.5" aria-hidden="true" />
      <span className="num">{Math.abs(rounded).toFixed(1)}%</span>
    </span>
  );
}

export default function KpiCard({
  title,
  icon: Icon,
  value,
  caption,
  delta,
  deltaLabel,
  goodDirection,
  deltaFormat,
  loading,
}) {
  return (
    <Card className="p-4">
      <div className="flex items-center justify-between">
        <p className="text-xs font-medium text-muted-foreground">{title}</p>
        {Icon && <Icon className="h-4 w-4 text-muted-foreground" aria-hidden="true" />}
      </div>

      {loading ? (
        <div className="mt-3 space-y-2">
          <Skeleton className="h-7 w-28" />
          <Skeleton className="h-3.5 w-40" />
        </div>
      ) : (
        <>
          <p className="num mt-2 text-2xl font-semibold tracking-tight">{value}</p>
          <div className="mt-1.5 flex items-center justify-between gap-2">
            <p className="truncate text-xs text-muted-foreground">{caption}</p>
          </div>
          {deltaLabel !== undefined && (
            <div className="mt-3 flex items-center gap-2 border-t pt-2.5">
              <DeltaChip delta={delta} goodDirection={goodDirection} format={deltaFormat} />
              {delta && delta.pct != null && (
                <span className="text-2xs text-muted-foreground">{deltaLabel}</span>
              )}
            </div>
          )}
        </>
      )}
    </Card>
  );
}
