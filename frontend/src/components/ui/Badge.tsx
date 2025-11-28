import { cn } from '@/lib/utils';
import { type ReactNode } from 'react';

interface BadgeProps {
  children: ReactNode;
  variant?: 'default' | 'success' | 'warning' | 'danger' | 'info';
  size?: 'sm' | 'md';
  className?: string;
}

export function Badge({
  children,
  variant = 'default',
  size = 'sm',
  className,
}: BadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center font-medium rounded-full',
        // Variants
        {
          'bg-[rgb(var(--secondary))] text-[rgb(var(--foreground))]':
            variant === 'default',
          'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400':
            variant === 'success',
          'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400':
            variant === 'warning',
          'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400':
            variant === 'danger',
          'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400':
            variant === 'info',
        },
        // Sizes
        {
          'text-xs px-2 py-0.5': size === 'sm',
          'text-sm px-2.5 py-1': size === 'md',
        },
        className
      )}
    >
      {children}
    </span>
  );
}

export function ActionBadge({ action }: { action: string }) {
  const variant = {
    BUY: 'success',
    SELL: 'danger',
    HOLD: 'warning',
  }[action] as 'success' | 'danger' | 'warning';

  return <Badge variant={variant}>{action}</Badge>;
}

