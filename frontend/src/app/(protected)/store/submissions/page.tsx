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
  FileText,
  AlertCircle,
  DollarSign,
  Package,
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
  DialogClose,
} from '@/components/ui/dialog';
import { PageHeader } from '@/components/ornate/page-header';
import { formatCurrency, cn } from '@/lib/utils';
import {
  getStoreSubmissions,
  acceptSubmission,
  counterSubmission,
  declineSubmission,
  ApiError,
} from '@/lib/api';
import type { StoreSubmission } from '@/lib/api/trading-posts';

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
    label: 'Countered',
    icon: MessageSquare,
    color: 'bg-[rgb(var(--accent))]/20 text-[rgb(var(--accent))] border-[rgb(var(--accent))]/30',
  },
  declined: {
    label: 'Declined',
    icon: XCircle,
    color: 'bg-[rgb(var(--destructive))]/20 text-[rgb(var(--destructive))] border-[rgb(var(--destructive))]/30',
  },
  user_accepted: {
    label: 'Deal Confirmed',
    icon: CheckCircle,
    color: 'bg-[rgb(var(--success))]/20 text-[rgb(var(--success))] border-[rgb(var(--success))]/30',
  },
  user_declined: {
    label: 'User Declined',
    icon: XCircle,
    color: 'bg-[rgb(var(--muted))]/20 text-muted-foreground border-border',
  },
};

interface CounterDialogProps {
  submission: StoreSubmission;
  onCounter: (amount: number, message?: string) => Promise<void>;
  isProcessing: boolean;
}

