import { useCallback, useEffect, useRef, useState } from 'react';

/**
 * Fetch on mount, whenever `deps` change, and every `interval` ms.
 *
 * - Stale-while-revalidate: a failed refresh keeps the previous `data` and sets
 *   `error`, so a network blip never blanks the screen.
 * - `loading` is true only until the first response for the current data set.
 * - Polling pauses while the tab is hidden and catches up when it becomes visible.
 * - Out-of-order responses (e.g. after a filter change) are discarded.
 */
export function usePolling(fetcher, { interval = 30000, deps = [], enabled = true } = {}) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [lastUpdated, setLastUpdated] = useState(null);

  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;
  const requestId = useRef(0);
  const lastRun = useRef(0);

  const run = useCallback(async () => {
    const id = ++requestId.current;
    lastRun.current = Date.now();
    setRefreshing(true);
    try {
      const result = await fetcherRef.current();
      if (id !== requestId.current) return;
      setData(result);
      setError(null);
      setLastUpdated(new Date());
    } catch (err) {
      if (id !== requestId.current) return;
      setError(err);
    } finally {
      if (id === requestId.current) {
        setLoading(false);
        setRefreshing(false);
      }
    }
  }, []);

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (!enabled) return undefined;
    // New dependency set (filter, window, page): show skeletons instead of the previous set's rows.
    setLoading(true);
    run();

    const tick = () => {
      if (document.visibilityState === 'visible') run();
    };
    const timer = setInterval(tick, interval);
    const onVisible = () => {
      if (document.visibilityState === 'visible' && Date.now() - lastRun.current >= interval) run();
    };
    document.addEventListener('visibilitychange', onVisible);

    return () => {
      clearInterval(timer);
      document.removeEventListener('visibilitychange', onVisible);
      requestId.current += 1; // invalidate in-flight requests
    };
  }, [enabled, interval, run, ...deps]);

  return { data, error, loading, refreshing, lastUpdated, refresh: run };
}
