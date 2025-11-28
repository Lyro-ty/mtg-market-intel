import { cn } from '@/lib/utils';

interface LoadingProps {
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

export function Loading({ size = 'md', className }: LoadingProps) {
  return (
    <div
      className={cn(
        'animate-spin rounded-full border-2 border-[rgb(var(--muted))] border-t-primary-500',
        {
          'w-4 h-4': size === 'sm',
          'w-8 h-8': size === 'md',
          'w-12 h-12': size === 'lg',
        },
        className
      )}
    />
  );
}

export function LoadingPage() {
  return (
    <div className="flex items-center justify-center min-h-[400px]">
      <Loading size="lg" />
    </div>
  );
}

export function LoadingCard() {
  return (
    <div className="animate-pulse">
      <div className="h-32 bg-[rgb(var(--secondary))] rounded-lg mb-4" />
      <div className="h-4 bg-[rgb(var(--secondary))] rounded w-3/4 mb-2" />
      <div className="h-4 bg-[rgb(var(--secondary))] rounded w-1/2" />
    </div>
  );
}

