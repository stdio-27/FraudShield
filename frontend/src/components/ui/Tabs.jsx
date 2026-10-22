import { cn } from '../../lib/utils';

/** Segmented control. `items`: [{ value, label, count? }] */
export function Tabs({ items, value, onChange, className, 'aria-label': ariaLabel }) {
  return (
    <div
      role="tablist"
      aria-label={ariaLabel}
      className={cn('inline-flex items-center gap-0.5 rounded-md border bg-muted/50 p-0.5', className)}
    >
      {items.map((item) => {
        const active = item.value === value;
        return (
          <button
            key={item.value}
            role="tab"
            type="button"
            aria-selected={active}
            onClick={() => onChange(item.value)}
            className={cn(
              'inline-flex h-7 items-center gap-1.5 rounded-sm px-2.5 text-xs font-medium transition-colors',
              active ? 'bg-background text-foreground shadow-sm ring-1 ring-border' : 'text-muted-foreground hover:text-foreground',
            )}
          >
            {item.label}
            {item.count != null && (
              <span className="num text-2xs text-muted-foreground">{item.count}</span>
            )}
          </button>
        );
      })}
    </div>
  );
}
