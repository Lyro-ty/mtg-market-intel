import { cn } from '@/lib/utils';

interface IconProps {
  className?: string;
}

export function IconAlert({ className }: IconProps) {
  return (
    <svg
      viewBox="0 0 512 512"
      fill="currentColor"
      className={cn('w-5 h-5', className)}
    >
      {/* Bell/alert icon */}
      <path d="M256 32c14.2 0 27.3 7.5 34.5 19.8l112 192c7.3 12.4 7.3 27.7 .2 40.1S378.5 304 364.2 304H147.8c-14.3 0-27.6-7.7-34.7-20.1s-7-27.8 .2-40.1l112-192C232.7 39.5 245.8 32 256 32zm0 128c-13.3 0-24 10.7-24 24V264c0 13.3 10.7 24 24 24s24-10.7 24-24V184c0-13.3-10.7-24-24-24zm32 224a32 32 0 1 0 -64 0 32 32 0 1 0 64 0z" />
    </svg>
  );
}
