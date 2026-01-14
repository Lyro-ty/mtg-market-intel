import { ArrowLeftRight, Clock, Eye } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { TradeStatusBadge } from './TradeStatusBadge';
import { formatCurrency, formatRelativeTime } from '@/lib/utils';
import type { TradeProposal } from '@/types';

interface TradeProposalCardProps {
  proposal: TradeProposal;
  currentUserId: number;
  onViewDetails?: () => void;
}

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
 * Calculate total item count
 */
function calculateItemCount(items: Array<{ quantity: number }>): number {
  return items.reduce((sum, item) => sum + item.quantity, 0);
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
 * Format expiration time - shows relative time for future dates
 */
function formatExpiration(expiresAt: string): string {
  const expDate = new Date(expiresAt);
  const now = new Date();
  const diffMs = expDate.getTime() - now.getTime();

  if (diffMs <= 0) {
    return 'Expired';
  }

  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
  const diffHours = Math.floor(diffMs / (1000 * 60 * 60));

  if (diffDays > 0) {
    return `${diffDays}d left`;
  }
  if (diffHours > 0) {
    return `${diffHours}h left`;
  }
  return 'Expiring soon';
}

/**
 * Summary card for displaying a trade proposal in list views.
 * Shows proposer/recipient info, item counts, values, status, and quick actions.
 */
export function TradeProposalCard({
  proposal,
  currentUserId,
  onViewDetails,
}: TradeProposalCardProps) {
  const isProposer = proposal.proposer.id === currentUserId;

  // Calculate values and counts
  const proposerItemCount = calculateItemCount(proposal.proposer_items);
  const recipientItemCount = calculateItemCount(proposal.recipient_items);
  const proposerValue = calculateTotalValue(proposal.proposer_items);
  const recipientValue = calculateTotalValue(proposal.recipient_items);

  // Display order: current user's items on left, other party on right
  const leftUser = isProposer ? proposal.proposer : proposal.recipient;
  const rightUser = isProposer ? proposal.recipient : proposal.proposer;
  const leftItemCount = isProposer ? proposerItemCount : recipientItemCount;
  const rightItemCount = isProposer ? recipientItemCount : proposerItemCount;
  const leftValue = isProposer ? proposerValue : recipientValue;
  const rightValue = isProposer ? recipientValue : proposerValue;

  const isExpired = proposal.status === 'expired';
  const isCompleted = proposal.status === 'completed';

  return (
    <Card
      interactive
      className="overflow-hidden"
      onClick={onViewDetails}
    >
      <CardContent className="p-4">
        {/* Trade Parties Row */}
        <div className="flex items-center justify-between gap-2 mb-3">
          {/* Left User (Current User) */}
          <div className="flex items-center gap-2 min-w-0 flex-1">
            <Avatar className="h-8 w-8 shrink-0">
              <AvatarFallback className="bg-amber-500/20 text-amber-500 text-xs font-medium">
                {getInitials(leftUser.username, leftUser.display_name)}
              </AvatarFallback>
            </Avatar>
            <div className="min-w-0">
              <div className="text-sm font-medium text-[rgb(var(--foreground))] truncate">
                {isProposer ? 'You' : leftUser.display_name ?? leftUser.username}
              </div>
              <div className="text-xs text-[rgb(var(--muted-foreground))]">
                {leftItemCount} card{leftItemCount !== 1 ? 's' : ''}
              </div>
            </div>
          </div>

          {/* Exchange Icon */}
          <div className="shrink-0 px-2">
            <ArrowLeftRight className="w-5 h-5 text-amber-500" />
          </div>

          {/* Right User (Other Party) */}
          <div className="flex items-center gap-2 min-w-0 flex-1 justify-end">
            <div className="min-w-0 text-right">
              <div className="text-sm font-medium text-[rgb(var(--foreground))] truncate">
                {!isProposer ? 'You' : rightUser.display_name ?? rightUser.username}
              </div>
              <div className="text-xs text-[rgb(var(--muted-foreground))]">
                {rightItemCount} card{rightItemCount !== 1 ? 's' : ''}
              </div>
            </div>
            <Avatar className="h-8 w-8 shrink-0">
              <AvatarFallback className="bg-blue-500/20 text-blue-500 text-xs font-medium">
                {getInitials(rightUser.username, rightUser.display_name)}
              </AvatarFallback>
            </Avatar>
          </div>
        </div>

        {/* Value Comparison Row */}
        <div className="flex items-center justify-between gap-2 mb-3 px-1">
          <div className="text-sm font-semibold text-[rgb(var(--foreground))]">
            {formatCurrency(leftValue)}
          </div>
          <div className="flex-1 border-t border-dashed border-[rgb(var(--border))]" />
          <div className="text-sm font-semibold text-[rgb(var(--foreground))]">
            {formatCurrency(rightValue)}
          </div>
        </div>

        {/* Status and Actions Row */}
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-3">
            <TradeStatusBadge status={proposal.status} size="sm" />

            {/* Expiration/Completion Info */}
            {!isCompleted && !isExpired && (
              <div className="flex items-center gap-1 text-xs text-[rgb(var(--muted-foreground))]">
                <Clock className="w-3 h-3" />
                <span>{formatExpiration(proposal.expires_at)}</span>
              </div>
            )}
            {isCompleted && proposal.completed_at && (
              <div className="text-xs text-[rgb(var(--muted-foreground))]">
                Completed {formatRelativeTime(proposal.completed_at)}
              </div>
            )}
          </div>

          {/* View Details Button */}
          <Button
            variant="ghost"
            size="sm"
            className="gap-1.5"
            onClick={(e) => {
              e.stopPropagation();
              onViewDetails?.();
            }}
          >
            <Eye className="w-4 h-4" />
            <span className="hidden sm:inline">View Details</span>
          </Button>
        </div>

        {/* Message Preview (if present) */}
        {proposal.message && (
          <div className="mt-3 pt-3 border-t border-[rgb(var(--border))]">
            <p className="text-xs text-[rgb(var(--muted-foreground))] line-clamp-1 italic">
              "{proposal.message}"
            </p>
          </div>
        )}

        {/* Counter Proposal Indicator */}
        {proposal.parent_proposal_id && (
          <div className="mt-2 text-xs text-amber-500/80">
            Counter-proposal
          </div>
        )}
      </CardContent>
    </Card>
  );
}
