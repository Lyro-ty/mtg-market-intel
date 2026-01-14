'use client';

import React, { useState, useCallback, useEffect } from 'react';
import Link from 'next/link';
import {
  Loader2,
  Star,
  Clock,
  TrendingUp,
  MessageSquare,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { PageHeader } from '@/components/ornate/page-header';
import { ReputationBadge } from '@/components/reputation/ReputationBadge';
import { StarRating } from '@/components/reputation/StarRating';
import { RatingDistribution } from '@/components/reputation/RatingDistribution';
import { ReviewCard } from '@/components/reputation/ReviewCard';
import { cn, formatRelativeTime } from '@/lib/utils';
import { useAuth } from '@/contexts/AuthContext';
import {
  getMyReputation,
  getUserReviews,
  ApiError,
} from '@/lib/api';
import type { Reputation, Review, ReviewListResponse } from '@/types';

const REVIEWS_PER_PAGE = 5;

export default function ReputationPage() {
  const { user } = useAuth();
  const [reputation, setReputation] = useState<Reputation | null>(null);
  const [reviews, setReviews] = useState<Review[]>([]);
  const [totalReviews, setTotalReviews] = useState(0);
  const [currentPage, setCurrentPage] = useState(1);
  const [isLoadingReputation, setIsLoadingReputation] = useState(true);
  const [isLoadingReviews, setIsLoadingReviews] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const totalPages = Math.ceil(totalReviews / REVIEWS_PER_PAGE);

  const fetchReputation = useCallback(async () => {
    setIsLoadingReputation(true);
    setError(null);
    try {
      const data = await getMyReputation();
      setReputation(data);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError('Failed to load reputation data');
      }
    } finally {
      setIsLoadingReputation(false);
    }
  }, []);

  const fetchReviews = useCallback(async (page: number) => {
    if (!user) return;

    setIsLoadingReviews(true);
    try {
      const offset = (page - 1) * REVIEWS_PER_PAGE;
      const data: ReviewListResponse = await getUserReviews(
        user.id,
        REVIEWS_PER_PAGE,
        offset
      );
      setReviews(data.reviews);
      setTotalReviews(data.total);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError('Failed to load reviews');
      }
    } finally {
      setIsLoadingReviews(false);
    }
  }, [user]);

  useEffect(() => {
    fetchReputation();
  }, [fetchReputation]);

  useEffect(() => {
    if (user) {
      fetchReviews(currentPage);
    }
  }, [user, currentPage, fetchReviews]);

  const handlePreviousPage = () => {
    if (currentPage > 1) {
      setCurrentPage((prev) => prev - 1);
    }
  };

  const handleNextPage = () => {
    if (currentPage < totalPages) {
      setCurrentPage((prev) => prev + 1);
    }
  };

  // Loading state
  if (isLoadingReputation && !reputation) {
    return (
      <div className="space-y-6 animate-in">
        <PageHeader
          title="My Reputation"
          subtitle="Your trading reputation and community trust level."
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
        title="My Reputation"
        subtitle="Your trading reputation and community trust level."
      />

      {/* Error display */}
      {error && (
        <div className="p-4 rounded-lg bg-[rgb(var(--destructive))]/10 border border-[rgb(var(--destructive))]/20">
          <p className="text-[rgb(var(--destructive))]">{error}</p>
        </div>
      )}

      {reputation ? (
        <>
          {/* Main reputation summary card */}
          <Card className="glow-accent">
            <CardContent className="p-6">
              <div className="flex flex-col md:flex-row items-center gap-6">
                {/* Large reputation badge */}
                <div className="flex-shrink-0">
                  <ReputationBadge
                    tier={reputation.tier}
                    size="lg"
                    showIcon
                    className="text-lg px-4 py-2"
                  />
                </div>

                {/* Rating and reviews count */}
                <div className="flex flex-col items-center md:items-start gap-2">
                  <div className="flex items-center gap-3">
                    <StarRating
                      rating={reputation.average_rating}
                      size="lg"
                      showValue
                    />
                  </div>
                  <p className="text-muted-foreground text-sm">
                    Based on {reputation.total_reviews} review{reputation.total_reviews !== 1 ? 's' : ''}
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Stats grid */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Rating distribution */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-lg">
                  <TrendingUp className="w-5 h-5 text-[rgb(var(--accent))]" />
                  Rating Distribution
                </CardTitle>
              </CardHeader>
              <CardContent>
                <RatingDistribution reputation={reputation} />
              </CardContent>
            </Card>

            {/* Stats card */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-lg">
                  <Star className="w-5 h-5 text-amber-500" />
                  Stats
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <span className="text-muted-foreground">Total Reviews</span>
                    <span className="font-medium text-foreground">
                      {reputation.total_reviews}
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-muted-foreground">Average Rating</span>
                    <span className="font-medium text-foreground">
                      {reputation.average_rating.toFixed(1)} / 5.0
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-muted-foreground">Trust Tier</span>
                    <ReputationBadge tier={reputation.tier} size="sm" showIcon />
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-muted-foreground flex items-center gap-1">
                      <Clock className="w-4 h-4" />
                      Last Updated
                    </span>
                    <span className="text-foreground text-sm">
                      {formatRelativeTime(reputation.last_calculated_at)}
                    </span>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Recent reviews section */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-lg">
                <MessageSquare className="w-5 h-5 text-[rgb(var(--accent))]" />
                Recent Reviews
              </CardTitle>
            </CardHeader>
            <CardContent>
              {isLoadingReviews ? (
                <div className="flex items-center justify-center h-32">
                  <Loader2 className="w-6 h-6 animate-spin text-[rgb(var(--accent))]" />
                </div>
              ) : reviews.length === 0 ? (
                <div className="text-center py-8">
                  <MessageSquare className="w-12 h-12 mx-auto text-muted-foreground mb-3" />
                  <p className="text-muted-foreground">No reviews yet</p>
                  <p className="text-muted-foreground text-sm mt-1">
                    Complete trades to receive reviews from other traders
                  </p>
                </div>
              ) : (
                <div className="space-y-4">
                  {reviews.map((review) => (
                    <ReviewCard key={review.id} review={review} />
                  ))}
                </div>
              )}

              {/* Pagination */}
              {totalPages > 1 && (
                <div className="flex items-center justify-between mt-6 pt-4 border-t border-border">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handlePreviousPage}
                    disabled={currentPage === 1 || isLoadingReviews}
                  >
                    <ChevronLeft className="w-4 h-4 mr-1" />
                    Previous
                  </Button>
                  <span className="text-sm text-muted-foreground">
                    Page {currentPage} of {totalPages}
                  </span>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleNextPage}
                    disabled={currentPage === totalPages || isLoadingReviews}
                  >
                    Next
                    <ChevronRight className="w-4 h-4 ml-1" />
                  </Button>
                </div>
              )}

              {/* Link to leaderboard */}
              <div className="flex justify-end mt-6">
                <Link href="/reputation/leaderboard">
                  <Button variant="outline" className="gap-2">
                    <TrendingUp className="w-4 h-4" />
                    View Leaderboard
                  </Button>
                </Link>
              </div>
            </CardContent>
          </Card>
        </>
      ) : (
        /* Empty state when no reputation data */
        <Card className="glow-accent">
          <CardContent className="p-8 text-center">
            <Star className="w-16 h-16 mx-auto text-muted-foreground mb-4" />
            <h3 className="text-lg font-medium text-foreground mb-2">
              No Reputation Data Yet
            </h3>
            <p className="text-muted-foreground mb-4">
              Start trading to build your reputation in the community.
            </p>
            <Link href="/trades">
              <Button className="gradient-arcane text-white">
                Browse Trades
              </Button>
            </Link>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
