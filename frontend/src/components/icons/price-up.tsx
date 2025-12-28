import { cn } from '@/lib/utils';

interface IconProps {
  className?: string;
}

export function IconPriceUp({ className }: IconProps) {
  return (
    <svg
      viewBox="0 0 512 512"
      fill="currentColor"
      className={cn('w-5 h-5', className)}
    >
      {/* Arrow up/price increase icon */}
      <path d="M233.4 105.4c12.5-12.5 32.8-12.5 45.3 0l192 192c12.5 12.5 12.5 32.8 0 45.3s-32.8 12.5-45.3 0L256 173.3 86.6 342.6c-12.5 12.5-32.8 12.5-45.3 0s-12.5-32.8 0-45.3l192-192z" />
    </svg>
  );
}
