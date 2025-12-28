import { cn } from '@/lib/utils';

interface IconProps {
  className?: string;
}

export function IconHold({ className }: IconProps) {
  return (
    <svg
      viewBox="0 0 512 512"
      fill="currentColor"
      className={cn('w-5 h-5', className)}
    >
      {/* Hand/hold icon */}
      <path d="M288 32c0-17.7-14.3-32-32-32s-32 14.3-32 32V256c0 17.7 14.3 32 32 32s32-14.3 32-32V32zM144 64c0-17.7-14.3-32-32-32s-32 14.3-32 32v192c0 17.7 14.3 32 32 32s32-14.3 32-32V64zM432 64c0-17.7-14.3-32-32-32s-32 14.3-32 32v192c0 17.7 14.3 32 32 32s32-14.3 32-32V64zM0 320c0 70.7 57.3 128 128 128h256c70.7 0 128-57.3 128-128V256H0v64z" />
    </svg>
  );
}
