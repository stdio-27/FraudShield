import { cn } from '../../lib/utils';

const TONES = {
  neutral: 'border-border bg-secondary text-secondary-foreground',
  outline: 'border-border text-muted-foreground',
  high: 'border-risk-high/30 bg-risk-high/10 text-risk-high',
  medium: 'border-risk-medium/30 bg-risk-medium/10 text-risk-medium',
  low: 'border-risk-low/30 bg-risk-low/10 text-risk-low',
};

const DOTS = {
  neutral: 'bg-muted-foreground',
  outline: 'bg-muted-foreground',
  high: 'bg-risk-high',
  medium: 'bg-risk-medium',
  low: 'bg-risk-low',
};

export function Badge({ tone = 'neutral', dot = false, className, children, ...props }) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 whitespace-nowrap rounded-md border px-2 py-0.5 text-2xs font-medium',
        TONES[tone],
        className,
      )}
      {...props}
    >
      {dot && <span className={cn('h-1.5 w-1.5 rounded-full', DOTS[tone])} aria-hidden="true" />}
      {children}
    </span>
  );
}
