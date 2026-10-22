import { ChevronDown } from 'lucide-react';
import { cn } from '../../lib/utils';

/** Styled native <select>: accessible and keyboard friendly without extra dependencies. */
export function Select({ className, children, ...props }) {
  return (
    <div className="relative inline-flex">
      <select
        className={cn(
          'h-8 appearance-none rounded-md border bg-transparent pl-2.5 pr-7 text-xs font-medium text-foreground',
          'hover:bg-accent disabled:cursor-not-allowed disabled:opacity-50',
          className,
        )}
        {...props}
      >
        {children}
      </select>
      <ChevronDown
        className="pointer-events-none absolute right-2 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground"
        aria-hidden="true"
      />
    </div>
  );
}
