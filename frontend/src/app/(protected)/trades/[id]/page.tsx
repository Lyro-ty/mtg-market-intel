'use client';

import { useParams, useRouter } from 'next/navigation';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  ArrowLeft,
  ArrowLeftRight,
  Loader2,
  AlertCircle,
  Clock,
  Calendar,
  CheckCircle,
  MessageSquare,
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { TradeStatusBadge } from '@/components/trades/TradeStatusBadge';
import { TradeItemCard } from '@/components/trades/TradeItemCard';
import {
  getTrade,
  acceptTrade,
  declineTrade,
  cancelTrade,
  confirmTrade,
  ApiError,
} from '@/lib/api';
import { formatCurrency, formatDate, formatRelativeTime } from '@/lib/utils';
import { useAuth } from '@/contexts/AuthContext';
import type { TradeProposal, TradeItem } from '@/types';

/**
 * Calculate total value of trade items
 */
function calculateTotalValue(
  items: Array<{ quantity: number; price_at_proposal: number | null }>
): number {
  return items.reduce((sum, item) => {
    const price = item.price_at_proposal ?? 0;
    return sum + price * item.quantity;
  }, 0);
}

/**
 * Get initials from username or display name
 */
function getInitials(username: string, displayName: string | null): string {
  const name = displayName ?? username;
  const parts = name.split(/[\s_-]+/);
  if (parts.length >= 2) {
    return (parts[0][0] + parts[1][0]).toUpperCase();
  }
  return name.slice(0, 2).toUpperCase();
}

/**
 * Format expiration status
 */
function getExpirationStatus(expiresAt: string): { text: string; isExpired: boolean; isUrgent: boolean } {
  const expDate = new Date(expiresAt);
  const now = new Date();
  const diffMs = expDate.getTime() - now.getTime();

  if (diffMs <= 0) {
    return { text: 'Expired', isExpired: true, isUrgent: false };
  }

  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
  const diffHours = Math.floor(diffMs / (1000 * 60 * 60));

  if (diffDays > 1) {
    return { text: `Expires in ${diffDays} days`, isExpired: false, isUrgent: false };
  }
  if (diffDays === 1) {
    return { text: 'Expires in 1 day', isExpired: false, isUrgent: true };
  }
  if (diffHours > 0) {
    return { text: `Expires in ${diffHours}h`, isExpired: false, isUrgent: true };
  }
  return { text: 'Expiring soon', isExpired: false, isUrgent: true };
}

/**
 * User display component with avatar
 */
function UserDisplay({
  user,
  isCurrentUser,
  side,
}: {
  user: { username: string; display_name: string | null };
  isCurrentUser: boolean;
  side: 'left' | 'right';
}) {
  const alignment = side === 'left' ? 'text-left' : 'text-right';
  const bgColor = side === 'left' ? 'bg-amber-500/20' : 'bg-blue-500/20';
  const textColor = side === 'left' ? 'text-amber-500' : 'text-blue-500';

  return (
    <div className={`flex flex-col items-center gap-2 ${alignment}`}>
      <Avatar className="h-16 w-16">
        <AvatarFallback className={`${bgColor} ${textColor} text-lg font-semibold`}>
          {getInitials(user.username, user.display_name)}
        </AvatarFallback>
      </Avatar>
      <div>
        <p className="text-sm font-medium text-[rgb(var(--foreground))]">
          {isCurrentUser ? 'You' : user.display_name ?? user.username}
        </p>
        {!isCurrentUser && user.display_name && (
          <p className="text-xs text-[rgb(var(--muted-foreground))]">@{user.username}</p>
        )}
      </div>
    </div>
  );
}

/**
 * Items column component
 */
