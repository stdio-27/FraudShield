import { AlertCircle, RefreshCw } from 'lucide-react';
import { cn } from '../../lib/utils';
import { getErrorMessage } from '../../services/api';
import { Button } from './Button';

/** Inline error strip. Rendered above stale data so a failed refresh never blanks the page. */
export function ErrorBanner({ error, onRetry, stale = false, className }) {
  if (!error) return null;
  return (
    <div
      role="alert"
      className={cn(
        'flex items-center gap-3 rounded-md border border-risk-high/30 bg-risk-high/5 px-3 py-2 text-xs',
        className,
      )}
    >
      <AlertCircle className="h-4 w-4 shrink-0 text-risk-high" aria-hidden="true" />
      <p className="min-w-0 flex-1 text-foreground/90">
        {getErrorMessage(error, 'Failed to load data')}
        {stale && <span className="text-muted-foreground"> Showing the last successful data.</span>}
      </p>
      {onRetry && (
        <Button variant="outline" size="sm" onClick={onRetry} className="h-7">
          <RefreshCw className="h-3 w-3" /> Retry
        </Button>
      )}
    </div>
  );
}

export function EmptyState({ icon: Icon, title, description, className }) {
  return (
    <div className={cn('flex flex-col items-center justify-center gap-2 px-6 py-14 text-center', className)}>
      {Icon && (
        <div className="mb-1 flex h-10 w-10 items-center justify-center rounded-md border bg-muted/40">
          <Icon className="h-5 w-5 text-muted-foreground" aria-hidden="true" />
        </div>
      )}
      <p className="text-sm font-medium">{title}</p>
      {description && <p className="max-w-sm text-xs text-muted-foreground">{description}</p>}
    </div>
  );
}
