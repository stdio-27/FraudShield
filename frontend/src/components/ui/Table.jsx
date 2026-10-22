import { ArrowDown, ArrowUp, ChevronsUpDown } from 'lucide-react';
import { cn } from '../../lib/utils';

export function Table({ className, ...props }) {
  return (
    <div className="w-full overflow-x-auto">
      <table className={cn('w-full caption-bottom border-collapse text-sm', className)} {...props} />
    </div>
  );
}

export const THead = ({ className, ...props }) => (
  <thead className={cn('border-b bg-muted/30 [&_tr]:border-b-0', className)} {...props} />
);

export const TBody = ({ className, ...props }) => (
  <tbody className={cn('[&_tr:last-child]:border-0', className)} {...props} />
);

export const TR = ({ className, ...props }) => (
  <tr className={cn('border-b transition-colors', className)} {...props} />
);

export const TH = ({ className, ...props }) => (
  <th
    className={cn(
      'h-9 whitespace-nowrap px-3 text-left align-middle text-2xs font-medium uppercase tracking-wider text-muted-foreground',
      className,
    )}
    {...props}
  />
);

export const TD = ({ className, ...props }) => (
  <td className={cn('px-3 py-2.5 align-middle', className)} {...props} />
);

/** Sortable column header. `sort` is { key, dir }; clicking cycles via onSort(key). */
export function SortHeader({ label, sortKey, sort, onSort, align = 'left', className }) {
  const active = sort.key === sortKey;
  const Icon = !active ? ChevronsUpDown : sort.dir === 'asc' ? ArrowUp : ArrowDown;
  return (
    <TH
      className={cn(align === 'right' && 'text-right', className)}
      aria-sort={active ? (sort.dir === 'asc' ? 'ascending' : 'descending') : 'none'}
    >
      <button
        type="button"
        onClick={() => onSort(sortKey)}
        className={cn(
          '-mx-1 inline-flex items-center gap-1 rounded px-1 py-0.5 uppercase tracking-wider transition-colors hover:text-foreground',
          active && 'text-foreground',
          align === 'right' && 'flex-row-reverse',
        )}
      >
        {label}
        <Icon className={cn('h-3 w-3', !active && 'opacity-50')} aria-hidden="true" />
      </button>
    </TH>
  );
}
