// frontend/src/components/ornate/divider.tsx
import { cn } from '@/lib/utils';

interface OrnateDividerProps {
  className?: string;
}

export function OrnateDivider({ className }: OrnateDividerProps) {
  return (
    <div className={cn('flex items-center gap-4 my-8', className)}>
      <div className="flex-1 h-px bg-gradient-to-r from-transparent via-[rgb(var(--magic-gold))]/30 to-transparent" />
      <svg
        className="w-4 h-4 text-[rgb(var(--magic-gold))]/50"
        viewBox="0 0 24 24"
        fill="currentColor"
      >
        <path d="M12 2L2 12l10 10 10-10L12 2z" />
      </svg>
      <div className="flex-1 h-px bg-gradient-to-r from-transparent via-[rgb(var(--magic-gold))]/30 to-transparent" />
    </div>
  );
}
