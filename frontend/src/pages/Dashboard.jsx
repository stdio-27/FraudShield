import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Activity, ArrowRight, DollarSign, Gauge, RefreshCw, ShieldAlert } from "lucide-react";
import api from "../services/api";
import { usePolling } from "../hooks/usePolling";
import KpiCard from "../components/KpiCard";
import { RiskChart, ThroughputChart, VolumeChart } from "../components/charts";
import { RiskScore } from "../components/AlertParts";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/Card";
import { EmptyState, ErrorBanner } from "../components/ui/Feedback";
import { Skeleton } from "../components/ui/Skeleton";
import { Tabs } from "../components/ui/Tabs";
import { Table, TBody, TD, TH, THead, TR } from "../components/ui/Table";
import { chronological, windowDelta } from "../lib/metrics";
import {
  formatBucketLabel,
  formatClock,
  formatCurrency,
  formatCurrencyCompact,
  formatInt,
  formatPercent,
  formatScore,
  formatTimeAgo,
  shortId,
} from "../lib/format";

const WINDOWS = [
  { value: 30, label: "30m" },
  { value: 60, label: "1h" },
  { value: 120, label: "2h" },
  { value: 360, label: "6h" },
  { value: 1440, label: "24h" },
];
const windowLabel = (m) => (m >= 60 ? `last ${m / 60} h` : `last ${m} min`);

const get = (url, params) => api.get(url, { params }).then((r) => r.data);

