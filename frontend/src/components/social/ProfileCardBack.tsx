'use client';

import { cn } from '@/lib/utils';
import { formatDate } from '@/lib/utils';
import {
  Trophy,
  TrendingUp,
  Calendar,
  Percent,
  Repeat2,
  Star,
  BarChart3,
} from 'lucide-react';

interface Badge {
  key: string;
  icon: string;
  name: string;
}

interface ProfileCardBackProps {
  username: string;
  displayName?: string;
  badges: Badge[];
  tradeCount: number;
  successRate?: number;
  formats: string[];
  memberSince: string;
  variant?: 'full' | 'standard' | 'compact';
  className?: string;
}

// Badge icon mapping
function BadgeIcon({ iconKey }: { iconKey: string }) {
  const iconMap: Record<string, typeof Trophy> = {
    trophy: Trophy,
    star: Star,
    trending: TrendingUp,
    repeat: Repeat2,
    chart: BarChart3,
  };

  const Icon = iconMap[iconKey] || Trophy;
  return <Icon className="h-4 w-4" />;
}

// Mini activity chart placeholder
function ActivityChart({ className }: { className?: string }) {
  // Placeholder bars representing trading activity
  const bars = [40, 65, 30, 80, 55, 70, 45];

  return (
    <div className={cn('flex items-end gap-1 h-8', className)}>
      {bars.map((height, i) => (
        <div
          key={i}
          className="w-2 bg-amber-500/60 rounded-t transition-all hover:bg-amber-500"
          style={{ height: `${height}%` }}
        />
      ))}
    </div>
  );
}

export function ProfileCardBack({
  username,
  displayName,
  badges,
  tradeCount,
  successRate = 95,
  formats,
  memberSince,
  variant = 'standard',
  className,
}: ProfileCardBackProps) {
  const isCompact = variant === 'compact';
  const isFull = variant === 'full';

  // Compact variant - minimal info
  if (isCompact) {
    return (
      <div
        className={cn(
          'h-full w-full p-3 flex flex-col justify-between',
          'bg-gradient-to-br from-gray-800/95 to-gray-900/95 text-white',
          className
        )}
      >
        <div className="text-center">
          <p className="text-xs text-gray-400">Stats</p>
          <p className="text-sm font-bold text-amber-400">{tradeCount} trades</p>
        </div>
        <div className="text-center">
          <p className="text-xs text-gray-500">Since {formatDate(memberSince, { year: 'numeric' })}</p>
        </div>
      </div>
    );
  }

  return (
    <div
      className={cn(
        'h-full w-full p-4 flex flex-col',
        'bg-gradient-to-br from-gray-800/95 via-gray-850/95 to-gray-900/95 text-white',
        isFull && 'p-5',
        className
      )}
    >
      {/* Header */}
      <div className="text-center mb-3">
        <h3 className={cn(
          'font-bold text-amber-400 truncate',
          isFull ? 'text-lg' : 'text-base'
        )}>
          {displayName || username}
        </h3>
        <p className="text-xs text-gray-400">Trading Card Stats</p>
      </div>

      {/* Achievements/Badges */}
      {badges.length > 0 && (
        <div className="mb-3">
          <p className="text-xs text-gray-500 uppercase tracking-wider mb-1.5">
            Achievements
          </p>
          <div className="flex flex-wrap gap-1.5">
            {badges.slice(0, isFull ? 6 : 4).map((badge) => (
              <div
                key={badge.key}
                className="flex items-center gap-1 px-2 py-1 rounded-full bg-amber-500/20 text-amber-400 text-xs"
                title={badge.name}
              >
                <BadgeIcon iconKey={badge.icon} />
                <span className="truncate max-w-16">{badge.name}</span>
              </div>
            ))}
            {badges.length > (isFull ? 6 : 4) && (
              <span className="text-xs text-gray-500 px-2 py-1">
                +{badges.length - (isFull ? 6 : 4)} more
              </span>
            )}
          </div>
        </div>
      )}

      {/* Trading Statistics */}
      <div className="mb-3 flex-1">
        <p className="text-xs text-gray-500 uppercase tracking-wider mb-1.5">
          Trading Stats
        </p>
        <div className="grid grid-cols-2 gap-2">
          <div className="flex items-center gap-2 p-2 rounded bg-gray-700/50">
            <Repeat2 className="h-4 w-4 text-blue-400" />
            <div>
              <p className="text-xs text-gray-400">Trades</p>
              <p className="font-bold text-white">{tradeCount}</p>
            </div>
          </div>
          <div className="flex items-center gap-2 p-2 rounded bg-gray-700/50">
            <Percent className="h-4 w-4 text-green-400" />
            <div>
              <p className="text-xs text-gray-400">Success</p>
              <p className="font-bold text-white">{successRate}%</p>
            </div>
          </div>
        </div>
      </div>

      {/* Format Specialties */}
      {formats.length > 0 && (
        <div className="mb-3">
          <p className="text-xs text-gray-500 uppercase tracking-wider mb-1.5">
            Formats
          </p>
          <div className="flex flex-wrap gap-1">
            {formats.slice(0, 3).map((format) => (
              <span
                key={format}
                className="px-2 py-0.5 rounded text-xs bg-gray-700/50 text-gray-300"
              >
                {format}
              </span>
            ))}
            {formats.length > 3 && (
              <span className="text-xs text-gray-500 px-1">
                +{formats.length - 3}
              </span>
            )}
          </div>
        </div>
      )}

      {/* Activity Chart (full variant only) */}
      {isFull && (
        <div className="mb-3">
          <p className="text-xs text-gray-500 uppercase tracking-wider mb-1.5">
            Recent Activity
          </p>
          <ActivityChart />
        </div>
      )}

      {/* Member Since */}
      <div className="mt-auto pt-2 border-t border-gray-700/50 flex items-center justify-center gap-1.5 text-xs text-gray-500">
        <Calendar className="h-3 w-3" />
        <span>Member since {formatDate(memberSince, { month: 'short', year: 'numeric' })}</span>
      </div>
    </div>
  );
}

export default ProfileCardBack;
