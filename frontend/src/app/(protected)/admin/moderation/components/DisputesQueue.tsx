'use client';

import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Gavel,
  Clock,
  User,
  AlertCircle,
  Loader2,
  ChevronDown,
  ChevronUp,
  Package,
  Truck,
  HelpCircle,
  CheckCircle,
  RefreshCw,
  ArrowLeftRight,
  FileText,
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible';
import { Separator } from '@/components/ui/separator';
import { assignDispute, resolveDispute, ApiError } from '@/lib/api';
import { formatRelativeTime, formatCurrency, cn } from '@/lib/utils';
import type { TradeDisputeResponse, ResolveDisputeRequest } from '@/lib/api/moderation';

// =============================================================================
// Dispute Type Icon
// =============================================================================

interface DisputeTypeIconProps {
  type: string;
  className?: string;
}

function DisputeTypeIcon({ type, className }: DisputeTypeIconProps) {
  switch (type) {
    case 'item_not_as_described':
      return <Package className={cn('w-4 h-4', className)} />;
    case 'didnt_ship':
      return <Truck className={cn('w-4 h-4', className)} />;
    default:
      return <HelpCircle className={cn('w-4 h-4', className)} />;
  }
}

// =============================================================================
// Evidence Snapshot Display
// =============================================================================

interface EvidenceSnapshotProps {
  snapshot: Record<string, unknown> | null;
}

