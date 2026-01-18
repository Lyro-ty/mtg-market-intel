'use client';

import { useState } from 'react';
import {
  AlertTriangle,
  AlertCircle,
  Clock,
  Flag,
  Gavel,
  MessageSquareWarning,
  User,
  Loader2,
  Filter,
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { ScrollArea } from '@/components/ui/scroll-area';
import { formatRelativeTime, cn } from '@/lib/utils';
import type { ModerationQueueItem, FlagLevel, FlagType } from '@/lib/api/moderation';

// =============================================================================
// Priority Badge Component
// =============================================================================

interface PriorityBadgeProps {
  level: FlagLevel;
}

function PriorityBadge({ level }: PriorityBadgeProps) {
  const config: Record<FlagLevel, { variant: 'destructive' | 'warning' | 'secondary' | 'outline'; label: string }> = {
    critical: { variant: 'destructive', label: 'Critical' },
    high: { variant: 'warning', label: 'High' },
    medium: { variant: 'secondary', label: 'Medium' },
    low: { variant: 'outline', label: 'Low' },
  };

  const { variant, label } = config[level] || config.low;

  return <Badge variant={variant}>{label}</Badge>;
}

// =============================================================================
// Flag Type Icon Component
// =============================================================================

interface FlagTypeIconProps {
  type: FlagType;
  className?: string;
}

function FlagTypeIcon({ type, className }: FlagTypeIconProps) {
  switch (type) {
    case 'report':
      return <Flag className={cn('w-4 h-4', className)} />;
    case 'auto_flag':
      return <AlertTriangle className={cn('w-4 h-4', className)} />;
    case 'dispute':
      return <Gavel className={cn('w-4 h-4', className)} />;
    case 'appeal':
      return <MessageSquareWarning className={cn('w-4 h-4', className)} />;
    default:
      return <AlertCircle className={cn('w-4 h-4', className)} />;
  }
}

// =============================================================================
// Queue Item Component
// =============================================================================

interface QueueItemProps {
  item: ModerationQueueItem;
  isSelected: boolean;
  onClick: () => void;
}

function QueueItem({ item, isSelected, onClick }: QueueItemProps) {
  const priorityColors: Record<FlagLevel, string> = {
    critical: 'border-l-4 border-l-[rgb(var(--destructive))]',
    high: 'border-l-4 border-l-[rgb(var(--warning))]',
    medium: 'border-l-4 border-l-amber-400',
    low: 'border-l-4 border-l-muted-foreground',
  };

  return (
    <button
      onClick={onClick}
      className={cn(
        'w-full p-3 text-left rounded-lg transition-colors',
        priorityColors[item.flag_level],
        isSelected
          ? 'bg-[rgb(var(--accent))]/10 border border-[rgb(var(--accent))]/30'
          : 'bg-muted/30 hover:bg-muted/50 border border-transparent'
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <div className="p-1.5 rounded-full bg-muted/50">
            <User className="w-4 h-4 text-muted-foreground" />
          </div>
          <div className="min-w-0">
            <p className="font-medium text-foreground truncate">
              {item.target_username}
            </p>
            <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <FlagTypeIcon type={item.flag_type} className="w-3 h-3" />
              <span className="capitalize">{item.flag_type.replace('_', ' ')}</span>
            </div>
          </div>
        </div>
        <div className="flex flex-col items-end gap-1 shrink-0">
          <PriorityBadge level={item.flag_level} />
          {item.report_count > 1 && (
            <span className="text-xs text-muted-foreground">
              {item.report_count} reports
            </span>
          )}
        </div>
      </div>
      <p className="mt-2 text-sm text-muted-foreground line-clamp-2">
        {item.flag_reason}
      </p>
      <div className="mt-2 flex items-center gap-1 text-xs text-muted-foreground">
        <Clock className="w-3 h-3" />
        {formatRelativeTime(item.created_at)}
      </div>
    </button>
  );
}

// =============================================================================
// Empty State Component
// =============================================================================

function EmptyState({ filtered }: { filtered: boolean }) {
  return (
    <div className="py-12 text-center">
      <Flag className="w-12 h-12 mx-auto text-muted-foreground mb-3" />
      <p className="text-muted-foreground">
        {filtered
          ? 'No items match the current filter'
          : 'No pending items in the moderation queue'}
      </p>
    </div>
  );
}

// =============================================================================
// Main Component
// =============================================================================

interface ModerationQueueProps {
  items: ModerationQueueItem[];
  isLoading: boolean;
  selectedUserId: number | null;
  onSelectCase: (userId: number) => void;
}

export function ModerationQueue({
  items,
  isLoading,
  selectedUserId,
  onSelectCase,
}: ModerationQueueProps) {
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [priorityFilter, setPriorityFilter] = useState<string>('all');

  // Filter items
  const filteredItems = items.filter((item) => {
    // Filter out appeals and disputes - they have their own tabs
    if (item.flag_type === 'appeal' || item.flag_type === 'dispute') {
      return false;
    }

    if (priorityFilter !== 'all' && item.flag_level !== priorityFilter) {
      return false;
    }

    return true;
  });

  // Sort by priority and date
  const sortedItems = [...filteredItems].sort((a, b) => {
    const priorityOrder = { critical: 0, high: 1, medium: 2, low: 3 };
    const aPriority = priorityOrder[a.flag_level] ?? 4;
    const bPriority = priorityOrder[b.flag_level] ?? 4;

    if (aPriority !== bPriority) {
      return aPriority - bPriority;
    }

    return new Date(a.created_at).getTime() - new Date(b.created_at).getTime();
  });

  const hasFilters = priorityFilter !== 'all';

  return (
    <Card className="glow-accent">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2 text-lg">
            <Flag className="w-5 h-5 text-[rgb(var(--accent))]" />
            Moderation Queue
            {sortedItems.length > 0 && (
              <span className="text-sm font-normal text-muted-foreground">
                ({sortedItems.length} items)
              </span>
            )}
          </CardTitle>
        </div>
        {/* Filters */}
        <div className="flex items-center gap-2 mt-3">
          <Filter className="w-4 h-4 text-muted-foreground" />
          <Select value={priorityFilter} onValueChange={setPriorityFilter}>
            <SelectTrigger className="w-[140px] h-8">
              <SelectValue placeholder="Priority" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Priorities</SelectItem>
              <SelectItem value="critical">Critical</SelectItem>
              <SelectItem value="high">High</SelectItem>
              <SelectItem value="medium">Medium</SelectItem>
              <SelectItem value="low">Low</SelectItem>
            </SelectContent>
          </Select>
          {hasFilters && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                setStatusFilter('all');
                setPriorityFilter('all');
              }}
              className="text-xs"
            >
              Clear
            </Button>
          )}
        </div>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-6 h-6 animate-spin text-[rgb(var(--accent))]" />
          </div>
        ) : sortedItems.length === 0 ? (
          <EmptyState filtered={hasFilters} />
        ) : (
          <ScrollArea className="h-[500px] pr-3">
            <div className="space-y-2">
              {sortedItems.map((item) => (
                <QueueItem
                  key={`${item.flag_type}-${item.id}`}
                  item={item}
                  isSelected={selectedUserId === item.target_user_id}
                  onClick={() => onSelectCase(item.target_user_id)}
                />
              ))}
            </div>
          </ScrollArea>
        )}
      </CardContent>
    </Card>
  );
}
