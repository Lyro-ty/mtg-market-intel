import { cn } from '@/lib/utils';

interface IconProps {
  className?: string;
}

export function IconDashboard({ className }: IconProps) {
  return (
    <svg
      viewBox="0 0 512 512"
      fill="currentColor"
      className={cn('w-5 h-5', className)}
    >
      {/* Dashboard/grid icon */}
      <path d="M64 64h160v160H64V64zm224 0h160v160H288V64zM64 288h160v160H64V288zm224 0h160v160H288V288z" />
    </svg>
  );
}
