'use client';

import React from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Lightbulb,
  Bell,
  AlertTriangle,
  Eye,
  EyeOff,
  ChevronRight,
  Clock,
  Target,
  BookOpen,
  TrendingUp,
  TrendingDown,
  Trophy,
  Loader2,
} from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { PageHeader } from '@/components/ornate/page-header';
import { PriceChange } from '@/components/ornate/price-change';
import { formatCurrency, cn } from '@/lib/utils';
import { getNotifications, markNotificationRead, markAllNotificationsRead } from '@/lib/api';
import type { Notification, NotificationType, NotificationPriority } from '@/types';
import { formatDistanceToNow } from 'date-fns';

// Map notification types to insight categories
type InsightCategory = 'alert' | 'opportunity' | 'educational';

function getInsightCategory(type: NotificationType): InsightCategory {
  switch (type) {
    case 'price_spike':
    case 'price_drop':
      return 'alert';
    case 'price_alert':
    case 'milestone':
      return 'opportunity';
    case 'educational':
    case 'system':
    default:
      return 'educational';
  }
}

const categoryIcons = {
  alert: AlertTriangle,
  opportunity: Target,
  educational: BookOpen,
};

const categoryColors = {
  alert: 'text-[rgb(var(--destructive))]',
  opportunity: 'text-[rgb(var(--success))]',
  educational: 'text-[rgb(var(--accent))]',
};

const priorityStyles: Record<NotificationPriority, { badge: string; border: string }> = {
  urgent: {
    badge: 'bg-[rgb(var(--destructive))]/20 text-[rgb(var(--destructive))] border-[rgb(var(--destructive))]/30',
    border: 'border-l-[rgb(var(--destructive))]',
  },
  high: {
    badge: 'bg-[rgb(var(--mythic-orange))]/20 text-[rgb(var(--mythic-orange))] border-[rgb(var(--mythic-orange))]/30',
    border: 'border-l-[rgb(var(--mythic-orange))]',
  },
  medium: {
    badge: 'bg-[rgb(var(--warning))]/20 text-[rgb(var(--warning))] border-[rgb(var(--warning))]/30',
    border: 'border-l-[rgb(var(--warning))]',
  },
  low: {
    badge: 'bg-[rgb(var(--muted))]/20 text-muted-foreground border-border',
    border: 'border-l-border',
  },
};

function getTypeIcon(type: NotificationType) {
  switch (type) {
    case 'price_spike':
      return TrendingUp;
    case 'price_drop':
      return TrendingDown;
    case 'price_alert':
      return Target;
    case 'milestone':
      return Trophy;
    case 'educational':
      return BookOpen;
    case 'system':
    default:
      return Bell;
  }
}

