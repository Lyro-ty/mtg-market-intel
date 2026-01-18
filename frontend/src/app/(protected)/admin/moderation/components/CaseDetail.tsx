'use client';

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  X,
  User,
  Calendar,
  Shield,
  AlertTriangle,
  CheckCircle,
  MessageSquare,
  ArrowLeftRight,
  Clock,
  Send,
  Loader2,
  AlertCircle,
  StickyNote,
  History,
  BarChart3,
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import { Separator } from '@/components/ui/separator';
import { ScrollArea } from '@/components/ui/scroll-area';
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
  DialogTrigger,
} from '@/components/ui/dialog';
import {
  getCaseDetail,
  takeAction,
  addUserNote,
  ApiError,
} from '@/lib/api';
import { formatRelativeTime, cn } from '@/lib/utils';
import type {
  ModerationCaseDetail,
  TakeActionRequest,
  ModNoteInfo,
} from '@/lib/api/moderation';

// =============================================================================
// Action Types
// =============================================================================

type ActionType = TakeActionRequest['action'];

const actionConfig: Record<ActionType, { label: string; description: string; variant: 'outline' | 'secondary' | 'destructive' }> = {
  dismiss: {
    label: 'Dismiss',
    description: 'Close this report without further action',
    variant: 'outline',
  },
  warn: {
    label: 'Warn',
    description: 'Send a warning to the user',
    variant: 'secondary',
  },
  restrict: {
    label: 'Restrict',
    description: 'Temporarily restrict user privileges',
    variant: 'secondary',
  },
  suspend: {
    label: 'Suspend',
    description: 'Temporarily suspend the account',
    variant: 'destructive',
  },
  ban: {
    label: 'Ban',
    description: 'Permanently ban the account',
    variant: 'destructive',
  },
  escalate: {
    label: 'Escalate',
    description: 'Escalate to senior moderator',
    variant: 'outline',
  },
};

// =============================================================================
// User Info Section
// =============================================================================

interface UserInfoSectionProps {
  user: ModerationCaseDetail['target_user'];
  tradeStats: ModerationCaseDetail['trade_stats'];
}

function UserInfoSection({ user, tradeStats }: UserInfoSectionProps) {
  return (
    <div className="space-y-4">
      {/* User header */}
      <div className="flex items-center gap-3">
        <div className="w-12 h-12 rounded-full bg-muted flex items-center justify-center">
          {user.avatar_url ? (
            <img
              src={user.avatar_url}
              alt={user.username}
              className="w-12 h-12 rounded-full"
            />
          ) : (
            <User className="w-6 h-6 text-muted-foreground" />
          )}
        </div>
        <div>
          <p className="font-semibold text-foreground">
            {user.display_name || user.username}
          </p>
          <p className="text-sm text-muted-foreground">@{user.username}</p>
        </div>
      </div>

      {/* User details */}
      <div className="grid grid-cols-2 gap-2 text-sm">
        <div className="flex items-center gap-1.5 text-muted-foreground">
          <Calendar className="w-4 h-4" />
          <span>
            Joined {user.created_at ? formatRelativeTime(user.created_at) : 'Unknown'}
          </span>
        </div>
        <div className="flex items-center gap-1.5">
          {user.is_active ? (
            <>
              <CheckCircle className="w-4 h-4 text-[rgb(var(--success))]" />
              <span className="text-[rgb(var(--success))]">Active</span>
            </>
          ) : (
            <>
              <AlertTriangle className="w-4 h-4 text-[rgb(var(--destructive))]" />
              <span className="text-[rgb(var(--destructive))]">Suspended</span>
            </>
          )}
        </div>
        <div className="flex items-center gap-1.5 text-muted-foreground">
          <Shield className="w-4 h-4" />
          <span>{user.is_verified ? 'Verified' : 'Unverified'}</span>
        </div>
      </div>

      {/* Trade stats */}
      <div className="p-3 rounded-lg bg-muted/30">
        <div className="flex items-center gap-2 mb-2">
          <BarChart3 className="w-4 h-4 text-[rgb(var(--accent))]" />
          <span className="font-medium text-sm">Trade Statistics</span>
        </div>
        <div className="grid grid-cols-2 gap-2 text-sm">
          <div>
            <span className="text-muted-foreground">Total: </span>
            <span className="text-foreground">{tradeStats.total_trades}</span>
          </div>
          <div>
            <span className="text-muted-foreground">Completed: </span>
            <span className="text-[rgb(var(--success))]">{tradeStats.completed_trades}</span>
          </div>
          <div>
            <span className="text-muted-foreground">Cancelled: </span>
            <span className="text-foreground">{tradeStats.cancelled_trades}</span>
          </div>
          <div>
            <span className="text-muted-foreground">Disputed: </span>
            <span className={tradeStats.disputed_trades > 0 ? 'text-[rgb(var(--warning))]' : 'text-foreground'}>
              {tradeStats.disputed_trades}
            </span>
          </div>
        </div>
        <div className="mt-2 pt-2 border-t border-border">
          <span className="text-muted-foreground">Completion Rate: </span>
          <span className={cn(
            'font-medium',
            tradeStats.completion_rate >= 80 ? 'text-[rgb(var(--success))]' :
            tradeStats.completion_rate >= 50 ? 'text-[rgb(var(--warning))]' :
            'text-[rgb(var(--destructive))]'
          )}>
            {tradeStats.completion_rate.toFixed(1)}%
          </span>
        </div>
      </div>
    </div>
  );
}

