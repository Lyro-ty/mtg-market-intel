import { cn } from '@/lib/utils';
import { User, CheckCircle, Shield, Trophy } from 'lucide-react';
import type { ReputationTier } from '@/types';

interface ReputationBadgeProps {
  tier: ReputationTier;
  size?: 'sm' | 'md' | 'lg';
  showIcon?: boolean;
  className?: string;
}

// Tier styling configuration
const tierStyles: Record<ReputationTier, {
  base: string;
  glow?: string;
  animated?: boolean;
}> = {
  new: {
    base: 'bg-gray-500/20 text-gray-400 border-gray-500/30',
  },
  established: {
    base: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  },
  trusted: {
    base: 'bg-purple-500/20 text-purple-400 border-purple-500/30',
    glow: 'shadow-[0_0_8px_rgba(168,85,247,0.3)]',
  },
  elite: {
    base: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
    glow: 'shadow-[0_0_12px_rgba(245,158,11,0.4)]',
    animated: true,
  },
};

// Tier labels
const tierLabels: Record<ReputationTier, string> = {
  new: 'New Trader',
  established: 'Established',
  trusted: 'Trusted',
  elite: 'Elite Trader',
};

// Size configuration
const sizeStyles = {
  sm: {
    badge: 'px-2 py-0.5 text-xs gap-1',
    icon: 'h-3 w-3',
  },
  md: {
    badge: 'px-2.5 py-1 text-sm gap-1.5',
    icon: 'h-4 w-4',
  },
  lg: {
    badge: 'px-3 py-1.5 text-base gap-2',
    icon: 'h-5 w-5',
  },
};

// Icons per tier
const tierIcons: Record<ReputationTier, React.ComponentType<{ className?: string }> | null> = {
  new: User,
  established: CheckCircle,
  trusted: Shield,
  elite: Trophy,
};

export function ReputationBadge({
  tier,
  size = 'md',
  showIcon = false,
  className,
}: ReputationBadgeProps) {
  const style = tierStyles[tier];
  const sizeStyle = sizeStyles[size];
  const Icon = showIcon ? tierIcons[tier] : null;

  return (
    <span
      className={cn(
        // Base badge styles
        'inline-flex items-center rounded-full border font-medium',
        sizeStyle.badge,
        style.base,
        // Glow effect for trusted and elite
        style.glow,
        // Animated glow for elite tier
        style.animated && 'animate-reputation-glow',
        className
      )}
    >
      {Icon && <Icon className={cn(sizeStyle.icon, 'flex-shrink-0')} />}
      {tierLabels[tier]}
    </span>
  );
}

export default ReputationBadge;