function InsightCard({
  notification,
  onMarkRead
}: {
  notification: Notification;
  onMarkRead: (id: number) => void;
}) {
  const category = getInsightCategory(notification.type);
  const Icon = getTypeIcon(notification.type);
  const metadata = notification.metadata;

  const timeAgo = formatDistanceToNow(new Date(notification.created_at), { addSuffix: true });

  return (
    <Card className={cn(
      'glow-accent border-l-4 transition-all hover:border-[rgb(var(--accent))]/30',
      priorityStyles[notification.priority].border,
      !notification.read && 'bg-[rgb(var(--accent))]/5'
    )}>
      <CardContent className="p-4">
        <div className="flex gap-4">
          {/* Icon */}
          <div className={cn(
            'w-10 h-10 rounded-lg flex items-center justify-center shrink-0',
            category === 'alert' && 'bg-[rgb(var(--destructive))]/10',
            category === 'opportunity' && 'bg-[rgb(var(--success))]/10',
            category === 'educational' && 'bg-[rgb(var(--accent))]/10'
          )}>
            <Icon className={cn('w-5 h-5', categoryColors[category])} />
          </div>

          {/* Content */}
          <div className="flex-1 min-w-0">
            <div className="flex items-start justify-between gap-2">
              <div>
                <div className="flex items-center gap-2 mb-1">
                  <h3 className={cn(
                    'font-heading font-medium',
                    !notification.read ? 'text-foreground' : 'text-muted-foreground'
                  )}>
                    {notification.title}
                  </h3>
                  {!notification.read && (
                    <span className="w-2 h-2 rounded-full bg-[rgb(var(--accent))]" />
                  )}
                </div>
                <p className="text-sm text-muted-foreground">{notification.message}</p>
              </div>
              <Badge className={priorityStyles[notification.priority].badge}>
                {notification.priority}
              </Badge>
            </div>

            {/* Card Info (if applicable) */}
            {metadata?.card_name && (
              <div className="mt-3 flex items-center gap-4 p-2 rounded-lg bg-secondary/50">
                <div className="flex-1">
                  <p className="font-medium text-foreground">{metadata.card_name}</p>
                  {metadata.set_code && (
                    <p className="text-xs text-muted-foreground">{metadata.set_code}</p>
                  )}
                </div>
                {metadata.current_price !== undefined && (
                  <div className="text-right">
                    <p className="font-medium text-foreground">
                      {formatCurrency(metadata.current_price)}
                    </p>
                    {metadata.price_change !== undefined && (
                      <PriceChange value={metadata.price_change} format="percent" size="sm" />
                    )}
                  </div>
                )}
              </div>
            )}

            {/* Footer */}
            <div className="mt-3 flex items-center justify-between">
              <span className="text-xs text-muted-foreground flex items-center gap-1">
                <Clock className="w-3 h-3" />
                {timeAgo}
              </span>
              <div className="flex items-center gap-2">
                {!notification.read && (
                  <Button
                    variant="ghost"
                    size="sm"
                    className="text-muted-foreground h-7"
                    onClick={() => onMarkRead(notification.id)}
                  >
                    Mark read
                  </Button>
                )}
                {metadata?.action && (
                  <Button variant="ghost" size="sm" className="text-[rgb(var(--accent))] h-7">
                    {metadata.action}
                    <ChevronRight className="w-4 h-4 ml-1" />
                  </Button>
                )}
              </div>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function InsightSkeleton() {
  return (
    <Card className="glow-accent border-l-4 border-l-border">
      <CardContent className="p-4">
        <div className="flex gap-4">
          <Skeleton className="w-10 h-10 rounded-lg" />
          <div className="flex-1">
            <div className="flex justify-between">
              <Skeleton className="h-5 w-48 mb-2" />
              <Skeleton className="h-5 w-16" />
            </div>
            <Skeleton className="h-4 w-full mb-3" />
            <Skeleton className="h-16 w-full mb-3" />
            <div className="flex justify-between">
              <Skeleton className="h-4 w-24" />
              <Skeleton className="h-7 w-20" />
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

export default function InsightsPage() {
  const queryClient = useQueryClient();
  const [filter, setFilter] = React.useState<'all' | NotificationType>('all');
  const [showUnreadOnly, setShowUnreadOnly] = React.useState(false);

  // Fetch notifications
  const { data, isLoading, error } = useQuery({
    queryKey: ['notifications', { unread_only: showUnreadOnly }],
    queryFn: () => getNotifications({ unread_only: showUnreadOnly, limit: 50 }),
    refetchInterval: 60000, // Refetch every minute
  });

  // Mark single notification as read
  const markReadMutation = useMutation({
    mutationFn: (id: number) => markNotificationRead(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notifications'] });
    },
  });

  // Mark all as read
  const markAllReadMutation = useMutation({
    mutationFn: markAllNotificationsRead,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notifications'] });
    },
  });

  // Filter notifications
  const filteredNotifications = React.useMemo(() => {
    if (!data?.items) return [];
    if (filter === 'all') return data.items;
    return data.items.filter(n => n.type === filter);
  }, [data?.items, filter]);

  // Count by category
  const counts = React.useMemo(() => {
    if (!data?.items) return { total: 0, alerts: 0, opportunities: 0, unread: 0 };
    return {
      total: data.items.length,
      alerts: data.items.filter(n => getInsightCategory(n.type) === 'alert').length,
      opportunities: data.items.filter(n => getInsightCategory(n.type) === 'opportunity').length,
      unread: data.unread_count,
    };
  }, [data]);

  if (error) {
    return (
      <div className="space-y-6 animate-in">
        <PageHeader
          title="Insights"
          subtitle="Portfolio alerts, market opportunities, and actionable intelligence"
        />
        <Card className="glow-accent">
          <CardContent className="py-12 text-center">
            <AlertTriangle className="w-12 h-12 mx-auto text-[rgb(var(--destructive))] mb-4" />
            <p className="text-muted-foreground">
              Failed to load insights. Please try again later.
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-in">
      <PageHeader
        title="Insights"
        subtitle="Portfolio alerts, market opportunities, and actionable intelligence"
      >
        <Button
          variant="secondary"
          size="sm"
          onClick={() => setShowUnreadOnly(!showUnreadOnly)}
          className={cn('glow-accent', showUnreadOnly && 'bg-[rgb(var(--accent))]/20')}
        >
          {showUnreadOnly ? <Eye className="w-4 h-4 mr-1" /> : <EyeOff className="w-4 h-4 mr-1" />}
          {showUnreadOnly ? 'Show All' : 'Unread Only'}
        </Button>
        <Button
          variant="secondary"
          size="sm"
          className="glow-accent"
          onClick={() => markAllReadMutation.mutate()}
          disabled={markAllReadMutation.isPending || counts.unread === 0}
        >
          {markAllReadMutation.isPending ? (
            <Loader2 className="w-4 h-4 mr-1 animate-spin" />
          ) : (
            <Bell className="w-4 h-4 mr-1" />
          )}
          Mark All Read
        </Button>
      </PageHeader>

      {/* Summary Stats */}
      <div className="grid grid-cols-4 gap-4">
        <Card className={cn(
          'glow-accent cursor-pointer transition-all',
          filter === 'all' && 'ring-2 ring-[rgb(var(--accent))]'
        )} onClick={() => setFilter('all')}>
          <CardContent className="p-4 text-center">
            <Lightbulb className="w-6 h-6 mx-auto text-[rgb(var(--accent))] mb-2" />
            {isLoading ? (
              <Skeleton className="h-8 w-12 mx-auto" />
            ) : (
              <p className="text-2xl font-bold text-foreground">{counts.total}</p>
            )}
            <p className="text-sm text-muted-foreground">Total Insights</p>
          </CardContent>
        </Card>
        <Card className={cn(
          'glow-accent cursor-pointer transition-all',
          (filter === 'price_spike' || filter === 'price_drop') && 'ring-2 ring-[rgb(var(--destructive))]'
        )} onClick={() => setFilter('price_spike')}>
          <CardContent className="p-4 text-center">
            <AlertTriangle className="w-6 h-6 mx-auto text-[rgb(var(--destructive))] mb-2" />
            {isLoading ? (
              <Skeleton className="h-8 w-12 mx-auto" />
            ) : (
              <p className="text-2xl font-bold text-[rgb(var(--destructive))]">{counts.alerts}</p>
            )}
            <p className="text-sm text-muted-foreground">Alerts</p>
          </CardContent>
        </Card>
        <Card className={cn(
          'glow-accent cursor-pointer transition-all',
          (filter === 'price_alert' || filter === 'milestone') && 'ring-2 ring-[rgb(var(--success))]'
        )} onClick={() => setFilter('price_alert')}>
          <CardContent className="p-4 text-center">
            <Target className="w-6 h-6 mx-auto text-[rgb(var(--success))] mb-2" />
            {isLoading ? (
              <Skeleton className="h-8 w-12 mx-auto" />
            ) : (
              <p className="text-2xl font-bold text-[rgb(var(--success))]">{counts.opportunities}</p>
            )}
            <p className="text-sm text-muted-foreground">Opportunities</p>
          </CardContent>
        </Card>
        <Card className="glow-accent">
          <CardContent className="p-4 text-center">
            <Bell className="w-6 h-6 mx-auto text-[rgb(var(--magic-gold))] mb-2" />
            {isLoading ? (
              <Skeleton className="h-8 w-12 mx-auto" />
            ) : (
              <p className="text-2xl font-bold text-[rgb(var(--magic-gold))]">{counts.unread}</p>
            )}
            <p className="text-sm text-muted-foreground">Unread</p>
          </CardContent>
        </Card>
      </div>

      {/* Insights List */}
      {isLoading ? (
        <div className="space-y-4">
          {[1, 2, 3].map((i) => (
            <InsightSkeleton key={i} />
          ))}
        </div>
      ) : filteredNotifications.length === 0 ? (
        <Card className="glow-accent">
          <CardContent className="py-12 text-center">
            <Lightbulb className="w-12 h-12 mx-auto text-muted-foreground mb-4" />
            <p className="text-muted-foreground">
              {showUnreadOnly
                ? "No unread insights. You're all caught up!"
                : 'No insights yet. Start tracking cards to receive personalized alerts.'}
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-4">
          {filteredNotifications.map((notification) => (
            <InsightCard
              key={notification.id}
              notification={notification}
              onMarkRead={(id) => markReadMutation.mutate(id)}
            />
          ))}
        </div>
      )}

      {/* Educational Footer */}
      <Card className="bg-gradient-to-r from-[rgb(var(--accent))]/10 to-[rgb(var(--magic-gold))]/10 border-[rgb(var(--accent))]/20">
        <CardContent className="p-4 flex items-center gap-4">
          <BookOpen className="w-8 h-8 text-[rgb(var(--accent))] shrink-0" />
          <div>
            <h3 className="font-heading font-medium text-foreground">
              Learn to Read the Market
            </h3>
            <p className="text-sm text-muted-foreground">
              Add cards to your inventory and want list to receive personalized price alerts and market insights.
            </p>
          </div>
          <Button variant="secondary" size="sm" className="shrink-0 ml-auto" asChild>
            <a href="/cards">Browse Cards</a>
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
