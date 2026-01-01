'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import {
  ArrowLeft,
  Loader2,
  Clock,
  CheckCircle,
  XCircle,
  MessageSquare,
  Store,
  AlertCircle,
  DollarSign,
  ArrowRight,
} from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { PageHeader } from '@/components/ornate/page-header';
import { formatCurrency, cn } from '@/lib/utils';
import {
  getMySubmissions,
  acceptCounterOffer,
  declineCounterOffer,
  ApiError,
} from '@/lib/api';
import type { QuoteSubmission } from '@/lib/api/quotes';

const statusConfig: Record<
  string,
  { label: string; icon: React.ElementType; color: string }
> = {
  pending: {
    label: 'Pending',
    icon: Clock,
    color: 'bg-[rgb(var(--warning))]/20 text-[rgb(var(--warning))] border-[rgb(var(--warning))]/30',
  },
  accepted: {
    label: 'Accepted',
    icon: CheckCircle,
    color: 'bg-[rgb(var(--success))]/20 text-[rgb(var(--success))] border-[rgb(var(--success))]/30',
  },
  countered: {
    label: 'Counter Offer',
    icon: MessageSquare,
    color: 'bg-[rgb(var(--accent))]/20 text-[rgb(var(--accent))] border-[rgb(var(--accent))]/30',
  },
  declined: {
    label: 'Declined',
    icon: XCircle,
    color: 'bg-[rgb(var(--destructive))]/20 text-[rgb(var(--destructive))] border-[rgb(var(--destructive))]/30',
  },
  user_accepted: {
    label: 'You Accepted',
    icon: CheckCircle,
    color: 'bg-[rgb(var(--success))]/20 text-[rgb(var(--success))] border-[rgb(var(--success))]/30',
  },
  user_declined: {
    label: 'You Declined',
    icon: XCircle,
    color: 'bg-[rgb(var(--muted))]/20 text-muted-foreground border-border',
  },
};

interface SubmissionCardProps {
  submission: QuoteSubmission;
  onAcceptCounter: (id: number) => Promise<void>;
  onDeclineCounter: (id: number) => Promise<void>;
  isProcessing: boolean;
}

