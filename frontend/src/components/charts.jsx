import {
  Area,
  AreaChart,
  Bar,
  CartesianGrid,
  ComposedChart,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './ui/Card';
import { Skeleton } from './ui/Skeleton';
import { EmptyState } from './ui/Feedback';
import { Activity } from 'lucide-react';
import { chronological } from '../lib/metrics';
import { HIGH_CONFIDENCE_THRESHOLD } from '../lib/risk';
import {
  formatBucketLabel,
  formatCompact,
  formatCurrency,
  formatCurrencyCompact,
  formatDateTime,
  formatInt,
  formatScore,
} from '../lib/format';

// SVG attributes cannot rely on Tailwind classes, so the (muted) palette lives here.
const COLORS = {
  grid: '#27272a',
  axis: '#71717a',
  bar: '#3f3f46',
  line: '#e4e4e7',
  flagged: '#ef4444',
  volume: '#a1a1aa',
  threshold: '#f59e0b',
};

const axisProps = {
  tick: { fill: COLORS.axis, fontSize: 11 },
  axisLine: false,
  tickLine: false,
};

function prepare(buckets) {
  const rows = chronological(buckets);
  const spansDays =
    rows.length > 1 && new Date(rows[0].bucket).toDateString() !== new Date(rows[rows.length - 1].bucket).toDateString();
  return rows.map((b) => ({
    ...b,
    label: formatBucketLabel(b.bucket, spansDays),
    full: formatDateTime(b.bucket),
  }));
}

function ChartTooltip({ active, payload, label, rows }) {
  if (!active || !payload?.length) return null;
  const full = payload[0]?.payload?.full || label;
  return (
    <div className="rounded-md border bg-popover px-3 py-2 text-xs shadow-lg">
      <p className="num mb-1.5 text-muted-foreground">{full}</p>
      <ul className="space-y-1">
        {rows.map(({ key, name, color, format }) => {
          const entry = payload.find((p) => p.dataKey === key);
          if (!entry) return null;
          return (
            <li key={key} className="flex items-center justify-between gap-6">
              <span className="flex items-center gap-2 text-muted-foreground">
                <span className="h-2 w-2 rounded-sm" style={{ background: color }} aria-hidden="true" />
                {name}
              </span>
              <span className="num font-medium">{format(entry.value)}</span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

function Legend({ items }) {
  return (
    <ul className="flex flex-wrap items-center gap-4 text-xs text-muted-foreground">
      {items.map((i) => (
        <li key={i.name} className="flex items-center gap-1.5">
          <span className="h-2 w-2 rounded-sm" style={{ background: i.color }} aria-hidden="true" />
          {i.name}
        </li>
      ))}
    </ul>
  );
}

export function ChartCard({ title, description, legend, loading, empty, children, className }) {
  return (
    <Card className={className}>
      <CardHeader>
        <div>
          <CardTitle>{title}</CardTitle>
          {description && <CardDescription>{description}</CardDescription>}
        </div>
        {legend && <Legend items={legend} />}
      </CardHeader>
      <CardContent className="pt-4">
        {loading ? (
          <Skeleton className="h-60 w-full" />
        ) : empty ? (
          <EmptyState
            icon={Activity}
            title="No transactions in this window"
            description="Try a longer time window, or score some transactions."
            className="h-60 py-0"
          />
        ) : (
          <div className="h-60">{children}</div>
        )}
      </CardContent>
    </Card>
  );
}

const commonChart = { margin: { top: 4, right: 4, bottom: 0, left: -12 } };

export function ThroughputChart({ buckets, loading, windowLabel }) {
  const data = prepare(buckets);
  const legend = [
    { name: 'Transactions', color: COLORS.bar },
    { name: 'Flagged', color: COLORS.flagged },
  ];
  return (
    <ChartCard
      title="Transaction throughput"
      description={`Scored transactions and flagged count per 5-minute bucket · ${windowLabel}`}
      legend={legend}
      loading={loading}
      empty={!data.length}
    >
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={data} {...commonChart}>
          <CartesianGrid vertical={false} stroke={COLORS.grid} />
          <XAxis dataKey="label" {...axisProps} minTickGap={32} />
          <YAxis yAxisId="left" {...axisProps} tickFormatter={formatCompact} allowDecimals={false} />
          <YAxis yAxisId="right" orientation="right" {...axisProps} allowDecimals={false} width={32} />
          <Tooltip
            cursor={{ fill: '#ffffff08' }}
            content={
              <ChartTooltip
                rows={[
                  { key: 'tx_count', name: 'Transactions', color: COLORS.bar, format: formatInt },
                  { key: 'flagged_count', name: 'Flagged', color: COLORS.flagged, format: formatInt },
                ]}
              />
            }
          />
          <Bar yAxisId="left" dataKey="tx_count" fill={COLORS.bar} radius={[2, 2, 0, 0]} maxBarSize={18} />
          <Line
            yAxisId="right"
            dataKey="flagged_count"
            type="monotone"
            stroke={COLORS.flagged}
            strokeWidth={1.75}
            dot={false}
            activeDot={{ r: 3 }}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}

export function RiskChart({ buckets, loading, windowLabel }) {
  const data = prepare(buckets);
  return (
    <ChartCard
      title="Average risk score"
      description={`Mean model score per bucket · ${windowLabel}`}
      legend={[
        { name: 'Avg score', color: COLORS.line },
        { name: `High-confidence ≥ ${HIGH_CONFIDENCE_THRESHOLD}`, color: COLORS.threshold },
      ]}
      loading={loading}
      empty={!data.length}
    >
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} {...commonChart}>
          <CartesianGrid vertical={false} stroke={COLORS.grid} />
          <XAxis dataKey="label" {...axisProps} minTickGap={32} />
          <YAxis {...axisProps} domain={[0, 1]} ticks={[0, 0.25, 0.5, 0.75, 1]} tickFormatter={(v) => v.toFixed(2)} />
          <Tooltip
            content={
              <ChartTooltip rows={[{ key: 'avg_fraud_score', name: 'Avg score', color: COLORS.line, format: (v) => formatScore(v, 4) }]} />
            }
          />
          <ReferenceLine y={HIGH_CONFIDENCE_THRESHOLD} stroke={COLORS.threshold} strokeDasharray="4 4" strokeOpacity={0.7} />
          <Line dataKey="avg_fraud_score" type="monotone" stroke={COLORS.line} strokeWidth={1.75} dot={false} activeDot={{ r: 3 }} />
        </LineChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}

export function VolumeChart({ buckets, loading, windowLabel }) {
  const data = prepare(buckets);
  return (
    <ChartCard
      title="Transaction volume"
      description={`Total amount scored per bucket · ${windowLabel}`}
      loading={loading}
      empty={!data.length}
    >
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} {...commonChart}>
          <CartesianGrid vertical={false} stroke={COLORS.grid} />
          <XAxis dataKey="label" {...axisProps} minTickGap={32} />
          <YAxis {...axisProps} tickFormatter={formatCurrencyCompact} width={56} />
          <Tooltip
            content={
              <ChartTooltip rows={[{ key: 'total_volume', name: 'Volume', color: COLORS.volume, format: formatCurrency }]} />
            }
          />
          <Area
            dataKey="total_volume"
            type="monotone"
            stroke={COLORS.volume}
            strokeWidth={1.75}
            fill={COLORS.volume}
            fillOpacity={0.1}
            dot={false}
            activeDot={{ r: 3 }}
          />
        </AreaChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}