function ItemsColumn({
  title,
  items,
  totalValue,
}: {
  title: string;
  items: TradeItem[];
  totalValue: number;
}) {
  return (
    <Card className="flex-1">
      <CardHeader className="py-3 px-4">
        <CardTitle className="text-sm font-medium">{title}</CardTitle>
      </CardHeader>
      <CardContent className="px-4 pb-4">
        {items.length === 0 ? (
          <div className="py-6 text-center text-sm text-[rgb(var(--muted-foreground))]">
            No items
          </div>
        ) : (
          <div className="space-y-2">
            {items.map((item) => (
              <TradeItemCard key={item.id} item={item} />
            ))}
          </div>
        )}
        <div className="mt-4 pt-3 border-t border-[rgb(var(--border))]">
          <div className="flex items-center justify-between">
            <span className="text-sm text-[rgb(var(--muted-foreground))]">Total Value</span>
            <span className="text-lg font-semibold text-[rgb(var(--foreground))]">
              {formatCurrency(totalValue)}
            </span>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

/**
 * Timeline item component
 */
function TimelineItem({
  icon: Icon,
  label,
  value,
  variant = 'default',
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: string;
  variant?: 'default' | 'urgent' | 'success';
}) {
  const variantClasses = {
    default: 'text-[rgb(var(--muted-foreground))]',
    urgent: 'text-amber-500',
    success: 'text-green-500',
  };

  return (
    <div className="flex items-center gap-2">
      <Icon className={`w-4 h-4 ${variantClasses[variant]}`} />
      <span className="text-sm">
        <span className="text-[rgb(var(--muted-foreground))]">{label}: </span>
        <span className={variantClasses[variant]}>{value}</span>
      </span>
    </div>
  );
}

/**
 * Action panel component with dynamic buttons based on role and status
 */
function ActionPanel({
  trade,
  currentUserId,
  onAccept,
  onDecline,
  onCancel,
  onConfirm,
  onCounter,
  isLoading,
}: {
  trade: TradeProposal;
  currentUserId: number;
  onAccept: () => void;
  onDecline: () => void;
  onCancel: () => void;
  onConfirm: () => void;
  onCounter: () => void;
  isLoading: boolean;
}) {
  const isProposer = trade.proposer.id === currentUserId;
  const isRecipient = trade.recipient.id === currentUserId;

  // Determine which actions are available
  const showAcceptDecline = isRecipient && trade.status === 'pending';
  const showCounter = isRecipient && trade.status === 'pending';
  const showCancel = isProposer && trade.status === 'pending';
  const showConfirm =
    trade.status === 'accepted' &&
    ((isProposer && !trade.proposer_confirmed) ||
      (isRecipient && !trade.recipient_confirmed));

  // Show completed message
  if (trade.status === 'completed') {
    return (
      <Card className="bg-green-500/10 border-green-500/20">
        <CardContent className="py-4">
          <div className="flex items-center justify-center gap-2 text-green-500">
            <CheckCircle className="w-5 h-5" />
            <span className="font-medium">Trade Completed Successfully</span>
          </div>
          {/* Future: Leave Review button */}
        </CardContent>
      </Card>
    );
  }

  // Show confirmation status for accepted trades
  if (trade.status === 'accepted') {
    return (
      <Card>
        <CardContent className="py-4">
          <div className="space-y-4">
            <div className="text-center">
              <p className="text-sm text-[rgb(var(--muted-foreground))] mb-2">
                Confirmation Status
              </p>
              <div className="flex items-center justify-center gap-6">
                <div className="flex items-center gap-2">
                  <span
                    className={`w-3 h-3 rounded-full ${
                      trade.proposer_confirmed ? 'bg-green-500' : 'bg-amber-500'
                    }`}
                  />
                  <span className="text-sm">
                    {trade.proposer.display_name ?? trade.proposer.username}:{' '}
                    {trade.proposer_confirmed ? 'Confirmed' : 'Pending'}
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <span
                    className={`w-3 h-3 rounded-full ${
                      trade.recipient_confirmed ? 'bg-green-500' : 'bg-amber-500'
                    }`}
                  />
                  <span className="text-sm">
                    {trade.recipient.display_name ?? trade.recipient.username}:{' '}
                    {trade.recipient_confirmed ? 'Confirmed' : 'Pending'}
                  </span>
                </div>
              </div>
            </div>

            {showConfirm && (
              <div className="flex justify-center">
                <Button
                  onClick={onConfirm}
                  disabled={isLoading}
                  className="gradient-arcane text-white glow-accent"
                >
                  {isLoading ? (
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  ) : (
                    <CheckCircle className="w-4 h-4 mr-2" />
                  )}
                  Confirm Completion
                </Button>
              </div>
            )}
          </div>
        </CardContent>
      </Card>
    );
  }

  // No actions available
  if (!showAcceptDecline && !showCounter && !showCancel) {
    return null;
  }

  return (
    <Card>
      <CardContent className="py-4">
        <div className="flex flex-wrap items-center justify-center gap-3">
          {showAcceptDecline && (
            <>
              <Button
                onClick={onAccept}
                disabled={isLoading}
                className="gradient-arcane text-white glow-accent"
              >
                {isLoading ? (
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                ) : (
                  <CheckCircle className="w-4 h-4 mr-2" />
                )}
                Accept Trade
              </Button>
              <Button onClick={onDecline} disabled={isLoading} variant="destructive">
                Decline
              </Button>
            </>
          )}

          {showCounter && (
            <Button onClick={onCounter} disabled={isLoading} variant="secondary">
              <ArrowLeftRight className="w-4 h-4 mr-2" />
              Counter Proposal
            </Button>
          )}

          {showCancel && (
            <Button onClick={onCancel} disabled={isLoading} variant="destructive">
              Cancel Trade
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

export default function TradeDetailPage() {
  const params = useParams();
  const router = useRouter();
  const queryClient = useQueryClient();
  const { user } = useAuth();

  const tradeId = typeof params.id === 'string' ? parseInt(params.id, 10) : 0;

  // Fetch trade details
  const {
    data: trade,
    isLoading,
    error,
  } = useQuery<TradeProposal, ApiError>({
    queryKey: ['trade', tradeId],
    queryFn: () => getTrade(tradeId),
    enabled: tradeId > 0,
  });

  // Mutation handlers
  const handleMutationSuccess = () => {
    queryClient.invalidateQueries({ queryKey: ['trade', tradeId] });
    queryClient.invalidateQueries({ queryKey: ['trades'] });
    queryClient.invalidateQueries({ queryKey: ['tradeStats'] });
  };

  const acceptMutation = useMutation({
    mutationFn: () => acceptTrade(tradeId),
    onSuccess: handleMutationSuccess,
  });

  const declineMutation = useMutation({
    mutationFn: () => declineTrade(tradeId),
    onSuccess: handleMutationSuccess,
  });

  const cancelMutation = useMutation({
    mutationFn: () => cancelTrade(tradeId),
    onSuccess: handleMutationSuccess,
  });

  const confirmMutation = useMutation({
    mutationFn: () => confirmTrade(tradeId),
    onSuccess: handleMutationSuccess,
  });

  const isMutating =
    acceptMutation.isPending ||
    declineMutation.isPending ||
    cancelMutation.isPending ||
    confirmMutation.isPending;

  // Handle counter proposal (navigate to counter page - placeholder for now)
  const handleCounter = () => {
    // TODO: Navigate to counter proposal page or open modal
    alert('Counter proposal feature coming soon!');
  };

  // Loading state
  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Loader2 className="w-8 h-8 animate-spin text-[rgb(var(--accent))]" />
      </div>
    );
  }

  // Error state
  if (error || !trade) {
    return (
      <div className="space-y-6 animate-in">
        <button
          onClick={() => router.push('/trades')}
          className="flex items-center gap-2 text-sm text-[rgb(var(--muted-foreground))] hover:text-[rgb(var(--foreground))] transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to Trades
        </button>

        <Card className="bg-[rgb(var(--destructive))]/10 border-[rgb(var(--destructive))]/20">
          <CardContent className="py-8">
            <div className="flex flex-col items-center gap-4">
              <AlertCircle className="w-12 h-12 text-[rgb(var(--destructive))]" />
              <div className="text-center">
                <h2 className="text-lg font-semibold text-[rgb(var(--foreground))]">
                  Trade Not Found
                </h2>
                <p className="text-sm text-[rgb(var(--muted-foreground))] mt-1">
                  {error?.message || 'The trade you are looking for does not exist or you do not have access to it.'}
                </p>
              </div>
              <Button onClick={() => router.push('/trades')} variant="secondary">
                Return to Trades
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  const currentUserId = user?.id ?? 0;
  const isProposer = trade.proposer.id === currentUserId;

  // Calculate totals
  const proposerValue = calculateTotalValue(trade.proposer_items);
  const recipientValue = calculateTotalValue(trade.recipient_items);

  // Timeline info
  const expirationStatus = getExpirationStatus(trade.expires_at);

  return (
    <div className="space-y-6 animate-in">
      {/* Header Row */}
      <div className="flex items-center justify-between">
        <button
          onClick={() => router.push('/trades')}
          className="flex items-center gap-2 text-sm text-[rgb(var(--muted-foreground))] hover:text-[rgb(var(--foreground))] transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to Trades
        </button>

        <div className="flex items-center gap-3">
          <span className="text-sm text-[rgb(var(--muted-foreground))]">
            Trade #{trade.id}
          </span>
          <TradeStatusBadge status={trade.status} />
        </div>
      </div>

      {/* Participants Section */}
      <Card>
        <CardContent className="py-6">
          <div className="flex items-center justify-center gap-8 sm:gap-16">
            <UserDisplay
              user={trade.proposer}
              isCurrentUser={isProposer}
              side="left"
            />

            <div className="flex flex-col items-center">
              <ArrowLeftRight className="w-8 h-8 text-amber-500" />
              <span className="text-xs text-[rgb(var(--muted-foreground))] mt-1">
                trading
              </span>
            </div>

            <UserDisplay
              user={trade.recipient}
              isCurrentUser={!isProposer}
              side="right"
            />
          </div>
        </CardContent>
      </Card>

      {/* Items Columns */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <ItemsColumn
          title={`${isProposer ? 'You are' : trade.proposer.display_name ?? trade.proposer.username + ' is'} Offering`}
          items={trade.proposer_items}
          totalValue={proposerValue}
        />
        <ItemsColumn
          title={`${isProposer ? trade.recipient.display_name ?? trade.recipient.username + ' is' : 'You are'} Offering`}
          items={trade.recipient_items}
          totalValue={recipientValue}
        />
      </div>

      {/* Message Section */}
      {trade.message && (
        <Card>
          <CardContent className="py-4">
            <div className="flex items-start gap-3">
              <MessageSquare className="w-5 h-5 text-[rgb(var(--muted-foreground))] shrink-0 mt-0.5" />
              <div>
                <p className="text-sm text-[rgb(var(--muted-foreground))] mb-1">Message</p>
                <p className="text-[rgb(var(--foreground))]">{trade.message}</p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Timeline Section */}
      <Card>
        <CardContent className="py-4">
          <div className="flex flex-wrap items-center justify-center gap-6 sm:gap-10">
            <TimelineItem
              icon={Calendar}
              label="Created"
              value={formatDate(trade.created_at)}
            />
            {trade.status !== 'completed' && trade.status !== 'cancelled' && trade.status !== 'expired' && (
              <TimelineItem
                icon={Clock}
                label="Expires"
                value={expirationStatus.text}
                variant={expirationStatus.isUrgent ? 'urgent' : 'default'}
              />
            )}
            {trade.completed_at && (
              <TimelineItem
                icon={CheckCircle}
                label="Completed"
                value={formatDate(trade.completed_at)}
                variant="success"
              />
            )}
            {trade.parent_proposal_id && (
              <TimelineItem
                icon={ArrowLeftRight}
                label="Counter to"
                value={`Trade #${trade.parent_proposal_id}`}
              />
            )}
          </div>
        </CardContent>
      </Card>

      {/* Action Panel */}
      <ActionPanel
        trade={trade}
        currentUserId={currentUserId}
        onAccept={() => acceptMutation.mutate()}
        onDecline={() => declineMutation.mutate()}
        onCancel={() => cancelMutation.mutate()}
        onConfirm={() => confirmMutation.mutate()}
        onCounter={handleCounter}
        isLoading={isMutating}
      />

      {/* Mutation Error Display */}
      {(acceptMutation.error ||
        declineMutation.error ||
        cancelMutation.error ||
        confirmMutation.error) && (
        <Card className="bg-[rgb(var(--destructive))]/10 border-[rgb(var(--destructive))]/20">
          <CardContent className="py-4">
            <div className="flex items-center gap-2 text-[rgb(var(--destructive))]">
              <AlertCircle className="w-5 h-5" />
              <p>
                {(acceptMutation.error ||
                  declineMutation.error ||
                  cancelMutation.error ||
                  confirmMutation.error)?.message || 'An error occurred'}
              </p>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
