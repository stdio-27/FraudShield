import { useCallback, useEffect, useMemo, useState } from 'react';
import { ArrowDown, ArrowUp, ChevronLeft, ChevronRight, RefreshCw, Search, ShieldAlert } from 'lucide-react';
import api, { getErrorMessage } from '../services/api';
import { usePolling } from '../hooks/usePolling';
import { useAuth } from '../context/AuthContext';
import AlertDetailSheet from '../components/AlertDetailSheet';
import { RiskScore } from '../components/AlertParts';
import { Button } from '../components/ui/Button';
import { Card } from '../components/ui/Card';
import { EmptyState, ErrorBanner } from '../components/ui/Feedback';
import { Select } from '../components/ui/Select';
import { Skeleton } from '../components/ui/Skeleton';
import { SortHeader, Table, TBody, TD, TH, THead, TR } from '../components/ui/Table';
import { Tabs } from '../components/ui/Tabs';
import { cn } from '../lib/utils';
import { STATUS_META, STATUS_ORDER } from '../lib/risk';
import { formatClock, formatCurrency, formatDateTime, formatInt, formatTimeAgo, shortId } from '../lib/format';

const FILTERS = {
  active: { label: 'Active', status: 'open,investigating' },
  open: { label: 'Open', status: 'open' },
  investigating: { label: 'Investigating', status: 'investigating' },
  resolved: { label: 'Resolved', status: 'confirmed_fraud,false_positive' },
  all: { label: 'All', status: undefined },
};
const PAGE_SIZES = [25, 50, 100];

// Comparators for client-side sorting of the loaded page. Nulls always sort last.
const SORTERS = {
  score: (a) => a.fraud_score,
  ref: (a) => (a.external_id || a.tx_id || '').toLowerCase(),
  amount: (a) => a.amount,
  tx_time: (a) => (a.transaction_time ? new Date(a.transaction_time).getTime() : null),
  created_at: (a) => (a.created_at ? new Date(a.created_at).getTime() : null),
  status: (a) => STATUS_ORDER.indexOf(a.status),
};

function sortAlerts(items, { key, dir }) {
  const get = SORTERS[key];
  const factor = dir === 'asc' ? 1 : -1;
  return [...items].sort((a, b) => {
    const va = get(a);
    const vb = get(b);
    if (va == null && vb == null) return 0;
    if (va == null) return 1;
    if (vb == null) return -1;
    if (va < vb) return -1 * factor;
    if (va > vb) return 1 * factor;
    return 0;
  });
}

const get = (url, params) => api.get(url, { params }).then((r) => r.data);