function CounterDialog({ submission, onCounter, isProcessing }: CounterDialogProps) {
  const [amount, setAmount] = useState(submission.offer_amount.toString());
  const [message, setMessage] = useState('');
  const [isOpen, setIsOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async () => {
    const counterAmount = parseFloat(amount);
    if (isNaN(counterAmount) || counterAmount <= 0) {
      setError('Please enter a valid amount');
      return;
    }

    setError(null);
    try {
      await onCounter(counterAmount, message || undefined);
      setIsOpen(false);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError('Failed to submit counter offer');
      }
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={setIsOpen}>
      <DialogTrigger asChild>
        <Button variant="outline" size="sm">
          <MessageSquare className="w-4 h-4 mr-1" />
          Counter
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Make Counter Offer</DialogTitle>
        </DialogHeader>
        <div className="space-y-4 pt-4">
          <div>
            <p className="text-sm text-muted-foreground mb-2">
              Quote: {submission.quote_name || `#${submission.quote_id}`}
            </p>
            <p className="text-sm">
              Market value:{' '}
              <span className="font-medium">
                {formatCurrency(submission.quote_total_value || 0)}
              </span>
            </p>
            <p className="text-sm">
              Original offer:{' '}
              <span className="font-medium">
                {formatCurrency(submission.offer_amount)}
              </span>
            </p>
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium text-foreground">
              Your Counter Offer ($)
            </label>
            <Input
              type="number"
              min="0.01"
              step="0.01"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
            />
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium text-foreground">
              Message (optional)
            </label>
            <textarea
              className="w-full px-3 py-2 rounded-lg border border-border bg-card text-foreground min-h-[80px]"
              placeholder="Explain your offer..."
              value={message}
              onChange={(e) => setMessage(e.target.value)}
            />
          </div>

          {error && (
            <p className="text-sm text-[rgb(var(--destructive))]">{error}</p>
          )}

          <div className="flex justify-end gap-2 pt-2">
            <DialogClose asChild>
              <Button variant="secondary">Cancel</Button>
            </DialogClose>
            <Button
              className="gradient-arcane text-white"
              onClick={handleSubmit}
              disabled={isProcessing}
            >
              {isProcessing ? (
                <>
                  <Loader2 className="w-4 h-4 mr-1 animate-spin" />
                  Sending...
                </>
              ) : (
                'Send Counter'
              )}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

interface SubmissionCardProps {
  submission: StoreSubmission;
  onAccept: (id: number) => Promise<void>;
  onCounter: (id: number, amount: number, message?: string) => Promise<void>;
  onDecline: (id: number) => Promise<void>;
  isProcessing: boolean;
}

function SubmissionCard({
  submission,
  onAccept,
  onCounter,
  onDecline,
  isProcessing,
}: SubmissionCardProps) {
  const status = statusConfig[submission.status] || statusConfig.pending;
  const StatusIcon = status.icon;
  const isPending = submission.status === 'pending';

  return (
    <Card
      className={cn(
        'glow-accent transition-all',
        isPending && 'border-[rgb(var(--warning))]/50'
      )}
    >
      <CardContent className="p-4">
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1">
            <div className="flex items-center gap-2 mb-2">
              <FileText className="w-4 h-4 text-muted-foreground" />
              <h3 className="font-heading font-medium">
                {submission.quote_name || `Quote #${submission.quote_id}`}
              </h3>
              <Badge className={status.color}>
                <StatusIcon className="w-3 h-3 mr-1" />
                {status.label}
              </Badge>
            </div>

            <div className="grid grid-cols-3 gap-4 mt-3">
              <div>
                <p className="text-xs text-muted-foreground">Cards</p>
                <p className="font-medium flex items-center gap-1">
                  <Package className="w-4 h-4" />
                  {submission.quote_item_count}
                </p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Market Value</p>
                <p className="font-medium">
                  {formatCurrency(submission.quote_total_value || 0)}
                </p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Your Offer</p>
                <p className="font-medium text-[rgb(var(--success))]">
                  {formatCurrency(submission.offer_amount)}
                </p>
              </div>
            </div>

            {submission.user_message && (
              <div className="mt-3 p-2 rounded bg-secondary">
                <p className="text-sm text-muted-foreground">
                  <MessageSquare className="w-3 h-3 inline mr-1" />
                  Customer: &quot;{submission.user_message}&quot;
                </p>
              </div>
            )}

            {submission.counter_amount && (
              <div className="mt-3 p-2 rounded bg-[rgb(var(--accent))]/10 border border-[rgb(var(--accent))]/20">
                <p className="text-sm">
                  Your counter:{' '}
                  <span className="font-medium text-[rgb(var(--accent))]">
                    {formatCurrency(submission.counter_amount)}
                  </span>
                  {submission.store_message && (
                    <span className="text-muted-foreground">
                      {' - '}&quot;{submission.store_message}&quot;
                    </span>
                  )}
                </p>
              </div>
            )}

            <p className="text-xs text-muted-foreground mt-2">
              Submitted {new Date(submission.submitted_at).toLocaleDateString()}
              {submission.responded_at && (
                <>
                  {' - '}
                  Responded {new Date(submission.responded_at).toLocaleDateString()}
                </>
              )}
            </p>
          </div>

          {isPending && (
            <div className="flex flex-col gap-2">
              <Button
                size="sm"
                className="gradient-arcane text-white"
                onClick={() => onAccept(submission.id)}
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
              <CounterDialog
                submission={submission}
                onCounter={(amount, message) =>
                  onCounter(submission.id, amount, message)
                }
                isProcessing={isProcessing}
              />
              <Button
                size="sm"
                variant="outline"
                className="text-[rgb(var(--destructive))] hover:bg-[rgb(var(--destructive))]/10"
                onClick={() => onDecline(submission.id)}
                disabled={isProcessing}
              >
                <XCircle className="w-4 h-4 mr-1" />
                Decline
              </Button>
            </div>
          )}

          {submission.status === 'user_accepted' && (
            <div className="text-right">
              <p className="text-2xl font-bold text-[rgb(var(--success))]">
                {formatCurrency(submission.counter_amount || submission.offer_amount)}
              </p>
              <p className="text-xs text-muted-foreground">Deal confirmed!</p>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

export default function StoreSubmissionsPage() {
  const router = useRouter();
  const [submissions, setSubmissions] = useState<StoreSubmission[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [processingId, setProcessingId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [filterStatus, setFilterStatus] = useState<string>('all');

  const fetchSubmissions = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      const response = await getStoreSubmissions(
        filterStatus === 'all' ? undefined : filterStatus
      );
      setSubmissions(response.items);
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.status === 403) {
          router.push('/store/register');
          return;
        }
        setError(err.message);
      } else {
        setError('Failed to load submissions');
      }
    } finally {
      setIsLoading(false);
    }
  }, [filterStatus, router]);

  useEffect(() => {
    fetchSubmissions();
  }, [fetchSubmissions]);

  const handleAccept = async (id: number) => {
    setProcessingId(id);
    try {
      await acceptSubmission(id);
      await fetchSubmissions();
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError('Failed to accept submission');
      }
    } finally {
      setProcessingId(null);
    }
  };

  const handleCounter = async (id: number, amount: number, message?: string) => {
    setProcessingId(id);
    try {
      await counterSubmission(id, { counter_amount: amount, message });
      await fetchSubmissions();
    } catch (err) {
      throw err;
    } finally {
      setProcessingId(null);
    }
  };

  const handleDecline = async (id: number) => {
    if (!confirm('Are you sure you want to decline this quote?')) return;

    setProcessingId(id);
    try {
      await declineSubmission(id);
      await fetchSubmissions();
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError('Failed to decline submission');
      }
    } finally {
      setProcessingId(null);
    }
  };

  // Count by status
  const pendingCount = submissions.filter((s) => s.status === 'pending').length;
  const acceptedCount = submissions.filter(
    (s) => s.status === 'accepted' || s.status === 'user_accepted'
  ).length;

  // Calculate total pending value
  const pendingValue = submissions
    .filter((s) => s.status === 'pending')
    .reduce((sum, s) => sum + s.offer_amount, 0);

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
        <Button variant="ghost" onClick={() => router.push('/store')}>
          <ArrowLeft className="w-4 h-4 mr-2" />
          Back
        </Button>
        <PageHeader
          title="Incoming Quotes"
          subtitle="Review and respond to trade-in quote submissions"
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

      {/* Stats */}
      <div className="grid grid-cols-3 gap-4">
        <Card className="glow-accent">
          <CardContent className="p-4 text-center">
            <p className="text-3xl font-bold text-[rgb(var(--warning))]">
              {pendingCount}
            </p>
            <p className="text-sm text-muted-foreground">Pending Review</p>
          </CardContent>
        </Card>
        <Card className="glow-accent">
          <CardContent className="p-4 text-center">
            <p className="text-3xl font-bold text-[rgb(var(--success))]">
              {formatCurrency(pendingValue)}
            </p>
            <p className="text-sm text-muted-foreground">Pending Value</p>
          </CardContent>
        </Card>
        <Card className="glow-accent">
          <CardContent className="p-4 text-center">
            <p className="text-3xl font-bold text-foreground">{acceptedCount}</p>
            <p className="text-sm text-muted-foreground">Deals Made</p>
          </CardContent>
        </Card>
      </div>

      {/* Pending Alert */}
      {pendingCount > 0 && (
        <Card className="border-[rgb(var(--warning))]/50 bg-[rgb(var(--warning))]/5">
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <DollarSign className="w-5 h-5 text-[rgb(var(--warning))]" />
              <div>
                <h3 className="font-medium text-[rgb(var(--warning))]">
                  {pendingCount} quote{pendingCount !== 1 ? 's' : ''} awaiting
                  your response
                </h3>
                <p className="text-sm text-muted-foreground">
                  Review and accept, counter, or decline each submission.
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
          ['all', 'pending', 'accepted', 'countered', 'declined'] as const
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
            <FileText className="w-12 h-12 mx-auto text-muted-foreground mb-4" />
            <p className="text-muted-foreground">
              {filterStatus === 'all'
                ? 'No submissions yet. They\'ll appear here when customers submit quotes.'
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
              onAccept={handleAccept}
              onCounter={handleCounter}
              onDecline={handleDecline}
              isProcessing={processingId === submission.id}
            />
          ))}
        </div>
      )}
    </div>
  );
}
