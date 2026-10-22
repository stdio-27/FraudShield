import { useEffect, useRef, useState } from 'react';
import { Check, ChevronDown, X } from 'lucide-react';
import { useHealth } from '../hooks/useHealth';
import { cn } from '../lib/utils';
import { formatClock } from '../lib/format';

function Row({ label, ok, detail }) {
  return (
    <li className="flex items-center justify-between gap-6 py-1.5">
      <span className="text-muted-foreground">{label}</span>
      <span className={cn('inline-flex items-center gap-1.5 font-medium', ok ? 'text-foreground' : 'text-risk-high')}>
        {ok ? <Check className="h-3.5 w-3.5 text-risk-low" /> : <X className="h-3.5 w-3.5" />}
        {detail}
      </span>
    </li>
  );
}

/** Live system status from GET /health (API reachability, model artifacts, database, Redis). */
export default function SystemStatus() {
  const { data, loading, lastUpdated } = useHealth();
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    if (!open) return undefined;
    const onDown = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    };
    const onKey = (e) => e.key === 'Escape' && setOpen(false);
    document.addEventListener('mousedown', onDown);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDown);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);

  let tone = 'bg-muted-foreground';
  let label = 'Checking…';
  if (!loading && data) {
    if (!data.reachable) {
      tone = 'bg-risk-high';
      label = 'API unreachable';
    } else if (data.status === 'healthy') {
      // Redis is an optimisation: the API still works without it.
      tone = data.redis ? 'bg-risk-low' : 'bg-risk-medium';
      label = data.redis ? 'All systems operational' : 'Operational, cache offline';
    } else {
      tone = 'bg-risk-high';
      label = 'Degraded';
    }
  }

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-haspopup="true"
        className="inline-flex h-8 items-center gap-2 rounded-md border px-2.5 text-xs font-medium text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
      >
        <span className={cn('h-2 w-2 rounded-full', tone)} aria-hidden="true" />
        <span className="hidden sm:inline">{label}</span>
        <ChevronDown className="h-3.5 w-3.5" aria-hidden="true" />
      </button>

      {open && (
        <div
          role="status"
          className="absolute right-0 top-full z-40 mt-2 w-72 animate-fade-in rounded-lg border bg-popover p-3 text-xs shadow-xl"
        >
          <p className="mb-1 text-2xs font-medium uppercase tracking-wider text-muted-foreground">System status</p>
          {data?.reachable ? (
            <ul className="divide-y">
              <Row label="API" ok detail="Reachable" />
              <Row label="Scoring model" ok={!!data.artifacts_loaded} detail={data.artifacts_loaded ? 'Loaded' : 'Not loaded'} />
              <Row label="Database" ok={!!data.database} detail={data.database ? 'Connected' : 'Unavailable'} />
              <Row label="Cache (Redis)" ok={!!data.redis} detail={data.redis ? 'Connected' : 'Offline'} />
            </ul>
          ) : (
            <p className="py-2 text-muted-foreground">
              The API did not respond. Check that the backend is running and that CORS allows this origin.
            </p>
          )}
          <p className="mt-2 border-t pt-2 text-muted-foreground">
            Checked <span className="num">{formatClock(lastUpdated)}</span> · refreshes every 30 s
          </p>
        </div>
      )}
    </div>
  );
}