function EvidenceSnapshot({ snapshot }: EvidenceSnapshotProps) {
  if (!snapshot) {
    return (
      <p className="text-sm text-muted-foreground">No evidence snapshot available</p>
    );
  }

  const tradeData = snapshot as {
    trade_id?: number;
    proposer_username?: string;
    recipient_username?: string;
    status?: string;
    message?: string;
    created_at?: string;
    expires_at?: string;
    proposer_confirmed_at?: string;
    recipient_confirmed_at?: string;
    items?: Array<{
      card_name?: string;
      side?: string;
      quantity?: number;
      condition?: string;
      price_at_proposal?: number;
    }>;
    captured_at?: string;
  };

  const proposerItems = tradeData.items?.filter((i) => i.side === 'proposer') || [];
  const recipientItems = tradeData.items?.filter((i) => i.side === 'recipient') || [];

  return (
    <div className="space-y-3">
      {/* Trade Info */}
      <div className="grid grid-cols-2 gap-2 text-sm">
        <div>
          <span className="text-muted-foreground">Trade ID: </span>
          <span className="text-foreground">#{tradeData.trade_id}</span>
        </div>
        <div>
          <span className="text-muted-foreground">Status: </span>
          <Badge variant="secondary" className="ml-1">
            {tradeData.status}
          </Badge>
        </div>
        <div>
          <span className="text-muted-foreground">Proposer: </span>
          <span className="text-foreground">@{tradeData.proposer_username}</span>
        </div>
        <div>
          <span className="text-muted-foreground">Recipient: </span>
          <span className="text-foreground">@{tradeData.recipient_username}</span>
        </div>
      </div>

      {/* Message */}
      {tradeData.message && (
        <div>
          <p className="text-sm font-medium text-foreground">Trade Message</p>
          <p className="text-sm text-muted-foreground">{tradeData.message}</p>
        </div>
      )}

      {/* Items */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {/* Proposer Items */}
        <div className="p-2 rounded-lg bg-muted/30">
          <p className="text-xs font-medium text-muted-foreground mb-2">
            Proposer Offers ({proposerItems.length})
          </p>
          {proposerItems.length === 0 ? (
            <p className="text-xs text-muted-foreground">No items</p>
          ) : (
            <div className="space-y-1">
              {proposerItems.map((item, idx) => (
                <div key={idx} className="text-xs">
                  <span className="text-foreground">{item.quantity}x {item.card_name}</span>
                  {item.price_at_proposal && (
                    <span className="text-muted-foreground ml-1">
                      ({formatCurrency(item.price_at_proposal)})
                    </span>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Recipient Items */}
        <div className="p-2 rounded-lg bg-muted/30">
          <p className="text-xs font-medium text-muted-foreground mb-2">
            Recipient Offers ({recipientItems.length})
          </p>
          {recipientItems.length === 0 ? (
            <p className="text-xs text-muted-foreground">No items</p>
          ) : (
            <div className="space-y-1">
              {recipientItems.map((item, idx) => (
                <div key={idx} className="text-xs">
                  <span className="text-foreground">{item.quantity}x {item.card_name}</span>
                  {item.price_at_proposal && (
                    <span className="text-muted-foreground ml-1">
                      ({formatCurrency(item.price_at_proposal)})
                    </span>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Confirmations */}
      <div className="flex items-center gap-4 text-xs">
        <div className="flex items-center gap-1">
          {tradeData.proposer_confirmed_at ? (
            <CheckCircle className="w-3 h-3 text-[rgb(var(--success))]" />
          ) : (
            <Clock className="w-3 h-3 text-muted-foreground" />
          )}
          <span className={tradeData.proposer_confirmed_at ? 'text-[rgb(var(--success))]' : 'text-muted-foreground'}>
            Proposer {tradeData.proposer_confirmed_at ? 'confirmed' : 'not confirmed'}
          </span>
        </div>
        <div className="flex items-center gap-1">
          {tradeData.recipient_confirmed_at ? (
            <CheckCircle className="w-3 h-3 text-[rgb(var(--success))]" />
          ) : (
            <Clock className="w-3 h-3 text-muted-foreground" />
          )}
          <span className={tradeData.recipient_confirmed_at ? 'text-[rgb(var(--success))]' : 'text-muted-foreground'}>
            Recipient {tradeData.recipient_confirmed_at ? 'confirmed' : 'not confirmed'}
          </span>
        </div>
      </div>

      {/* Capture timestamp */}
      {tradeData.captured_at && (
        <p className="text-xs text-muted-foreground">
          Evidence captured {formatRelativeTime(tradeData.captured_at)}
        </p>
      )}
    </div>
  );
}

// =============================================================================
// Dispute Card Component
// =============================================================================

interface DisputeCardProps {
  dispute: TradeDisputeResponse;
  onResolve: (disputeId: number) => void;
  onAssign: (disputeId: number) => void;
}

function DisputeCard({ dispute, onResolve, onAssign }: DisputeCardProps) {
  const [isOpen, setIsOpen] = useState(false);

  const statusConfig: Record<string, { variant: 'secondary' | 'success' | 'warning'; label: string }> = {
    open: { variant: 'secondary', label: 'Open' },
    evidence_requested: { variant: 'warning', label: 'Evidence Requested' },
    resolved: { variant: 'success', label: 'Resolved' },
  };

  const typeLabels: Record<string, string> = {
    item_not_as_described: 'Item Not As Described',
    didnt_ship: 'Did Not Ship',
    other: 'Other',
  };

  const status = statusConfig[dispute.status] || statusConfig.open;

  return (
    <Collapsible open={isOpen} onOpenChange={setIsOpen}>
      <Card className="glow-accent">
        <CardContent className="p-4">
          <CollapsibleTrigger className="w-full text-left">
            <div className="flex items-start justify-between gap-3">
              <div className="flex items-center gap-3 min-w-0">
                <div className="p-2 rounded-full bg-muted/50">
                  <DisputeTypeIcon type={dispute.dispute_type} className="text-muted-foreground" />
                </div>
                <div className="min-w-0">
                  <p className="font-medium text-foreground">
                    {typeLabels[dispute.dispute_type] || dispute.dispute_type}
                  </p>
                  <p className="text-sm text-muted-foreground">
                    Filed by @{dispute.filer_username}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                <Badge variant={status.variant}>{status.label}</Badge>
                {isOpen ? (
                  <ChevronUp className="w-4 h-4 text-muted-foreground" />
                ) : (
                  <ChevronDown className="w-4 h-4 text-muted-foreground" />
                )}
              </div>
            </div>
          </CollapsibleTrigger>

          <CollapsibleContent className="pt-4 space-y-4">
            {/* Description */}
            {dispute.description && (
              <div>
                <p className="text-sm font-medium text-foreground mb-1">Description</p>
                <p className="text-sm text-muted-foreground">{dispute.description}</p>
              </div>
            )}

            <Separator />

            {/* Evidence Snapshot */}
            <div>
              <p className="text-sm font-medium text-foreground mb-2 flex items-center gap-2">
                <FileText className="w-4 h-4" />
                Trade Evidence
              </p>
              <EvidenceSnapshot snapshot={dispute.evidence_snapshot} />
            </div>

            {/* Resolution (if resolved) */}
            {dispute.resolution && (
              <>
                <Separator />
                <div className="p-3 rounded-lg bg-muted/30 border border-border/50">
                  <p className="text-sm font-medium text-foreground mb-1">Resolution</p>
                  <Badge variant="secondary" className="mb-2">
                    {dispute.resolution.replace('_', ' ')}
                  </Badge>
                  {dispute.resolution_notes && (
                    <p className="text-sm text-muted-foreground">{dispute.resolution_notes}</p>
                  )}
                  {dispute.resolved_at && (
                    <p className="text-xs text-muted-foreground mt-1">
                      Resolved {formatRelativeTime(dispute.resolved_at)}
                    </p>
                  )}
                </div>
              </>
            )}

            {/* Timestamps */}
            <div className="flex items-center gap-4 text-xs text-muted-foreground">
              <div className="flex items-center gap-1">
                <Clock className="w-3 h-3" />
                Filed {formatRelativeTime(dispute.created_at)}
              </div>
              {dispute.assigned_moderator_id && (
                <div className="flex items-center gap-1">
                  <User className="w-3 h-3" />
                  Assigned
                </div>
              )}
            </div>

            {/* Action Buttons */}
            {dispute.status !== 'resolved' && (
              <div className="flex gap-2">
                {!dispute.assigned_moderator_id && (
                  <Button
                    variant="outline"
                    onClick={() => onAssign(dispute.id)}
                    className="flex-1"
                  >
                    Assign to Me
                  </Button>
                )}
                <Button
                  onClick={() => onResolve(dispute.id)}
                  className="flex-1 gradient-arcane text-white"
                >
                  Resolve Dispute
                </Button>
              </div>
            )}
          </CollapsibleContent>
        </CardContent>
      </Card>
    </Collapsible>
  );
}

// =============================================================================
// Resolve Dispute Dialog
// =============================================================================

interface ResolveDisputeDialogProps {
  dispute: TradeDisputeResponse | null;
  onClose: () => void;
  onResolved: () => void;
}

function ResolveDisputeDialog({ dispute, onClose, onResolved }: ResolveDisputeDialogProps) {
  const [resolution, setResolution] = useState<ResolveDisputeRequest['resolution']>('mutual_cancel');
  const [notes, setNotes] = useState('');
  const queryClient = useQueryClient();

  const resolveMutation = useMutation({
    mutationFn: (request: ResolveDisputeRequest) =>
      resolveDispute(dispute!.id, request),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['moderation-disputes'] });
      setNotes('');
      onClose();
      onResolved();
    },
  });

  const handleSubmit = () => {
    resolveMutation.mutate({ resolution, notes });
  };

  const resolutionOptions: { value: ResolveDisputeRequest['resolution']; label: string; description: string }[] = [
    { value: 'buyer_wins', label: 'Buyer Wins', description: 'Buyer receives refund/items' },
    { value: 'seller_wins', label: 'Seller Wins', description: 'Seller keeps payment/items' },
    { value: 'mutual_cancel', label: 'Mutual Cancel', description: 'Both parties return to original state' },
    { value: 'inconclusive', label: 'Inconclusive', description: 'Insufficient evidence to decide' },
  ];

  return (
    <Dialog open={!!dispute} onOpenChange={() => onClose()}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Resolve Dispute</DialogTitle>
          <DialogDescription>
            Make a decision on this trade dispute. Your resolution will be final.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-4">
          {/* Dispute Summary */}
          {dispute && (
            <div className="p-3 rounded-lg bg-muted/30 border border-border/50">
              <p className="text-sm font-medium">
                Dispute #{dispute.id} - {dispute.dispute_type.replace('_', ' ')}
              </p>
              <p className="text-xs text-muted-foreground mt-1">
                Filed by @{dispute.filer_username}
              </p>
            </div>
          )}

          {/* Resolution Type */}
          <div className="space-y-2">
            <Label>Resolution</Label>
            <Select value={resolution} onValueChange={(v) => setResolution(v as typeof resolution)}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {resolutionOptions.map((opt) => (
                  <SelectItem key={opt.value} value={opt.value}>
                    <div>
                      <span className="font-medium">{opt.label}</span>
                      <span className="text-muted-foreground ml-2 text-xs">
                        - {opt.description}
                      </span>
                    </div>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Notes */}
          <div className="space-y-2">
            <Label>Resolution Notes</Label>
            <Textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Explain the reasoning for this resolution..."
              className="min-h-[100px]"
            />
          </div>

          {/* Error display */}
          {resolveMutation.isError && (
            <div className="p-3 rounded-lg bg-[rgb(var(--destructive))]/10 border border-[rgb(var(--destructive))]/20">
              <div className="flex items-center gap-2">
                <AlertCircle className="w-4 h-4 text-[rgb(var(--destructive))]" />
                <p className="text-sm text-[rgb(var(--destructive))]">
                  {resolveMutation.error?.message || 'Failed to resolve dispute'}
                </p>
              </div>
            </div>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button
            onClick={handleSubmit}
            disabled={!notes.trim() || resolveMutation.isPending}
            className="gradient-arcane text-white"
          >
            {resolveMutation.isPending ? (
              <>
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                Processing...
              </>
            ) : (
              'Submit Resolution'
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// =============================================================================
// Main Component
// =============================================================================

interface DisputesQueueProps {
  disputes: TradeDisputeResponse[];
  isLoading: boolean;
  error: ApiError | null;
  onRefresh: () => void;
}

export function DisputesQueue({ disputes, isLoading, error, onRefresh }: DisputesQueueProps) {
  const [selectedDispute, setSelectedDispute] = useState<TradeDisputeResponse | null>(null);
  const queryClient = useQueryClient();

  const assignMutation = useMutation({
    mutationFn: assignDispute,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['moderation-disputes'] });
      onRefresh();
    },
  });

  const handleResolve = (disputeId: number) => {
    const dispute = disputes.find((d) => d.id === disputeId);
    if (dispute) {
      setSelectedDispute(dispute);
    }
  };

  const handleAssign = (disputeId: number) => {
    assignMutation.mutate(disputeId);
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="w-8 h-8 animate-spin text-[rgb(var(--accent))]" />
      </div>
    );
  }

  if (error) {
    return (
      <Card className="glow-accent">
        <CardContent className="py-12 text-center">
          <AlertCircle className="w-12 h-12 mx-auto text-[rgb(var(--destructive))] mb-3" />
          <p className="text-[rgb(var(--destructive))] mb-4">
            {error.message || 'Failed to load disputes'}
          </p>
          <Button variant="outline" onClick={onRefresh}>
            <RefreshCw className="w-4 h-4 mr-2" />
            Retry
          </Button>
        </CardContent>
      </Card>
    );
  }

  if (disputes.length === 0) {
    return (
      <Card className="glow-accent">
        <CardContent className="py-12 text-center">
          <CheckCircle className="w-12 h-12 mx-auto text-[rgb(var(--success))] mb-3" />
          <p className="text-muted-foreground">No open disputes</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="font-medium text-foreground flex items-center gap-2">
          <Gavel className="w-5 h-5 text-[rgb(var(--accent))]" />
          Open Disputes ({disputes.length})
        </h3>
        <Button variant="outline" size="sm" onClick={onRefresh}>
          <RefreshCw className="w-4 h-4 mr-1" />
          Refresh
        </Button>
      </div>

      <div className="space-y-3">
        {disputes.map((dispute) => (
          <DisputeCard
            key={dispute.id}
            dispute={dispute}
            onResolve={handleResolve}
            onAssign={handleAssign}
          />
        ))}
      </div>

      {/* Resolve Dialog */}
      <ResolveDisputeDialog
        dispute={selectedDispute}
        onClose={() => setSelectedDispute(null)}
        onResolved={onRefresh}
      />
    </div>
  );
}
