'use client';

import React, { useState, useCallback, useEffect } from 'react';
import Link from 'next/link';
import { Loader2, Trophy, ArrowLeft, Users } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { PageHeader } from '@/components/ornate/page-header';
import { ReputationBadge } from '@/components/reputation/ReputationBadge';
import { StarRating } from '@/components/reputation/StarRating';
import { cn } from '@/lib/utils';
import { useAuth } from '@/contexts/AuthContext';
import { getReputationLeaderboard, ApiError } from '@/lib/api';
import type { LeaderboardEntry, LeaderboardResponse } from '@/types';

const MIN_REVIEWS_OPTIONS = [
  { value: '5', label: '5+ reviews' },
  { value: '10', label: '10+ reviews' },
  { value: '25', label: '25+ reviews' },
  { value: '50', label: '50+ reviews' },
];

// Medal icons for top 3 positions
function getMedalIcon(position: number): React.ReactNode {
  switch (position) {
    case 1:
      return <span className="text-xl" role="img" aria-label="First place">&#129351;</span>;
    case 2:
      return <span className="text-xl" role="img" aria-label="Second place">&#129352;</span>;
    case 3:
      return <span className="text-xl" role="img" aria-label="Third place">&#129353;</span>;
    default:
      return null;
  }
}

// Get initials for avatar fallback
function getInitials(displayName: string | null, username: string): string {
  const name = displayName || username;
  const parts = name.split(/[\s_-]+/);
  if (parts.length >= 2) {
    return (parts[0][0] + parts[1][0]).toUpperCase();
  }
  return name.slice(0, 2).toUpperCase();
}

export default function LeaderboardPage() {
  const { user } = useAuth();
  const [entries, setEntries] = useState<LeaderboardEntry[]>([]);
  const [minReviews, setMinReviews] = useState<string>('5');
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchLeaderboard = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data: LeaderboardResponse = await getReputationLeaderboard(50, parseInt(minReviews));
      setEntries(data.entries);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError('Failed to load leaderboard');
      }
    } finally {
      setIsLoading(false);
    }
  }, [minReviews]);

  useEffect(() => {
    fetchLeaderboard();
  }, [fetchLeaderboard]);

  const handleMinReviewsChange = (value: string) => {
    setMinReviews(value);
  };

  // Loading state
  if (isLoading && entries.length === 0) {
    return (
      <div className="space-y-6 animate-in">
        <PageHeader
          title="Reputation Leaderboard"
          subtitle="Top traders in our community."
        />
        <div className="flex items-center justify-center h-64">
          <Loader2 className="w-8 h-8 animate-spin text-[rgb(var(--accent))]" />
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-in">
      <PageHeader
        title="Reputation Leaderboard"
        subtitle="Top traders in our community."
      />

      {/* Filter controls */}
      <div className="flex flex-wrap items-center gap-4">
        <label className="text-sm text-muted-foreground">Min Reviews:</label>
        <Select value={minReviews} onValueChange={handleMinReviewsChange}>
          <SelectTrigger className="w-[140px]">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {MIN_REVIEWS_OPTIONS.map((option) => (
              <SelectItem key={option.value} value={option.value}>
                {option.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Error display */}
      {error && (
        <div className="p-4 rounded-lg bg-[rgb(var(--destructive))]/10 border border-[rgb(var(--destructive))]/20">
          <p className="text-[rgb(var(--destructive))]">{error}</p>
        </div>
      )}

      {/* Leaderboard table */}
      <Card className="glow-accent">
        <CardContent className="p-0">
          {isLoading ? (
            <div className="flex items-center justify-center h-32">
              <Loader2 className="w-6 h-6 animate-spin text-[rgb(var(--accent))]" />
            </div>
          ) : entries.length === 0 ? (
            <div className="text-center py-12">
              <Users className="w-12 h-12 mx-auto text-muted-foreground mb-3" />
              <p className="text-muted-foreground">No traders match the current filter</p>
              <p className="text-muted-foreground text-sm mt-1">
                Try lowering the minimum reviews requirement
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-border bg-muted/50">
                    <th className="px-4 py-3 text-left text-sm font-medium text-muted-foreground w-16">#</th>
                    <th className="px-4 py-3 text-left text-sm font-medium text-muted-foreground">User</th>
                    <th className="px-4 py-3 text-left text-sm font-medium text-muted-foreground">Rating</th>
                    <th className="px-4 py-3 text-center text-sm font-medium text-muted-foreground">Reviews</th>
                    <th className="px-4 py-3 text-right text-sm font-medium text-muted-foreground">Tier</th>
                  </tr>
                </thead>
                <tbody>
                  {entries.map((entry, index) => {
                    const position = index + 1;
                    const isCurrentUser = user && entry.user_id === user.id;
                    const displayName = entry.display_name || entry.username;

                    return (
                      <tr
                        key={entry.user_id}
                        className={cn(
                          'border-b border-border/50 transition-colors',
                          isCurrentUser
                            ? 'bg-[rgb(var(--accent))]/10 hover:bg-[rgb(var(--accent))]/15'
                            : 'hover:bg-muted/30',
                          position <= 3 && 'bg-amber-500/5'
                        )}
                      >
                        {/* Position */}
                        <td className="px-4 py-4">
                          <div className="flex items-center justify-center w-8">
                            {position <= 3 ? (
                              getMedalIcon(position)
                            ) : (
                              <span className="text-muted-foreground font-medium">{position}</span>
                            )}
                          </div>
                        </td>

                        {/* User info */}
                        <td className="px-4 py-4">
                          <div className="flex items-center gap-3">
                            <Avatar className="h-9 w-9">
                              <AvatarFallback className="bg-[rgb(var(--accent))]/20 text-[rgb(var(--accent))] text-sm">
                                {getInitials(entry.display_name, entry.username)}
                              </AvatarFallback>
                            </Avatar>
                            <div className="flex flex-col">
                              <span className={cn(
                                'font-medium',
                                isCurrentUser && 'text-[rgb(var(--accent))]'
                              )}>
                                {displayName}
                                {isCurrentUser && (
                                  <span className="ml-2 text-xs text-muted-foreground">(you)</span>
                                )}
                              </span>
                              {entry.display_name && (
                                <span className="text-xs text-muted-foreground">@{entry.username}</span>
                              )}
                            </div>
                          </div>
                        </td>

                        {/* Rating */}
                        <td className="px-4 py-4">
                          <div className="flex items-center gap-2">
                            <StarRating rating={entry.average_rating} size="sm" showValue />
                          </div>
                        </td>

                        {/* Reviews count */}
                        <td className="px-4 py-4 text-center">
                          <span className="text-foreground">{entry.total_reviews}</span>
                        </td>

                        {/* Tier badge */}
                        <td className="px-4 py-4 text-right">
                          <ReputationBadge tier={entry.tier} size="sm" showIcon />
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Back link */}
      <div className="flex justify-start">
        <Link href="/reputation">
          <Button variant="outline" className="gap-2">
            <ArrowLeft className="w-4 h-4" />
            Back to My Reputation
          </Button>
        </Link>
      </div>
    </div>
  );
}