export default function Dashboard() {
  const [windowMinutes, setWindowMinutes] = useState(120);
  const [showAllBuckets, setShowAllBuckets] = useState(false);

  // One poller per resource (same 30 s cadence as before) so each card loads and fails independently.
  const summary = usePolling(() => get("/analytics/summary"));
  const series = usePolling(() => get("/analytics/time-series", { window_minutes: windowMinutes }), {
    deps: [windowMinutes],
  });
  const backlog = usePolling(() => get("/analytics/alert-telemetry").then((d) => d.telemetry || []));
  const latest = usePolling(() => get("/alerts", { status: "open", limit: 6 }));

  const resources = [summary, series, backlog, latest];
  const refreshing = resources.some((r) => r.refreshing);
  const lastUpdated = resources.map((r) => r.lastUpdated).filter(Boolean).sort((a, b) => b - a)[0] || null;
  const refreshAll = () => resources.forEach((r) => r.refresh());

  const buckets = series.data?.buckets;
  const label = windowLabel(windowMinutes);

  // Trend chips: recent half of the window vs the half before it, from real bucket data.
  const deltas = useMemo(
    () => ({
      tx: windowDelta(buckets, "tx_count", windowMinutes),
      volume: windowDelta(buckets, "total_volume", windowMinutes),
      flagged: windowDelta(buckets, "flagged_count", windowMinutes),
      score: windowDelta(buckets, "avg_fraud_score", windowMinutes, { weightKey: "tx_count" }),
    }),
    [buckets, windowMinutes],
  );
  const deltaLabel = `vs previous ${windowMinutes / 2} min`;

  const s = summary.data;
  const summaryLoading = summary.loading && !s;
  const avgTicket = s && s.total_transactions ? s.total_volume / s.total_transactions : null;

  const rows = useMemo(() => chronological(buckets).reverse(), [buckets]);
  const visibleRows = showAllBuckets ? rows : rows.slice(0, 10);

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-xl font-semibold tracking-tight">Overview</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Fraud monitoring across all scored transactions.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Tabs aria-label="Time window" items={WINDOWS} value={windowMinutes} onChange={setWindowMinutes} />
          <Button variant="outline" size="sm" onClick={refreshAll} disabled={refreshing}>
            <RefreshCw className={`h-3.5 w-3.5 ${refreshing ? "animate-spin" : ""}`} />
            Refresh
          </Button>
          <span className="num hidden text-xs text-muted-foreground sm:inline" title="Auto-refreshes every 30 seconds">
            {lastUpdated ? `Updated ${formatClock(lastUpdated)}` : "Loading…"}
          </span>
        </div>
      </div>

      {/* One banner for any failing resource; whatever loaded before stays on screen. */}
      <ErrorBanner
        error={resources.find((r) => r.error)?.error}
        stale={resources.some((r) => r.data)}
        onRetry={refreshAll}
      />

      {/* KPI strip */}
      <section aria-label="Key metrics" className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <KpiCard
          title="Transactions scored"
          icon={Activity}
          loading={summaryLoading}
          value={formatInt(s?.total_transactions)}
          caption={avgTicket != null ? `Average ticket ${formatCurrency(avgTicket)}` : "All time"}
          delta={deltas.tx}
          deltaLabel={deltaLabel}
          deltaFormat={formatInt}
        />
        <KpiCard
          title="Total volume"
          icon={DollarSign}
          loading={summaryLoading}
          value={formatCurrencyCompact(s?.total_volume)}
          caption={s ? `${formatCurrency(s.total_volume)} exact` : "All time"}
          delta={deltas.volume}
          deltaLabel={deltaLabel}
          deltaFormat={formatCurrencyCompact}
        />
        <KpiCard
          title="Flagged transactions"
          icon={ShieldAlert}
          loading={summaryLoading}
          value={formatInt(s?.flagged_count)}
          caption={s ? `${formatPercent(s.fraud_rate_pct, 2)} of all transactions flagged` : "All time"}
          delta={deltas.flagged}
          deltaLabel={deltaLabel}
          goodDirection="down"
          deltaFormat={formatInt}
        />
        <KpiCard
          title="Average risk score"
          icon={Gauge}
          loading={summaryLoading}
          value={formatScore(s?.avg_fraud_score, 4)}
          caption={s ? `Peak score ${formatScore(s.max_fraud_score, 4)}` : "All time"}
          delta={deltas.score}
          deltaLabel={deltaLabel}
          goodDirection="down"
          deltaFormat={(v) => formatScore(v, 4)}
        />
      </section>

      {/* Charts + backlog */}
      <section className="grid gap-4 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <ThroughputChart buckets={buckets} loading={series.loading} windowLabel={label} />
        </div>
        <BacklogCard backlog={backlog} />
      </section>

      <section className="grid gap-4 lg:grid-cols-2">
        <RiskChart buckets={buckets} loading={series.loading} windowLabel={label} />
        <VolumeChart buckets={buckets} loading={series.loading} windowLabel={label} />
      </section>

      {/* Tables */}
      <section className="grid gap-4 xl:grid-cols-5">
        <Card className="xl:col-span-2">
          <CardHeader>
            <div>
              <CardTitle>Latest open alerts</CardTitle>
              <CardDescription>Newest alerts awaiting review</CardDescription>
            </div>
            <Link
              to="/alerts"
              className="inline-flex items-center gap-1 text-xs font-medium text-muted-foreground hover:text-foreground"
            >
              View queue <ArrowRight className="h-3 w-3" />
            </Link>
          </CardHeader>
          <LatestAlerts latest={latest} />
        </Card>

        <Card className="xl:col-span-3">
          <CardHeader>
            <div>
              <CardTitle>Activity by 5-minute bucket</CardTitle>
              <CardDescription>
                {label} · {formatInt(rows.length)} buckets with activity
              </CardDescription>
            </div>
            {rows.length > 10 && (
              <Button variant="ghost" size="sm" onClick={() => setShowAllBuckets((v) => !v)}>
                {showAllBuckets ? "Show fewer" : `Show all ${rows.length}`}
              </Button>
            )}
          </CardHeader>
          <BucketTable rows={visibleRows} loading={series.loading} windowMinutes={windowMinutes} />
        </Card>
      </section>
    </div>
  );
}

