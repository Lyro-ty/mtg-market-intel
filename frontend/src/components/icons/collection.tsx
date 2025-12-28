import { cn } from '@/lib/utils';

interface IconProps {
  className?: string;
}

export function IconCollection({ className }: IconProps) {
  return (
    <svg
      viewBox="0 0 512 512"
      fill="currentColor"
      className={cn('w-5 h-5', className)}
    >
      {/* Stacked cards/collection icon */}
      <path d="M64 32C28.7 32 0 60.7 0 96v288c0 35.3 28.7 64 64 64h384c35.3 0 64-28.7 64-64V96c0-35.3-28.7-64-64-64H64zm32 64h320c17.7 0 32 14.3 32 32v240c0 17.7-14.3 32-32 32H96c-17.7 0-32-14.3-32-32V128c0-17.7 14.3-32 32-32z" />
    </svg>
  );
}
