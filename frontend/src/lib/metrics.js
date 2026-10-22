const BUCKET_MS = 5 * 60 * 1000;

/** Buckets arrive newest-first from the API; charts need oldest-first. */
export function chronological(buckets) {
  return [...(buckets || [])].sort((a, b) => new Date(a.bucket) - new Date(b.bucket));
}

/**
 * Compare the most recent half of the selected window with the half before it,
 * using only buckets the API actually returned (missing 5-minute buckets mean
 * zero activity).  The still-filling current bucket is excluded.
 *
 * `key`       numeric field of a bucket to aggregate
 * `weightKey` when given, the aggregate is a weighted mean (e.g. avg score by tx_count)
 *             instead of a sum
 *
 * Returns null when there is nothing meaningful to compare (no recent activity).
 */
export function windowDelta(buckets, key, windowMinutes, { weightKey } = {}) {
  const half = (windowMinutes * 60 * 1000) / 2;
  const end = Math.floor(Date.now() / BUCKET_MS) * BUCKET_MS; // start of the in-progress bucket
  const complete = (buckets || []).filter((b) => new Date(b.bucket).getTime() + BUCKET_MS <= end);
  if (!complete.length) return null;

  const inRange = (from, to) =>
    complete.filter((b) => {
      const t = new Date(b.bucket).getTime();
      return t >= from && t < to;
    });
  const aggregate = (rows) => {
    if (weightKey) {
      const weight = rows.reduce((s, r) => s + (r[weightKey] || 0), 0);
      return weight ? rows.reduce((s, r) => s + (r[key] || 0) * (r[weightKey] || 0), 0) / weight : null;
    }
    return rows.reduce((s, r) => s + (r[key] || 0), 0);
  };

  const current = aggregate(inRange(end - half, end));
  const previous = aggregate(inRange(end - 2 * half, end - half));
  if (current == null && previous == null) return null;
  if (!weightKey && !current && !previous) return null;

  const pct = previous ? ((current - previous) / previous) * 100 : null;
  return { current, previous, pct, spanMinutes: windowMinutes / 2 };
}
