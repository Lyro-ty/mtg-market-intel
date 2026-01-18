'use client';

import { cn } from '@/lib/utils';
import { motion } from 'framer-motion';
import { useState, useCallback } from 'react';
import {
  MessageCircle,
  Repeat2,
  UserPlus,
  Star,
  CircleDot,
} from 'lucide-react';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { FrameEffects, type FrameTier } from './FrameEffects';
import { ProfileCardBack } from './ProfileCardBack';

// Card type icons and colors
const cardTypeConfig: Record<string, { icon: typeof Star; color: string; label: string }> = {
  collector: { icon: Star, color: 'text-purple-400 bg-purple-500/20', label: 'Collector' },
  trader: { icon: Repeat2, color: 'text-blue-400 bg-blue-500/20', label: 'Trader' },
  brewer: { icon: CircleDot, color: 'text-green-400 bg-green-500/20', label: 'Brewer' },
  investor: { icon: Star, color: 'text-amber-400 bg-amber-500/20', label: 'Investor' },
};

export interface ProfileCardUser {
  id: number;
  username: string;
  displayName?: string;
  avatarUrl?: string;
  tagline?: string;
  cardType?: 'collector' | 'trader' | 'brewer' | 'investor';
  tradeCount: number;
  reputationScore?: number;
  reputationCount: number;
  frameTier: FrameTier;
  isOnline: boolean;
  badges: Array<{ key: string; icon: string; name: string }>;
  formats: string[];
  memberSince: string;
  hashid: string;
}

export interface ProfileCardProps {
  user: ProfileCardUser;
  variant?: 'full' | 'standard' | 'compact';
  showActions?: boolean;
  onMessage?: () => void;
  onTrade?: () => void;
  onConnect?: () => void;
  className?: string;
}

// Size configurations for different variants
const sizeConfig = {
  compact: {
    card: 'w-48 h-24',
    avatar: 'h-10 w-10',
    name: 'text-sm',
    stats: 'text-xs',
    padding: 'p-2',
  },
  standard: {
    card: 'w-64 h-80',
    avatar: 'h-16 w-16',
    name: 'text-lg',
    stats: 'text-sm',
    padding: 'p-4',
  },
  full: {
    card: 'w-80 h-96',
    avatar: 'h-20 w-20',
    name: 'text-xl',
    stats: 'text-base',
    padding: 'p-5',
  },
};

