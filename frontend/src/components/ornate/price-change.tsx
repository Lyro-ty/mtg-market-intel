// frontend/src/components/ornate/price-change.tsx
import { TrendingUp, TrendingDown, Minus } from 'lucide-react';
import { cn, safeToFixed } from '@/lib/utils';

interface PriceChangeProps {
  value: number | null | undefined;
  format?: 'percent' | 'currency';
  size?: 'sm' | 'md' | 'lg';
  showIcon?: boolean;
  className?: string;
}

export function PriceChange({
  value,
  format = 'percent',
  size = 'md',
  showIcon = true,
  className,
}: PriceChangeProps) {
  // Handle null/undefined values gracefully
  if (value === null || value === undefined || isNaN(value)) {
    return null;
  }

  const isPositive = value > 0;
  const isNegative = value < 0;
  const isNeutral = value === 0;

  const sizeClasses = {
    sm: 'text-xs',
    md: 'text-sm',
    lg: 'text-base',
  };

  const iconSizes = {
    sm: 'w-3 h-3',
    md: 'w-4 h-4',
    lg: 'w-5 h-5',
  };

  const formatted =
    format === 'percent'
      ? `${isPositive ? '+' : ''}${safeToFixed(value, 1)}%`
      : `${isPositive ? '+' : ''}$${safeToFixed(Math.abs(value), 2)}`;

  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 font-medium',
        sizeClasses[size],
        isPositive && 'text-[rgb(var(--success))]',
        isNegative && 'text-[rgb(var(--destructive))]',
        isNeutral && 'text-muted-foreground',
        className
      )}
    >
      {showIcon && (
        <>
          {isPositive && <TrendingUp className={iconSizes[size]} />}
          {isNegative && <TrendingDown className={iconSizes[size]} />}
          {isNeutral && <Minus className={iconSizes[size]} />}
        </>
      )}
      {formatted}
    </span>
  );
}