function SubmissionCard({
  submission,
  onAcceptCounter,
  onDeclineCounter,
  isProcessing,
}: SubmissionCardProps) {
  const status = statusConfig[submission.status] || statusConfig.pending;
  const StatusIcon = status.icon;

  const hasCounter = submission.status === 'countered' && submission.counter_amount;

  return (
    <Card
      className={cn(
        'glow-accent transition-all',
        submission.status === 'countered' && 'border-[rgb(var(--accent))]/50'
      )}
    >
      <CardContent className="p-4">
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1">
            <div className="flex items-center gap-2 mb-2">
              <Store className="w-4 h-4 text-muted-foreground" />
              <h3 className="font-heading font-medium">
                {submission.trading_post?.store_name || 'Unknown Store'}
              </h3>
              <Badge className={status.color}>
                <StatusIcon className="w-3 h-3 mr-1" />
                {status.label}
              </Badge>
            </div>

            <p className="text-sm text-muted-foreground">
              {submission.quote_name || `Quote #${submission.quote_id}`}
              {' - '}
              {submission.quote_item_count} card
              {submission.quote_item_count !== 1 ? 's' : ''}
            </p>

            <div className="mt-3 flex items-center gap-4">
              <div>
                <p className="text-xs text-muted-foreground">Original Offer</p>
                <p className="font-medium">
                  {formatCurrency(submission.offer_amount)}
                </p>
              </div>

              {hasCounter && (
                <>
                  <ArrowRight className="w-4 h-4 text-muted-foreground" />
                  <div>
                    <p className="text-xs text-muted-foreground">Counter Offer</p>
                    <p className="font-medium text-[rgb(var(--accent))]">
                      {formatCurrency(submission.counter_amount!)}
                    </p>
                  </div>
                </>
              )}
            </div>

            {submission.store_message && (
              <div className="mt-3 p-2 rounded bg-secondary">
                <p className="text-sm text-muted-foreground">
                  <MessageSquare className="w-3 h-3 inline mr-1" />
                  &quot;{submission.store_message}&quot;
                </p>
              </div>
            )}

            <p className="text-xs text-muted-foreground mt-2">
              Submitted {new Date(submission.submitted_at).toLocaleDateString()}
              {submission.responded_at && (
                <> - Responded {new Date(submission.responded_at).toLocaleDateString()}</>
              )}
            </p>
          </div>

          {submission.status === 'countered' && (
            <div className="flex flex-col gap-2">
              <Button
                size="sm"
                className="gradient-arcane text-white"
                onClick={() => onAcceptCounter(submission.id)}
                disabled={isProcessing}
              >
                {isProcessing ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <>
                    <CheckCircle className="w-4 h-4 mr-1" />
                    Accept
                  </>
                )}
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={() => onDeclineCounter(submission.id)}
                disabled={isProcessing}
              >
                <XCircle className="w-4 h-4 mr-1" />
                Decline
              </Button>
            </div>
          )}

          {submission.status === 'accepted' && (
            <div className="text-right">
              <p className="text-2xl font-bold text-[rgb(var(--success))]">
                {formatCurrency(submission.offer_amount)}
              </p>
              <p className="text-xs text-muted-foreground">
                Contact store to complete trade
              </p>
            </div>
          )}

          {submission.status === 'user_accepted' && (
            <div className="text-right">
              <p className="text-2xl font-bold text-[rgb(var(--success))]">
                {formatCurrency(submission.counter_amount || submission.offer_amount)}
              </p>
              <p className="text-xs text-muted-foreground">Deal agreed!</p>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

export default function SubmissionsPage() {
  const router = useRouter();
  const [submissions, setSubmissions] = useState<QuoteSubmission[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [processingId, setProcessingId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [filterStatus, setFilterStatus] = useState<string>('all');

  const fetchSubmissions = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      const response = await getMySubmissions(
        filterStatus === 'all' ? undefined : filterStatus
      );
      setSubmissions(response.items);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError('Failed to load submissions');
      }
    } finally {
      setIsLoading(false);
    }
  }, [filterStatus]);

  useEffect(() => {
    fetchSubmissions();
  }, [fetchSubmissions]);

  const handleAcceptCounter = async (id: number) => {
    setProcessingId(id);
    try {
      await acceptCounterOffer(id);
      await fetchSubmissions();
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError('Failed to accept counter offer');
      }
    } finally {
      setProcessingId(null);
    }
  };

  const handleDeclineCounter = async (id: number) => {
    setProcessingId(id);
    try {
      await declineCounterOffer(id);
      await fetchSubmissions();
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError('Failed to decline counter offer');
      }
    } finally {
      setProcessingId(null);
    }
  };

  // Count by status
  const pendingCount = submissions.filter((s) => s.status === 'pending').length;
  const counterCount = submissions.filter((s) => s.status === 'countered').length;
  const acceptedCount = submissions.filter(
    (s) => s.status === 'accepted' || s.status === 'user_accepted'
  ).length;

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Loader2 className="w-8 h-8 animate-spin text-[rgb(var(--accent))]" />
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-in">
      <div className="flex items-center gap-4">
        <Button variant="ghost" onClick={() => router.push('/quotes')}>
          <ArrowLeft className="w-4 h-4 mr-2" />
          Back
        </Button>
        <PageHeader
          title="Quote Submissions"
          subtitle="Track responses from stores you've submitted quotes to"
        />
      </div>

      {error && (
        <div className="p-4 rounded-lg bg-[rgb(var(--destructive))]/10 border border-[rgb(var(--destructive))]/20">
          <div className="flex items-center gap-2">
            <AlertCircle className="w-5 h-5 text-[rgb(var(--destructive))]" />
            <p className="text-[rgb(var(--destructive))]">{error}</p>
          </div>
        </div>
      )}

      {/* Summary Stats */}
      <div className="grid grid-cols-4 gap-4">
        <Card className="glow-accent">
          <CardContent className="p-4 text-center">
            <p className="text-3xl font-bold text-foreground">
              {submissions.length}
            </p>
            <p className="text-sm text-muted-foreground">Total</p>
          </CardContent>
        </Card>
        <Card className="glow-accent">
          <CardContent className="p-4 text-center">
            <p className="text-3xl font-bold text-[rgb(var(--warning))]">
              {pendingCount}
            </p>
            <p className="text-sm text-muted-foreground">Pending</p>
          </CardContent>
        </Card>
        <Card className="glow-accent">
          <CardContent className="p-4 text-center">
            <p className="text-3xl font-bold text-[rgb(var(--accent))]">
              {counterCount}
            </p>
            <p className="text-sm text-muted-foreground">Counter Offers</p>
          </CardContent>
        </Card>
        <Card className="glow-accent">
          <CardContent className="p-4 text-center">
            <p className="text-3xl font-bold text-[rgb(var(--success))]">
              {acceptedCount}
            </p>
            <p className="text-sm text-muted-foreground">Accepted</p>
          </CardContent>
        </Card>
      </div>

      {/* Counter Offers Alert */}
      {counterCount > 0 && (
        <Card className="border-[rgb(var(--accent))]/50 bg-[rgb(var(--accent))]/5">
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <DollarSign className="w-5 h-5 text-[rgb(var(--accent))]" />
              <div>
                <h3 className="font-medium text-[rgb(var(--accent))]">
                  You have {counterCount} counter offer
                  {counterCount !== 1 ? 's' : ''} to review!
                </h3>
                <p className="text-sm text-muted-foreground">
                  Review and accept or decline the counter offers below.
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Filters */}
      <div className="flex items-center gap-2">
        <span className="text-sm text-muted-foreground">Status:</span>
        {(
          ['all', 'pending', 'countered', 'accepted', 'declined'] as const
        ).map((status) => (
          <Button
            key={status}
            variant={filterStatus === status ? 'default' : 'secondary'}
            size="sm"
            onClick={() => setFilterStatus(status)}
            className={
              filterStatus === status ? 'gradient-arcane text-white' : ''
            }
          >
            {status === 'all'
              ? 'All'
              : status.charAt(0).toUpperCase() + status.slice(1)}
          </Button>
        ))}
      </div>

      {/* Submissions List */}
      {submissions.length === 0 ? (
        <Card className="glow-accent">
          <CardContent className="py-12 text-center">
            <Store className="w-12 h-12 mx-auto text-muted-foreground mb-4" />
            <p className="text-muted-foreground">
              {filterStatus === 'all'
                ? 'No submissions yet. Submit a quote to stores to see responses here.'
                : `No ${filterStatus} submissions found.`}
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-3">
          {submissions.map((submission) => (
            <SubmissionCard
              key={submission.id}
              submission={submission}
              onAcceptCounter={handleAcceptCounter}
              onDeclineCounter={handleDeclineCounter}
              isProcessing={processingId === submission.id}
            />
          ))}
        </div>
      )}
    </div>
  );
}
