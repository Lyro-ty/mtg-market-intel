'use client';

import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import {
  MessageSquareWarning,
  Clock,
  User,
  AlertCircle,
  Loader2,
  ChevronDown,
  ChevronUp,
  ExternalLink,
  CheckCircle,
  XCircle,
  RefreshCw,
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
import { resolveAppeal, ApiError } from '@/lib/api';
import { formatRelativeTime, cn } from '@/lib/utils';
import type { AppealResponse, ResolveAppealRequest } from '@/lib/api/moderation';

// =============================================================================
// Appeal Card Component
// =============================================================================

interface AppealCardProps {
  appeal: AppealResponse;
  onResolve: (appealId: number) => void;
}

function AppealCard({ appeal, onResolve }: AppealCardProps) {
  const [isOpen, setIsOpen] = useState(false);

  const statusConfig: Record<string, { variant: 'secondary' | 'success' | 'destructive' | 'warning'; label: string }> = {
    pending: { variant: 'secondary', label: 'Pending' },
    upheld: { variant: 'destructive', label: 'Upheld' },
    reduced: { variant: 'warning', label: 'Reduced' },
    overturned: { variant: 'success', label: 'Overturned' },
  };

  const status = statusConfig[appeal.status] || statusConfig.pending;

  return (
    <Collapsible open={isOpen} onOpenChange={setIsOpen}>
      <Card className="glow-accent">
        <CardContent className="p-4">
          <CollapsibleTrigger className="w-full text-left">
            <div className="flex items-start justify-between gap-3">
              <div className="flex items-center gap-3 min-w-0">
                <div className="p-2 rounded-full bg-muted/50">
                  <User className="w-4 h-4 text-muted-foreground" />
                </div>
                <div className="min-w-0">
                  <p className="font-medium text-foreground">@{appeal.username}</p>
                  <p className="text-sm text-muted-foreground">
                    Appealing: <span className="capitalize">{appeal.moderation_action.action_type}</span>
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
            {/* Original Action */}
            <div className="p-3 rounded-lg bg-muted/30 border border-border/50">
              <p className="text-sm font-medium text-foreground mb-1">Original Action</p>
              <div className="text-sm text-muted-foreground space-y-1">
                <p>
                  <span className="font-medium">Type:</span>{' '}
                  <span className="capitalize">{appeal.moderation_action.action_type}</span>
                </p>
                {appeal.moderation_action.reason && (
                  <p>
                    <span className="font-medium">Reason:</span> {appeal.moderation_action.reason}
                  </p>
                )}
                {appeal.moderation_action.duration_days && (
                  <p>
                    <span className="font-medium">Duration:</span>{' '}
                    {appeal.moderation_action.duration_days} days
                  </p>
                )}
                <p>
                  <span className="font-medium">Date:</span>{' '}
                  {formatRelativeTime(appeal.moderation_action.created_at)}
                </p>
              </div>
            </div>

            {/* Appeal Text */}
            <div>
              <p className="text-sm font-medium text-foreground mb-1">Appeal Statement</p>
              <p className="text-sm text-muted-foreground">{appeal.appeal_text}</p>
            </div>

            {/* Evidence URLs */}
            {appeal.evidence_urls.length > 0 && (
              <div>
                <p className="text-sm font-medium text-foreground mb-1">Evidence</p>
                <div className="space-y-1">
                  {appeal.evidence_urls.map((url, idx) => (
                    <a
                      key={idx}
                      href={url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center gap-1 text-sm text-[rgb(var(--accent))] hover:underline"
                    >
                      <ExternalLink className="w-3 h-3" />
                      Evidence {idx + 1}
                    </a>
                  ))}
                </div>
              </div>
            )}

            {/* Resolution Notes (if resolved) */}
            {appeal.resolution_notes && (
              <div className="p-3 rounded-lg bg-muted/30 border border-border/50">
                <p className="text-sm font-medium text-foreground mb-1">Resolution</p>
                <p className="text-sm text-muted-foreground">{appeal.resolution_notes}</p>
                {appeal.resolved_at && (
                  <p className="text-xs text-muted-foreground mt-1">
                    Resolved {formatRelativeTime(appeal.resolved_at)}
                  </p>
                )}
              </div>
            )}

            {/* Timestamps */}
            <div className="flex items-center gap-4 text-xs text-muted-foreground">
              <div className="flex items-center gap-1">
                <Clock className="w-3 h-3" />
                Filed {formatRelativeTime(appeal.created_at)}
              </div>
            </div>

            {/* Action Button */}
            {appeal.status === 'pending' && (
              <Button
                onClick={() => onResolve(appeal.id)}
                className="w-full"
              >
                Resolve Appeal
              </Button>
            )}
          </CollapsibleContent>
        </CardContent>
      </Card>
    </Collapsible>
  );
}

// =============================================================================
// Resolve Appeal Dialog
// =============================================================================

interface ResolveAppealDialogProps {
  appeal: AppealResponse | null;
  onClose: () => void;
  onResolved: () => void;
}

function ResolveAppealDialog({ appeal, onClose, onResolved }: ResolveAppealDialogProps) {
  const [resolution, setResolution] = useState<ResolveAppealRequest['resolution']>('upheld');
  const [notes, setNotes] = useState('');
  const queryClient = useQueryClient();

  const resolveMutation = useMutation({
    mutationFn: (request: ResolveAppealRequest) =>
      resolveAppeal(appeal!.id, request),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['moderation-appeals'] });
      setNotes('');
      onClose();
      onResolved();
    },
  });

  const handleSubmit = () => {
    resolveMutation.mutate({ resolution, notes });
  };

  const resolutionOptions: { value: ResolveAppealRequest['resolution']; label: string; description: string }[] = [
    { value: 'upheld', label: 'Uphold', description: 'Original action stands' },
    { value: 'reduced', label: 'Reduce', description: 'Lessen the severity' },
    { value: 'overturned', label: 'Overturn', description: 'Reverse the action' },
  ];

  return (
    <Dialog open={!!appeal} onOpenChange={() => onClose()}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Resolve Appeal</DialogTitle>
          <DialogDescription>
            Review the appeal from @{appeal?.username} and provide a resolution.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-4">
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
                  {resolveMutation.error?.message || 'Failed to resolve appeal'}
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

interface AppealsQueueProps {
  appeals: AppealResponse[];
  isLoading: boolean;
  error: ApiError | null;
  onRefresh: () => void;
}

export function AppealsQueue({ appeals, isLoading, error, onRefresh }: AppealsQueueProps) {
  const [selectedAppeal, setSelectedAppeal] = useState<AppealResponse | null>(null);

  const handleResolve = (appealId: number) => {
    const appeal = appeals.find((a) => a.id === appealId);
    if (appeal) {
      setSelectedAppeal(appeal);
    }
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
            {error.message || 'Failed to load appeals'}
          </p>
          <Button variant="outline" onClick={onRefresh}>
            <RefreshCw className="w-4 h-4 mr-2" />
            Retry
          </Button>
        </CardContent>
      </Card>
    );
  }

  if (appeals.length === 0) {
    return (
      <Card className="glow-accent">
        <CardContent className="py-12 text-center">
          <CheckCircle className="w-12 h-12 mx-auto text-[rgb(var(--success))] mb-3" />
          <p className="text-muted-foreground">No pending appeals</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="font-medium text-foreground flex items-center gap-2">
          <MessageSquareWarning className="w-5 h-5 text-[rgb(var(--accent))]" />
          Pending Appeals ({appeals.length})
        </h3>
        <Button variant="outline" size="sm" onClick={onRefresh}>
          <RefreshCw className="w-4 h-4 mr-1" />
          Refresh
        </Button>
      </div>

      <div className="space-y-3">
        {appeals.map((appeal) => (
          <AppealCard
            key={appeal.id}
            appeal={appeal}
            onResolve={handleResolve}
          />
        ))}
      </div>

      {/* Resolve Dialog */}
      <ResolveAppealDialog
        appeal={selectedAppeal}
        onClose={() => setSelectedAppeal(null)}
        onResolved={onRefresh}
      />
    </div>
  );
}
