const EM_DASH = '—';

const intFmt = new Intl.NumberFormat('en-US');
const compactFmt = new Intl.NumberFormat('en-US', { notation: 'compact', maximumFractionDigits: 1 });
const currencyFmt = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' });
const currencyCompactFmt = new Intl.NumberFormat('en-US', {
  style: 'currency',
  currency: 'USD',
  notation: 'compact',
  maximumFractionDigits: 1,
});

const isNum = (v) => typeof v === 'number' && Number.isFinite(v);

export const formatInt = (v) => (isNum(v) ? intFmt.format(v) : EM_DASH);
export const formatCompact = (v) => (isNum(v) ? compactFmt.format(v) : EM_DASH);
export const formatCurrency = (v) => (isNum(v) ? currencyFmt.format(v) : EM_DASH);
export const formatCurrencyCompact = (v) => (isNum(v) ? currencyCompactFmt.format(v) : EM_DASH);
export const formatScore = (v, digits = 4) => (isNum(v) ? v.toFixed(digits) : EM_DASH);
export const formatPercent = (v, digits = 1) => (isNum(v) ? `${v.toFixed(digits)}%` : EM_DASH);

/** "20 Oct 2026, 14:03:22" in the viewer's local time zone. */
export function formatDateTime(iso) {
  if (!iso) return EM_DASH;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return EM_DASH;
  return d.toLocaleString('en-GB', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  });
}

/** "14:03:22" in the viewer's local time zone. */
export function formatClock(dateOrIso) {
  if (!dateOrIso) return EM_DASH;
  const d = dateOrIso instanceof Date ? dateOrIso : new Date(dateOrIso);
  if (Number.isNaN(d.getTime())) return EM_DASH;
  return d.toLocaleTimeString('en-GB', { hour12: false });
}

/** Axis label: time only for windows within a day, otherwise "20 Oct 14:05". */
export function formatBucketLabel(iso, withDate = false) {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  const time = d.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', hour12: false });
  if (!withDate) return time;
  return `${d.toLocaleDateString('en-GB', { day: '2-digit', month: 'short' })} ${time}`;
}

/** "3m ago", "2h ago", "5d ago". */
export function formatTimeAgo(iso, now = Date.now()) {
  if (!iso) return EM_DASH;
  const t = new Date(iso).getTime();
  if (Number.isNaN(t)) return EM_DASH;
  const seconds = Math.round((now - t) / 1000);
  if (seconds < 0) return 'just now';
  if (seconds < 45) return `${seconds}s ago`;
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 48) return `${hours}h ago`;
  return `${Math.round(hours / 24)}d ago`;
}

export const shortId = (id, n = 8) => (id ? String(id).slice(0, n) : EM_DASH);
