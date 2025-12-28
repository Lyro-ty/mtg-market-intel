import { cn } from '@/lib/utils';

interface IconProps {
  className?: string;
}

export function IconPriceDown({ className }: IconProps) {
  return (
    <svg
      viewBox="0 0 512 512"
      fill="currentColor"
      className={cn('w-5 h-5', className)}
    >
      {/* Arrow down/price decrease icon */}
      <path d="M233.4 406.6c12.5 12.5 32.8 12.5 45.3 0l192-192c12.5-12.5 12.5-32.8 0-45.3s-32.8-12.5-45.3 0L256 338.7 86.6 169.4c-12.5-12.5-32.8-12.5-45.3 0s-12.5 32.8 0 45.3l192 192z" />
    </svg>
  );
}
