import { forwardRef } from 'react';
import { cn } from '../../lib/utils';

const VARIANTS = {
  default: 'bg-primary text-primary-foreground hover:bg-primary/90',
  outline: 'border bg-transparent hover:bg-accent',
  ghost: 'hover:bg-accent text-muted-foreground hover:text-foreground',
  destructive: 'bg-risk-high text-white hover:bg-risk-high/90',
};

const SIZES = {
  sm: 'h-8 px-3 text-xs',
  md: 'h-9 px-4 text-sm',
  icon: 'h-8 w-8',
};

export const Button = forwardRef(function Button(
  { variant = 'default', size = 'md', className, type = 'button', ...props },
  ref,
) {
  return (
    <button
      ref={ref}
      type={type}
      className={cn(
        'inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md font-medium transition-colors',
        'disabled:pointer-events-none disabled:opacity-50',
        VARIANTS[variant],
        SIZES[size],
        className,
      )}
      {...props}
    />
  );
});