// =============================================================================
// Reports Section
// =============================================================================

interface ReportsSectionProps {
  reports: ModerationCaseDetail['reports'];
}

function ReportsSection({ reports }: ReportsSectionProps) {
  if (reports.length === 0) {
    return (
      <p className="text-sm text-muted-foreground text-center py-4">
        No reports against this user
      </p>
    );
  }

  return (
    <div className="space-y-2">
      {reports.slice(0, 5).map((report) => (
        <div
          key={report.id}
          className="p-3 rounded-lg bg-muted/30 border border-border/50"
        >
          <div className="flex items-center justify-between mb-1">
            <span className="text-sm font-medium text-foreground">
              {report.reason}
            </span>
            <span className="text-xs text-muted-foreground">
              {formatRelativeTime(report.created_at)}
            </span>
          </div>
          {report.details && (
            <p className="text-sm text-muted-foreground line-clamp-2">
              {report.details}
            </p>
          )}
          <p className="text-xs text-muted-foreground mt-1">
            Reported by @{report.reporter_username}
          </p>
        </div>
      ))}
      {reports.length > 5 && (
        <p className="text-sm text-muted-foreground text-center">
          +{reports.length - 5} more reports
        </p>
      )}
    </div>
  );
}

// =============================================================================
// Previous Actions Section
// =============================================================================

interface PreviousActionsSectionProps {
  actions: ModerationCaseDetail['previous_actions'];
}

function PreviousActionsSection({ actions }: PreviousActionsSectionProps) {
  if (actions.length === 0) {
    return (
      <p className="text-sm text-muted-foreground text-center py-4">
        No previous moderation actions
      </p>
    );
  }

  return (
    <div className="space-y-2">
      {actions.map((action) => (
        <div
          key={action.id}
          className="p-3 rounded-lg bg-muted/30 border border-border/50"
        >
          <div className="flex items-center justify-between">
            <Badge
              variant={
                action.action_type === 'ban' ? 'destructive' :
                action.action_type === 'suspend' ? 'warning' :
                'secondary'
              }
            >
              {action.action_type}
            </Badge>
            <span className="text-xs text-muted-foreground">
              {formatRelativeTime(action.created_at)}
            </span>
          </div>
          {action.reason && (
            <p className="text-sm text-muted-foreground mt-1 line-clamp-2">
              {action.reason}
            </p>
          )}
          {action.moderator_username && (
            <p className="text-xs text-muted-foreground mt-1">
              By @{action.moderator_username}
            </p>
          )}
        </div>
      ))}
    </div>
  );
}

// =============================================================================
// Moderator Notes Section
// =============================================================================

interface ModeratorNotesSectionProps {
  notes: ModerationCaseDetail['mod_notes'];
  userId: number;
  onNoteAdded: () => void;
}