function BacklogCard({ backlog }) {
  const items = backlog.data || [];
  const byStatus = (status) => items.find((t) => t.status === status);
  const open = byStatus("open");
  const investigating = byStatus("investigating");
  const total = (open?.alert_count || 0) + (investigating?.alert_count || 0);

  return (
    <Card>
      <CardHeader>
        <div>
          <CardTitle>Alert backlog</CardTitle>
          <CardDescription>Alerts that still need an analyst</CardDescription>
        </div>
        <Link
          to="/alerts"
          className="inline-flex items-center gap-1 text-xs font-medium text-muted-foreground hover:text-foreground"
        >
          Open queue <ArrowRight className="h-3 w-3" />
        </Link>
      </CardHeader>
      <CardContent>
        {backlog.loading && !backlog.data ? (
          <div className="space-y-4">
            <Skeleton className="h-9 w-24" />
            <Skeleton className="h-14 w-full" />
            <Skeleton className="h-14 w-full" />
          </div>
        ) : (
          <>
            <p className="num text-3xl font-semibold tracking-tight">{formatInt(total)}</p>
            <p className="mt-1 text-xs text-muted-foreground">open or under investigation</p>

            <div className="mt-5 space-y-4">
              {[
                { key: "open", label: "Open", row: open, bar: "bg-risk-high" },
                { key: "investigating", label: "Investigating", row: investigating, bar: "bg-risk-medium" },
              ].map(({ key, label, row, bar }) => (
                <div key={key}>
                  <div className="flex items-baseline justify-between text-xs">
                    <span className="font-medium">{label}</span>
                    <span className="num">{formatInt(row?.alert_count || 0)}</span>
                  </div>
                  <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-muted" aria-hidden="true">
                    <div className={`h-full rounded-full ${bar}`} style={{ width: total ? `${((row?.alert_count || 0) / total) * 100}%` : 0 }} />
                  </div>
                  <p className="mt-1.5 text-2xs text-muted-foreground">
                    Average severity <span className="num text-foreground">{row ? formatScore(row.avg_severity, 3) : "—"}</span>
                  </p>
                </div>
              ))}
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}

function LatestAlerts({ latest }) {
  const items = latest.data?.items || [];

  if (latest.loading && !latest.data) {
    return (
      <div className="space-y-3 p-4">
        {Array.from({ length: 5 }).map((_, i) => (
          <Skeleton key={i} className="h-9 w-full" />
        ))}
      </div>
    );
  }
  if (latest.error && !latest.data) {
    return (
      <div className="p-4">
        <ErrorBanner error={latest.error} onRetry={latest.refresh} />
      </div>
    );
  }
  if (!items.length) {
    return <EmptyState icon={ShieldAlert} title="No open alerts" description="Flagged transactions will appear here." />;
  }

  return (
    <Table>
      <THead>
        <TR>
          <TH>Score</TH>
          <TH>Reference</TH>
          <TH className="text-right">Amount</TH>
          <TH className="text-right">Detected</TH>
        </TR>
      </THead>
      <TBody>
        {items.map((a) => (
          <TR key={a.alert_id} className="hover:bg-muted/30">
            <TD>
              <RiskScore score={a.fraud_score} showLabel={false} />
            </TD>
            <TD className="num text-xs" title={a.tx_id}>
              {a.external_id || shortId(a.tx_id)}
            </TD>
            <TD className="num text-right text-xs">{formatCurrency(a.amount)}</TD>
            <TD className="whitespace-nowrap text-right text-xs text-muted-foreground">{formatTimeAgo(a.created_at)}</TD>
          </TR>
        ))}
      </TBody>
    </Table>
  );
}

function BucketTable({ rows, loading, windowMinutes }) {
  if (loading) {
    return (
      <div className="space-y-3 p-4">
        {Array.from({ length: 6 }).map((_, i) => (
          <Skeleton key={i} className="h-7 w-full" />
        ))}
      </div>
    );
  }
  if (!rows.length) {
    return <EmptyState icon={Activity} title="No activity in this window" description="Try a longer time window." />;
  }
  const withDate = windowMinutes > 360;
  return (
    <Table>
      <THead>
        <TR>
          <TH>Bucket start</TH>
          <TH className="text-right">Transactions</TH>
          <TH className="text-right">Volume</TH>
          <TH className="text-right">Avg score</TH>
          <TH className="text-right">Flagged</TH>
          <TH className="text-right">Flag rate</TH>
        </TR>
      </THead>
      <TBody>
        {rows.map((b) => {
          const rate = b.tx_count ? (b.flagged_count / b.tx_count) * 100 : 0;
          return (
            <TR key={b.bucket} className="hover:bg-muted/30">
              <TD className="num text-xs">{formatBucketLabel(b.bucket, withDate)}</TD>
              <TD className="num text-right text-xs">{formatInt(b.tx_count)}</TD>
              <TD className="num text-right text-xs">{formatCurrency(b.total_volume)}</TD>
              <TD className="num text-right text-xs">{formatScore(b.avg_fraud_score, 4)}</TD>
              <TD className="text-right">
                {b.flagged_count > 0 ? (
                  <Badge tone="high" className="num">
                    {formatInt(b.flagged_count)}
                  </Badge>
                ) : (
                  <span className="num text-xs text-muted-foreground">0</span>
                )}
              </TD>
              <TD className="num text-right text-xs text-muted-foreground">{formatPercent(rate, 1)}</TD>
            </TR>
          );
        })}
      </TBody>
    </Table>
  );
}
