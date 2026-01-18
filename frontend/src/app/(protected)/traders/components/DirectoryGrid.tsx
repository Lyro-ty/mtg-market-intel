'use client';

import { useMemo } from 'react';
import { useRouter } from 'next/navigation';
import { Users, UserX, Heart, ChevronLeft, ChevronRight } from 'lucide-react';
import { ProfileCard, type ProfileCardUser } from '@/components/social/ProfileCard';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';
import type { DirectoryUser } from '@/lib/api/directory';
import type { FrameTier } from '@/components/social/FrameEffects';

interface DirectoryGridProps {
  users: DirectoryUser[];
  total: number;
  isLoading: boolean;
  viewMode: 'grid' | 'list';
  page: number;
  pageSize?: number;
  onPageChange: (page: number) => void;
  favoriteIds?: Set<number>;
  onToggleFavorite?: (userId: number) => void;
  className?: string;
}

// Convert DirectoryUser to ProfileCardUser
function toProfileCardUser(user: DirectoryUser): ProfileCardUser {
  return {
    id: user.id,
    username: user.username,
    displayName: user.display_name || undefined,
    avatarUrl: user.avatar_url || undefined,
    tagline: user.tagline || undefined,
    cardType: user.card_type as ProfileCardUser['cardType'],
    tradeCount: user.trade_count,
    reputationScore: user.reputation_score || undefined,
    reputationCount: user.reputation_count,
    frameTier: (user.frame_tier || 'bronze') as FrameTier,
    isOnline: user.is_online,
    badges: user.badges || [],
    formats: user.formats || [],
    memberSince: user.member_since,
    hashid: '', // We'll generate links using the id directly
  };
}

export function DirectoryGrid({
  users,
  total,
  isLoading,
  viewMode,
  page,
  pageSize = 20,
  onPageChange,
  favoriteIds = new Set(),
  onToggleFavorite,
  className,
}: DirectoryGridProps) {
  const router = useRouter();

  // Calculate pagination
  const totalPages = Math.ceil(total / pageSize);
  const startItem = page * pageSize + 1;
  const endItem = Math.min((page + 1) * pageSize, total);

  // Transform users to ProfileCardUser format
  const profileUsers = useMemo(
    () => users.map(toProfileCardUser),
    [users]
  );

  // Handle user click - navigate to profile
  const handleUserClick = (userId: number) => {
    // Find the user to get their username for the profile URL
    const user = users.find((u) => u.id === userId);
    if (user) {
      // TODO: Use hashid when available, for now use username
      router.push(`/u/${user.username}`);
    }
  };

  // Handle message action
  const handleMessage = (userId: number) => {
    router.push(`/messages?user=${userId}`);
  };

  // Handle trade action
  const handleTrade = (userId: number) => {
    router.push(`/trades/new?recipient=${userId}`);
  };

  // Handle connect action
  const handleConnect = (userId: number) => {
    // This would trigger a connection request
    // For now, navigate to the user's profile
    handleUserClick(userId);
  };

  // Loading skeleton
  if (isLoading) {
    return (
      <div className={cn('space-y-6', className)}>
        <div
          className={cn(
            viewMode === 'grid'
              ? 'grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6'
              : 'space-y-4'
          )}
        >
          {Array.from({ length: 8 }).map((_, i) => (
            <ProfileCardSkeleton key={i} variant={viewMode === 'grid' ? 'standard' : 'compact'} />
          ))}
        </div>
      </div>
    );
  }

  // Empty state
  if (users.length === 0) {
    return (
      <div className={cn('flex flex-col items-center justify-center py-16', className)}>
        <div className="w-16 h-16 rounded-full bg-muted flex items-center justify-center mb-4">
          <UserX className="h-8 w-8 text-muted-foreground" />
        </div>
        <h3 className="text-lg font-semibold text-foreground mb-2">No Traders Found</h3>
        <p className="text-muted-foreground text-center max-w-md">
          Try adjusting your search filters or check back later as more traders join the community.
        </p>
      </div>
    );
  }

  return (
    <div className={cn('space-y-6', className)}>
      {/* Results count */}
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">
          <Users className="inline-block h-4 w-4 mr-1" />
          Showing {startItem}-{endItem} of {total} traders
        </p>
      </div>

      {/* Grid / List */}
      <div
        className={cn(
          viewMode === 'grid'
            ? 'grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6'
            : 'space-y-4'
        )}
      >
        {profileUsers.map((user, index) => (
          <div key={user.id} className="relative group">
            {/* Favorite button overlay */}
            {onToggleFavorite && (
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  onToggleFavorite(user.id);
                }}
                className={cn(
                  'absolute top-2 right-2 z-10 p-1.5 rounded-full transition-all',
                  'opacity-0 group-hover:opacity-100',
                  favoriteIds.has(user.id)
                    ? 'bg-red-500/20 text-red-500'
                    : 'bg-black/50 text-white hover:bg-black/70'
                )}
                aria-label={
                  favoriteIds.has(user.id)
                    ? 'Remove from favorites'
                    : 'Add to favorites'
                }
              >
                <Heart
                  className={cn(
                    'h-4 w-4',
                    favoriteIds.has(user.id) && 'fill-current'
                  )}
                />
              </button>
            )}

            <ProfileCard
              user={user}
              variant={viewMode === 'grid' ? 'standard' : 'compact'}
              showActions={viewMode === 'grid'}
              onMessage={() => handleMessage(users[index].id)}
              onTrade={() => handleTrade(users[index].id)}
              onConnect={() => handleConnect(users[index].id)}
              className={cn(
                'cursor-pointer transition-transform hover:scale-[1.02]',
                viewMode === 'list' && 'w-full'
              )}
            />
          </div>
        ))}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => onPageChange(page - 1)}
            disabled={page === 0}
          >
            <ChevronLeft className="h-4 w-4 mr-1" />
            Previous
          </Button>

          <div className="flex items-center gap-1">
            {/* Page numbers */}
            {generatePageNumbers(page, totalPages).map((pageNum, idx) =>
              pageNum === '...' ? (
                <span key={`ellipsis-${idx}`} className="px-2 text-muted-foreground">
                  ...
                </span>
              ) : (
                <Button
                  key={pageNum}
                  variant={page === pageNum ? 'default' : 'outline'}
                  size="sm"
                  onClick={() => onPageChange(pageNum as number)}
                  className={cn(
                    'min-w-[36px]',
                    page === pageNum &&
                      'bg-[rgb(var(--accent))] hover:bg-[rgb(var(--accent))]/90'
                  )}
                >
                  {(pageNum as number) + 1}
                </Button>
              )
            )}
          </div>

          <Button
            variant="outline"
            size="sm"
            onClick={() => onPageChange(page + 1)}
            disabled={page >= totalPages - 1}
          >
            Next
            <ChevronRight className="h-4 w-4 ml-1" />
          </Button>
        </div>
      )}
    </div>
  );
}