export default function AlertsTable() {
  const { canModify } = useAuth();

  const [filter, setFilter] = useState('active');
  const [pageSize, setPageSize] = useState(25);
  const [page, setPage] = useState(0);
  const [sort, setSort] = useState({ key: 'created_at', dir: 'desc' });
  const [query, setQuery] = useState('');

  const [selected, setSelected] = useState(null);
  const [updatingId, setUpdatingId] = useState(null);
  const [actionError, setActionError] = useState(null);

  const alerts = usePolling(
    () => get('/alerts', { status: FILTERS[filter].status, limit: pageSize, offset: page * pageSize }),
    { deps: [filter, pageSize, page] },
  );
  const telemetry = usePolling(() => get('/analytics/alert-telemetry').then((d) => d.telemetry || []));

  const items = alerts.data?.items;
  const total = alerts.data?.total ?? 0;
  const lastPage = Math.max(0, Math.ceil(total / pageSize) - 1);

  // Keep the open drawer in sync with refreshed data.
  useEffect(() => {
    if (!selected || !items) return;
    const fresh = items.find((a) => a.alert_id === selected.alert_id);
    if (fresh && fresh !== selected) setSelected(fresh);
  }, [items, selected]);

  // If rows disappear (e.g. resolved elsewhere) and the page no longer exists, step back.
  useEffect(() => {
    if (alerts.data && page > lastPage) setPage(lastPage);
  }, [alerts.data, page, lastPage]);

  const changeFilter = (value) => {
    setFilter(value);
    setPage(0);
  };

  const toggleSort = (key) =>
    setSort((s) => (s.key === key ? { key, dir: s.dir === 'asc' ? 'desc' : 'asc' } : { key, dir: key === 'ref' || key === 'status' ? 'asc' : 'desc' }));

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase();
    const filtered = !items
      ? []
      : q
        ? items.filter((a) =>
            [a.external_id, a.tx_id, a.alert_id, a.status, a.amount != null ? String(a.amount) : '']
              .filter(Boolean)
              .some((v) => String(v).toLowerCase().includes(q)),
          )
        : items;
    return sortAlerts(filtered, sort);
  }, [items, query, sort]);

  const changeStatus = useCallback(
    async (alert, status) => {
      if (alert.status === status) return;
      setUpdatingId(alert.alert_id);
      setActionError(null);
      try {
        const { data } = await api.patch(`/alerts/${alert.alert_id}`, { status });
        setSelected((cur) => (cur && cur.alert_id === data.alert_id ? data : cur));
        await Promise.all([alerts.refresh(), telemetry.refresh()]);
      } catch (err) {
        setActionError(err);
      } finally {
        setUpdatingId(null);
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [alerts.refresh, telemetry.refresh],
  );

  const closeSheet = useCallback(() => {
    setSelected(null);
    setActionError(null);
  }, []);

  const counts = useMemo(() => {
    const byStatus = (s) => telemetry.data?.find((t) => t.status === s)?.alert_count;
    const open = byStatus('open') ?? 0;
    const investigating = byStatus('investigating') ?? 0;
    return telemetry.data ? { active: open + investigating, open, investigating } : {};
  }, [telemetry.data]);

  const tabItems = Object.entries(FILTERS).map(([value, f]) => ({ value, label: f.label, count: counts[value] }));
  const from = total ? page * pageSize + 1 : 0;
  const to = Math.min(total, (page + 1) * pageSize);
  const refreshing = alerts.refreshing || telemetry.refreshing;

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-xl font-semibold tracking-tight">Alerts queue</h2>
          <p className="mt-1 text-sm text-muted-foreground">Flagged transactions awaiting analyst review.</p>
        </div>
        <div className="flex items-center gap-2">
          <span className="num hidden text-xs text-muted-foreground sm:inline" title="Auto-refreshes every 30 seconds">
            {alerts.lastUpdated ? `Updated ${formatClock(alerts.lastUpdated)}` : 'Loading…'}
          </span>
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              alerts.refresh();
              telemetry.refresh();
            }}
            disabled={refreshing}
          >
            <RefreshCw className={cn('h-3.5 w-3.5', refreshing && 'animate-spin')} />
            Refresh
          </Button>
        </div>
      </div>

      <ErrorBanner error={alerts.error} stale={!!alerts.data} onRetry={alerts.refresh} />
      <ErrorBanner error={!selected ? actionError : null} onRetry={null} />

      {/* Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Tabs aria-label="Alert status filter" items={tabItems} value={filter} onChange={changeFilter} />
        <div className="relative w-full sm:w-72">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" aria-hidden="true" />
          <input
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search this page: reference, ID, amount…"
            aria-label="Search alerts on this page"
            className="h-8 w-full rounded-md border bg-transparent pl-8 pr-3 text-xs placeholder:text-muted-foreground/60 hover:border-ring/60"
          />
        </div>
      </div>

      <Card className="overflow-hidden">
        <Table>
          <THead>
            <TR>
              <SortHeader label="Score" sortKey="score" sort={sort} onSort={toggleSort} />
              <SortHeader label="Reference" sortKey="ref" sort={sort} onSort={toggleSort} />
              <SortHeader label="Amount" sortKey="amount" sort={sort} onSort={toggleSort} align="right" />
              <SortHeader label="Transaction time" sortKey="tx_time" sort={sort} onSort={toggleSort} />
              <SortHeader label="Detected" sortKey="created_at" sort={sort} onSort={toggleSort} />
              <TH>Top driver</TH>
              <SortHeader label="Status" sortKey="status" sort={sort} onSort={toggleSort} />
              <TH className="w-8" />
            </TR>
          </THead>
          <TBody>
            {alerts.loading && !items
              ? Array.from({ length: 8 }).map((_, i) => (
                  <TR key={i}>
                    {Array.from({ length: 8 }).map((__, j) => (
                      <TD key={j}>
                        <Skeleton className="h-4 w-full max-w-[7rem]" />
                      </TD>
                    ))}
                  </TR>
                ))
              : alerts.loading
                ? Array.from({ length: 6 }).map((_, i) => (
                    <TR key={i}>
                      {Array.from({ length: 8 }).map((__, j) => (
                        <TD key={j}>
                          <Skeleton className="h-4 w-full max-w-[7rem]" />
                        </TD>
                      ))}
                    </TR>
                  ))
                : visible.map((a) => (
                    <AlertTableRow
                      key={a.alert_id}
                      alert={a}
                      canModify={canModify}
                      updating={updatingId === a.alert_id}
                      onOpen={() => {
                        setActionError(null);
                        setSelected(a);
                      }}
                      onStatusChange={changeStatus}
                    />
                  ))}
          </TBody>
        </Table>

        {!alerts.loading && items && visible.length === 0 && (
          <EmptyState
            icon={ShieldAlert}
            title={query ? 'No alerts match your search' : 'No alerts here'}
            description={
              query
                ? 'Search only covers the rows loaded on this page.'
                : filter === 'active'
                  ? 'Nothing is waiting for review. The system is operating within normal parameters.'
                  : 'No alerts have this status.'
            }
          />
        )}
        {alerts.error && !alerts.data && !alerts.loading && (
          <EmptyState icon={ShieldAlert} title="Could not load alerts" description={getErrorMessage(alerts.error)} />
        )}

        {/* Footer: range, rows per page, pager */}
        <div className="flex flex-wrap items-center justify-between gap-3 border-t px-4 py-2.5 text-xs text-muted-foreground">
          <p>
            <span className="num text-foreground">{from}–{to}</span> of <span className="num text-foreground">{formatInt(total)}</span> alerts
            <span className="hidden md:inline"> · sorting applies to the rows on this page</span>
          </p>
          <div className="flex items-center gap-3">
            <label className="flex items-center gap-2">
              Rows
              <Select
                value={pageSize}
                onChange={(e) => {
                  setPageSize(Number(e.target.value));
                  setPage(0);
                }}
                aria-label="Rows per page"
              >
                {PAGE_SIZES.map((n) => (
                  <option key={n} value={n}>
                    {n}
                  </option>
                ))}
              </Select>
            </label>
            <div className="flex items-center gap-1">
              <Button variant="outline" size="icon" onClick={() => setPage((p) => Math.max(0, p - 1))} disabled={page === 0} aria-label="Previous page">
                <ChevronLeft className="h-4 w-4" />
              </Button>
              <span className="num min-w-[4.5rem] text-center">
                Page {page + 1} / {lastPage + 1}
              </span>
              <Button variant="outline" size="icon" onClick={() => setPage((p) => Math.min(lastPage, p + 1))} disabled={page >= lastPage} aria-label="Next page">
                <ChevronRight className="h-4 w-4" />
              </Button>
            </div>
          </div>
        </div>
      </Card>

      <AlertDetailSheet
        alert={selected}
        onClose={closeSheet}
        onStatusChange={changeStatus}
        canModify={canModify}
        updating={!!selected && updatingId === selected.alert_id}
        error={selected ? actionError : null}
      />
    </div>
  );
}

