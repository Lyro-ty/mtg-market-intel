// frontend/src/components/ornate/flourish.tsx
import { cn } from '@/lib/utils';

interface FlourishProps {
  position: 'top-left' | 'top-right' | 'bottom-left' | 'bottom-right';
  className?: string;
}

export function Flourish({ position, className }: FlourishProps) {
  const positionClasses = {
    'top-left': 'top-1 left-1',
    'top-right': 'top-1 right-1 rotate-90',
    'bottom-left': 'bottom-1 left-1 -rotate-90',
    'bottom-right': 'bottom-1 right-1 rotate-180',
  };

  return (
    <svg
      className={cn(
        'absolute w-4 h-4 text-[rgb(var(--magic-gold))]/40',
        positionClasses[position],
        className
      )}
      viewBox="0 0 24 24"
      fill="currentColor"
    >
      <path d="M2 2 C2 12, 12 12, 12 22 L12 12 L22 12 C12 12, 12 2, 2 2Z" />
    </svg>
  );
}