function ModeratorNotesSection({ notes, userId, onNoteAdded }: ModeratorNotesSectionProps) {
  const [newNote, setNewNote] = useState('');
  const queryClient = useQueryClient();

  const addNoteMutation = useMutation({
    mutationFn: (content: string) => addUserNote(userId, { content }),
    onSuccess: () => {
      setNewNote('');
      queryClient.invalidateQueries({ queryKey: ['moderation-case', userId] });
      onNoteAdded();
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (newNote.trim()) {
      addNoteMutation.mutate(newNote.trim());
    }
  };

  return (
    <div className="space-y-3">
      {/* Add note form */}
      <form onSubmit={handleSubmit} className="flex gap-2">
        <Textarea
          value={newNote}
          onChange={(e) => setNewNote(e.target.value)}
          placeholder="Add a note..."
          className="min-h-[60px] resize-none"
        />
        <Button
          type="submit"
          size="sm"
          disabled={!newNote.trim() || addNoteMutation.isPending}
          className="shrink-0"
        >
          {addNoteMutation.isPending ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <Send className="w-4 h-4" />
          )}
        </Button>
      </form>

      {/* Existing notes */}
      {notes.length === 0 ? (
        <p className="text-sm text-muted-foreground text-center py-2">
          No moderator notes yet
        </p>
      ) : (
        <div className="space-y-2">
          {notes.map((note) => (
            <div
              key={note.id}
              className="p-2 rounded-lg bg-muted/30 border border-border/50"
            >
              <p className="text-sm text-foreground">{note.content}</p>
              <div className="flex items-center justify-between mt-1">
                <span className="text-xs text-muted-foreground">
                  @{note.moderator_username}
                </span>
                <span className="text-xs text-muted-foreground">
                  {formatRelativeTime(note.created_at)}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// =============================================================================
// Take Action Dialog
// =============================================================================

interface TakeActionDialogProps {
  userId: number;
  username: string;
  onActionComplete: () => void;
}

function TakeActionDialog({ userId, username, onActionComplete }: TakeActionDialogProps) {
  const [open, setOpen] = useState(false);
  const [selectedAction, setSelectedAction] = useState<ActionType>('warn');
  const [reason, setReason] = useState('');
  const [durationDays, setDurationDays] = useState<string>('');

  const actionMutation = useMutation({
    mutationFn: (request: TakeActionRequest) => takeAction(userId, request),
    onSuccess: () => {
      setOpen(false);
      setReason('');
      setDurationDays('');
      onActionComplete();
    },
  });

  const handleSubmit = () => {
    const request: TakeActionRequest = {
      action: selectedAction,
      reason,
    };

    if ((selectedAction === 'restrict' || selectedAction === 'suspend') && durationDays) {
      request.duration_days = parseInt(durationDays, 10);
    }

    actionMutation.mutate(request);
  };

  const needsDuration = selectedAction === 'restrict' || selectedAction === 'suspend';
  const config = actionConfig[selectedAction];

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button className="w-full gradient-arcane text-white glow-accent">
          Take Action
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Take Moderation Action</DialogTitle>
          <DialogDescription>
            Take action against @{username}. This will be logged and visible to other moderators.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-4">
          {/* Action type selector */}
          <div className="space-y-2">
            <Label>Action Type</Label>
            <Select value={selectedAction} onValueChange={(v) => setSelectedAction(v as ActionType)}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {Object.entries(actionConfig).map(([key, { label, description }]) => (
                  <SelectItem key={key} value={key}>
                    <div>
                      <span className="font-medium">{label}</span>
                      <span className="text-muted-foreground ml-2 text-xs">
                        - {description}
                      </span>
                    </div>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Duration (for restrict/suspend) */}
          {needsDuration && (
            <div className="space-y-2">
              <Label>Duration (days)</Label>
              <Input
                type="number"
                min="1"
                max="365"
                value={durationDays}
                onChange={(e) => setDurationDays(e.target.value)}
                placeholder="e.g., 7"
              />
            </div>
          )}

          {/* Reason */}
          <div className="space-y-2">
            <Label>Reason</Label>
            <Textarea
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="Explain the reason for this action..."
              className="min-h-[100px]"
            />
          </div>

          {/* Error display */}
          {actionMutation.isError && (
            <div className="p-3 rounded-lg bg-[rgb(var(--destructive))]/10 border border-[rgb(var(--destructive))]/20">
              <div className="flex items-center gap-2">
                <AlertCircle className="w-4 h-4 text-[rgb(var(--destructive))]" />
                <p className="text-sm text-[rgb(var(--destructive))]">
                  {actionMutation.error?.message || 'Failed to take action'}
                </p>
              </div>
            </div>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => setOpen(false)}>
            Cancel
          </Button>
          <Button
            variant={config.variant}
            onClick={handleSubmit}
            disabled={!reason.trim() || actionMutation.isPending}
          >
            {actionMutation.isPending ? (
              <>
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                Processing...
              </>
            ) : (
              config.label
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

interface CaseDetailProps {
  userId: number;
  onClose: () => void;
  onActionComplete: () => void;
}

export function CaseDetail({ userId, onClose, onActionComplete }: CaseDetailProps) {
  const {
    data: caseData,
    isLoading,
    error,
    refetch,
  } = useQuery<ModerationCaseDetail, ApiError>({
    queryKey: ['moderation-case', userId],
    queryFn: () => getCaseDetail(userId),
  });

  if (isLoading) {
    return (
      <Card className="glow-accent">
        <CardContent className="py-12">
          <div className="flex items-center justify-center">
            <Loader2 className="w-8 h-8 animate-spin text-[rgb(var(--accent))]" />
          </div>
        </CardContent>
      </Card>
    );
  }

  if (error || !caseData) {
    return (
      <Card className="glow-accent">
        <CardContent className="py-12">
          <div className="text-center">
            <AlertCircle className="w-12 h-12 mx-auto text-[rgb(var(--destructive))] mb-3" />
            <p className="text-[rgb(var(--destructive))]">
              {error?.message || 'Failed to load case details'}
            </p>
            <Button variant="outline" className="mt-4" onClick={() => refetch()}>
              Retry
            </Button>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="glow-accent">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2 text-lg">
            <User className="w-5 h-5 text-[rgb(var(--accent))]" />
            Case Details
          </CardTitle>
          <Button variant="ghost" size="icon" onClick={onClose}>
            <X className="w-4 h-4" />
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        <ScrollArea className="h-[500px] pr-3">
          <div className="space-y-6">
            {/* User Info */}
            <UserInfoSection
              user={caseData.target_user}
              tradeStats={caseData.trade_stats}
            />

            <Separator />

            {/* Reports */}
            <div>
              <h4 className="font-medium text-sm mb-2 flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 text-[rgb(var(--warning))]" />
                Reports ({caseData.reports.length})
              </h4>
              <ReportsSection reports={caseData.reports} />
            </div>

            <Separator />

            {/* Previous Actions */}
            <div>
              <h4 className="font-medium text-sm mb-2 flex items-center gap-2">
                <History className="w-4 h-4 text-muted-foreground" />
                Previous Actions ({caseData.previous_actions.length})
              </h4>
              <PreviousActionsSection actions={caseData.previous_actions} />
            </div>

            <Separator />

            {/* Moderator Notes */}
            <div>
              <h4 className="font-medium text-sm mb-2 flex items-center gap-2">
                <StickyNote className="w-4 h-4 text-[rgb(var(--accent))]" />
                Moderator Notes ({caseData.mod_notes.length})
              </h4>
              <ModeratorNotesSection
                notes={caseData.mod_notes}
                userId={userId}
                onNoteAdded={() => refetch()}
              />
            </div>

            <Separator />

            {/* Recent Trades */}
            {caseData.recent_trades.length > 0 && (
              <div>
                <h4 className="font-medium text-sm mb-2 flex items-center gap-2">
                  <ArrowLeftRight className="w-4 h-4 text-muted-foreground" />
                  Recent Trades ({caseData.recent_trades.length})
                </h4>
                <div className="space-y-2">
                  {caseData.recent_trades.slice(0, 5).map((trade) => (
                    <div
                      key={trade.id}
                      className="p-2 rounded-lg bg-muted/30 border border-border/50 flex items-center justify-between"
                    >
                      <div>
                        <span className="text-sm text-foreground">
                          Trade with @{trade.other_party_username}
                        </span>
                        <div className="flex items-center gap-1 text-xs text-muted-foreground">
                          <Clock className="w-3 h-3" />
                          {formatRelativeTime(trade.created_at)}
                        </div>
                      </div>
                      <Badge
                        variant={
                          trade.status === 'completed' ? 'success' :
                          trade.status === 'cancelled' ? 'destructive' :
                          'secondary'
                        }
                      >
                        {trade.status}
                      </Badge>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Action Buttons */}
            <div className="pt-4 space-y-2">
              <TakeActionDialog
                userId={userId}
                username={caseData.target_user.username}
                onActionComplete={onActionComplete}
              />
            </div>
          </div>
        </ScrollArea>
      </CardContent>
    </Card>
  );
}