export function ProfileCard({
  user,
  variant = 'standard',
  showActions = true,
  onMessage,
  onTrade,
  onConnect,
  className,
}: ProfileCardProps) {
  const [isFlipped, setIsFlipped] = useState(false);
  const [isHovered, setIsHovered] = useState(false);

  const size = sizeConfig[variant];
  const isCompact = variant === 'compact';
  const cardTypeInfo = user.cardType ? cardTypeConfig[user.cardType] : null;
  const CardTypeIcon = cardTypeInfo?.icon;

  // Handle card flip
  const handleFlip = useCallback(() => {
    setIsFlipped((prev) => !prev);
  }, []);

  // Handle action button clicks - prevent flip
  const handleAction = useCallback(
    (e: React.MouseEvent, action?: () => void) => {
      e.stopPropagation();
      action?.();
    },
    []
  );

  // Get initials for avatar fallback
  const getInitials = (name: string) => {
    return name
      .split(' ')
      .map((n) => n[0])
      .join('')
      .toUpperCase()
      .slice(0, 2);
  };

  // Compact variant - simplified horizontal card
  if (isCompact) {
    return (
      <FrameEffects
        tier={user.frameTier}
        isHovered={isHovered}
        className={cn(size.card, className)}
      >
        <div
          className={cn(
            'h-full w-full cursor-pointer',
            'bg-gradient-to-br from-gray-800/90 to-gray-900/90',
            size.padding
          )}
          onClick={handleFlip}
          onMouseEnter={() => setIsHovered(true)}
          onMouseLeave={() => setIsHovered(false)}
          style={{ perspective: '1000px' }}
        >
          <motion.div
            className="relative w-full h-full"
            style={{ transformStyle: 'preserve-3d' }}
            animate={{ rotateY: isFlipped ? 180 : 0 }}
            transition={{ duration: 0.5, ease: 'easeInOut' }}
          >
            {/* Front */}
            <div
              className="absolute inset-0 flex items-center gap-3"
              style={{ backfaceVisibility: 'hidden' }}
            >
              <div className="relative">
                <Avatar className={size.avatar}>
                  <AvatarImage src={user.avatarUrl} alt={user.username} />
                  <AvatarFallback className="bg-gray-700 text-amber-400">
                    {getInitials(user.displayName || user.username)}
                  </AvatarFallback>
                </Avatar>
                {user.isOnline && (
                  <span className="absolute bottom-0 right-0 h-2.5 w-2.5 rounded-full bg-green-500 ring-2 ring-gray-800" />
                )}
              </div>
              <div className="flex-1 min-w-0">
                <p className={cn('font-semibold text-white truncate', size.name)}>
                  {user.displayName || user.username}
                </p>
                <p className={cn('text-gray-400 truncate', size.stats)}>
                  {user.tradeCount} trades
                </p>
              </div>
            </div>

            {/* Back */}
            <div
              className="absolute inset-0"
              style={{ backfaceVisibility: 'hidden', transform: 'rotateY(180deg)' }}
            >
              <ProfileCardBack
                username={user.username}
                displayName={user.displayName}
                badges={user.badges}
                tradeCount={user.tradeCount}
                formats={user.formats}
                memberSince={user.memberSince}
                variant="compact"
              />
            </div>
          </motion.div>
        </div>
      </FrameEffects>
    );
  }

  // Standard and Full variants
  return (
    <FrameEffects
      tier={user.frameTier}
      isHovered={isHovered}
      className={cn(size.card, className)}
    >
      <div
        className={cn(
          'h-full w-full cursor-pointer',
          'bg-gradient-to-br from-gray-800/90 to-gray-900/90'
        )}
        onClick={handleFlip}
        onMouseEnter={() => setIsHovered(true)}
        onMouseLeave={() => setIsHovered(false)}
        style={{ perspective: '1000px' }}
      >
        <motion.div
          className="relative w-full h-full"
          style={{ transformStyle: 'preserve-3d' }}
          animate={{ rotateY: isFlipped ? 180 : 0 }}
          transition={{ duration: 0.6, ease: 'easeInOut' }}
        >
          {/* Front of Card */}
          <div
            className={cn(
              'absolute inset-0 flex flex-col',
              size.padding
            )}
            style={{ backfaceVisibility: 'hidden' }}
          >
            {/* Header with Card Type Badge */}
            {cardTypeInfo && CardTypeIcon && (
              <div className="flex justify-end mb-2">
                <Badge
                  className={cn(
                    'text-xs font-medium',
                    cardTypeInfo.color
                  )}
                >
                  <CardTypeIcon className="h-3 w-3 mr-1" />
                  {cardTypeInfo.label}
                </Badge>
              </div>
            )}

            {/* Avatar and Name */}
            <div className="flex flex-col items-center text-center flex-1">
              <div className="relative mb-3">
                <Avatar className={cn(size.avatar, 'ring-2 ring-amber-500/50')}>
                  <AvatarImage src={user.avatarUrl} alt={user.username} />
                  <AvatarFallback className="bg-gray-700 text-amber-400 text-xl font-bold">
                    {getInitials(user.displayName || user.username)}
                  </AvatarFallback>
                </Avatar>
                {user.isOnline && (
                  <span className="absolute bottom-0 right-0 h-4 w-4 rounded-full bg-green-500 ring-2 ring-gray-800" />
                )}
              </div>

              <h3 className={cn('font-bold text-white mb-1 truncate max-w-full', size.name)}>
                {user.displayName || user.username}
              </h3>
              <p className="text-xs text-gray-500 mb-2">@{user.username}</p>

              {/* Tagline */}
              {user.tagline && (
                <p className="text-sm text-gray-400 italic mb-3 line-clamp-2">
                  "{user.tagline}"
                </p>
              )}

              {/* Stats Row */}
              <div className="flex items-center justify-center gap-4 mb-3">
                <div className="text-center">
                  <p className={cn('font-bold text-white', size.stats)}>{user.tradeCount}</p>
                  <p className="text-xs text-gray-500">Trades</p>
                </div>
                <div className="w-px h-8 bg-gray-700" />
                <div className="text-center">
                  <div className="flex items-center justify-center gap-1">
                    <Star className="h-4 w-4 text-amber-400 fill-amber-400" />
                    <span className={cn('font-bold text-white', size.stats)}>
                      {user.reputationScore?.toFixed(1) || '5.0'}
                    </span>
                  </div>
                  <p className="text-xs text-gray-500">({user.reputationCount})</p>
                </div>
              </div>

              {/* Badges */}
              {user.badges.length > 0 && (
                <div className="flex flex-wrap justify-center gap-1 mb-3">
                  {user.badges.slice(0, 3).map((badge) => (
                    <span
                      key={badge.key}
                      className="text-xs px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-400"
                      title={badge.name}
                    >
                      {badge.name}
                    </span>
                  ))}
                  {user.badges.length > 3 && (
                    <span className="text-xs text-gray-500">+{user.badges.length - 3}</span>
                  )}
                </div>
              )}

              {/* Formats */}
              {user.formats.length > 0 && (
                <div className="flex flex-wrap justify-center gap-1 mb-auto">
                  {user.formats.slice(0, 3).map((format) => (
                    <span
                      key={format}
                      className="text-xs px-2 py-0.5 rounded bg-gray-700/50 text-gray-400"
                    >
                      {format}
                    </span>
                  ))}
                </div>
              )}
            </div>

            {/* Action Buttons */}
            {showActions && (
              <div className="flex gap-2 mt-auto pt-3 border-t border-gray-700/50">
                {onMessage && (
                  <Button
                    variant="ghost"
                    size="sm"
                    className="flex-1 text-gray-400 hover:text-white hover:bg-gray-700"
                    onClick={(e) => handleAction(e, onMessage)}
                  >
                    <MessageCircle className="h-4 w-4 mr-1" />
                    Message
                  </Button>
                )}
                {onTrade && (
                  <Button
                    variant="ghost"
                    size="sm"
                    className="flex-1 text-amber-400 hover:text-amber-300 hover:bg-amber-500/20"
                    onClick={(e) => handleAction(e, onTrade)}
                  >
                    <Repeat2 className="h-4 w-4 mr-1" />
                    Trade
                  </Button>
                )}
                {onConnect && (
                  <Button
                    variant="ghost"
                    size="sm"
                    className="flex-1 text-blue-400 hover:text-blue-300 hover:bg-blue-500/20"
                    onClick={(e) => handleAction(e, onConnect)}
                  >
                    <UserPlus className="h-4 w-4 mr-1" />
                    Connect
                  </Button>
                )}
              </div>
            )}
          </div>

          {/* Back of Card */}
          <div
            className="absolute inset-0"
            style={{ backfaceVisibility: 'hidden', transform: 'rotateY(180deg)' }}
          >
            <ProfileCardBack
              username={user.username}
              displayName={user.displayName}
              badges={user.badges}
              tradeCount={user.tradeCount}
              formats={user.formats}
              memberSince={user.memberSince}
              variant={variant}
            />
          </div>
        </motion.div>
      </div>
    </FrameEffects>
  );
}

export default ProfileCard;
