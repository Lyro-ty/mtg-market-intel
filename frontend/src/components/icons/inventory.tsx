import { cn } from '@/lib/utils';

interface IconProps {
  className?: string;
}

export function IconInventory({ className }: IconProps) {
  return (
    <svg
      viewBox="0 0 512 512"
      fill="currentColor"
      className={cn('w-5 h-5', className)}
    >
      {/* Stacked boxes/inventory icon */}
      <path d="M32 32h192v192H32V32zm256 0h192v192H288V32zM32 288h192v192H32V288zm320-32v64h-64v64h64v64h64v-64h64v-64h-64v-64h-64z" />
    </svg>
  );
}