// Generate page numbers with ellipsis
function generatePageNumbers(
  currentPage: number,
  totalPages: number
): (number | '...')[] {
  if (totalPages <= 7) {
    return Array.from({ length: totalPages }, (_, i) => i);
  }

  const pages: (number | '...')[] = [];

  // Always show first page
  pages.push(0);

  if (currentPage > 3) {
    pages.push('...');
  }

  // Show pages around current
  const start = Math.max(1, currentPage - 1);
  const end = Math.min(totalPages - 2, currentPage + 1);

  for (let i = start; i <= end; i++) {
    if (!pages.includes(i)) {
      pages.push(i);
    }
  }

  if (currentPage < totalPages - 4) {
    pages.push('...');
  }

  // Always show last page
  if (!pages.includes(totalPages - 1)) {
    pages.push(totalPages - 1);
  }

  return pages;
}

// Profile Card Skeleton
interface ProfileCardSkeletonProps {
  variant?: 'standard' | 'compact';
}

function ProfileCardSkeleton({ variant = 'standard' }: ProfileCardSkeletonProps) {
  if (variant === 'compact') {
    return (
      <div className="flex items-center gap-3 p-3 bg-card border border-border rounded-lg">
        <Skeleton className="h-10 w-10 rounded-full" />
        <div className="flex-1 space-y-2">
          <Skeleton className="h-4 w-24" />
          <Skeleton className="h-3 w-16" />
        </div>
        <Skeleton className="h-6 w-16" />
      </div>
    );
  }

  return (
    <div className="w-64 h-80 bg-card border border-border rounded-lg p-4 space-y-4">
      <div className="flex justify-end">
        <Skeleton className="h-5 w-16 rounded-full" />
      </div>
      <div className="flex flex-col items-center">
        <Skeleton className="h-16 w-16 rounded-full" />
        <Skeleton className="h-5 w-24 mt-3" />
        <Skeleton className="h-3 w-16 mt-1" />
        <Skeleton className="h-4 w-32 mt-3" />
      </div>
      <div className="flex justify-center gap-4">
        <div className="text-center">
          <Skeleton className="h-4 w-8" />
          <Skeleton className="h-3 w-10 mt-1" />
        </div>
        <div className="text-center">
          <Skeleton className="h-4 w-8" />
          <Skeleton className="h-3 w-10 mt-1" />
        </div>
      </div>
      <div className="flex flex-wrap justify-center gap-1">
        <Skeleton className="h-5 w-14 rounded-full" />
        <Skeleton className="h-5 w-14 rounded-full" />
        <Skeleton className="h-5 w-14 rounded-full" />
      </div>
      <div className="flex gap-2 pt-3 border-t border-border">
        <Skeleton className="flex-1 h-8" />
        <Skeleton className="flex-1 h-8" />
      </div>
    </div>
  );
}

export default DirectoryGrid;