function AlertTableRow({ alert, canModify, updating, onOpen, onStatusChange }) {
  const top = alert.shap_reasons?.[0];
  const up = top?.direction === 'INCREASE RISK';

  return (
    <TR
      tabIndex={0}
      onClick={onOpen}
      onKeyDown={(e) => {
        if (e.target === e.currentTarget && (e.key === 'Enter' || e.key === ' ')) {
          e.preventDefault();
          onOpen();
        }
      }}
      className="group cursor-pointer hover:bg-muted/40 focus-visible:bg-muted/40 focus-visible:ring-inset"
      aria-label={`Open alert ${alert.external_id || alert.tx_id}`}
    >
      <TD>
        <RiskScore score={alert.fraud_score} />
      </TD>
      <TD>
        <p className="num max-w-[12rem] truncate text-xs font-medium" title={alert.external_id || alert.tx_id}>
          {alert.external_id || shortId(alert.tx_id)}
        </p>
        <p className="num mt-0.5 text-2xs text-muted-foreground" title={alert.tx_id}>
          {shortId(alert.tx_id)}…
        </p>
      </TD>
      <TD className="num text-right text-xs font-medium">{formatCurrency(alert.amount)}</TD>
      <TD>
        <p className="num whitespace-nowrap text-xs">{formatDateTime(alert.transaction_time)}</p>
        <p className="mt-0.5 text-2xs text-muted-foreground">{alert.transaction_time ? formatTimeAgo(alert.transaction_time) : ''}</p>
      </TD>
      <TD className="whitespace-nowrap text-xs text-muted-foreground" title={formatDateTime(alert.created_at)}>
        {formatTimeAgo(alert.created_at)}
      </TD>
      <TD>
        {top ? (
          <span className="inline-flex items-center gap-1.5 text-xs" title={`${top.feature}: ${top.direction.toLowerCase()}`}>
            {up ? (
              <ArrowUp className="h-3.5 w-3.5 text-risk-high" aria-label="raises risk" />
            ) : (
              <ArrowDown className="h-3.5 w-3.5 text-risk-low" aria-label="lowers risk" />
            )}
            <span className="num">{top.feature}</span>
            <span className="num text-muted-foreground">{top.attribution_score.toFixed(2)}</span>
          </span>
        ) : (
          <span className="text-xs text-muted-foreground">—</span>
        )}
      </TD>
      <TD onClick={(e) => e.stopPropagation()} onKeyDown={(e) => e.stopPropagation()}>
        <Select
          value={alert.status}
          disabled={!canModify || updating}
          onChange={(e) => onStatusChange(alert, e.target.value)}
          aria-label={`Status of alert ${alert.external_id || alert.tx_id}`}
          title={canModify ? 'Change status' : 'Your role is read-only'}
          className="w-36"
        >
          {STATUS_ORDER.map((s) => (
            <option key={s} value={s}>
              {STATUS_META[s].label}
            </option>
          ))}
        </Select>
      </TD>
      <TD className="w-8 text-muted-foreground">
        <ChevronRight className="h-4 w-4 opacity-0 transition-opacity group-hover:opacity-100 group-focus-visible:opacity-100" aria-hidden="true" />
      </TD>
    </TR>
  );
}
