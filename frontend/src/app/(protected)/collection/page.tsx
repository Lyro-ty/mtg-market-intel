'use client';

import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Package,
  LayoutGrid,
  BarChart3,
  Trophy,
  TrendingUp,
  CheckCircle,
  Circle,
  Layers,
  RefreshCw,
  AlertCircle,
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { Badge } from '@/components/ui/badge';
import { PageHeader } from '@/components/ornate/page-header';
import {
  getInventory,
  getCollectionStats,
  refreshCollectionStats,
  getSetCompletions,
  getMilestones,
} from '@/lib/api';
import { formatCurrency, cn } from '@/lib/utils';
import type { SetCompletion, Milestone, CollectionStats } from '@/types';

type TabType = 'sets' | 'binder' | 'stats';

function SetProgressCard({ set }: { set: SetCompletion }) {
  const completionPct = Math.round(set.completion_percentage);

  return (
    <Card className="glow-accent hover:border-[rgb(var(--accent))]/30 transition-colors">
      <CardContent className="p-4">
        <div className="flex items-start justify-between mb-3">
          <div className="flex items-center gap-2">
            {set.icon_svg_uri && (
              <img
                src={set.icon_svg_uri}
                alt={set.set_code}
                className="w-6 h-6 opacity-80"
              />
            )}
            <div>
              <Badge variant="outline" className="mb-1 text-xs">
                {set.set_code.toUpperCase()}
              </Badge>
              <h3 className="font-heading text-foreground font-medium">{set.set_name}</h3>
            </div>
          </div>
        </div>

        {/* Progress bar */}
        <div className="space-y-2">
          <div className="flex justify-between text-sm">
            <span className="text-muted-foreground">
              {set.owned_cards} / {set.total_cards} cards
            </span>
            <span className={cn(
              'font-medium',
              completionPct >= 75 ? 'text-[rgb(var(--success))]' :
              completionPct >= 50 ? 'text-[rgb(var(--warning))]' :
              'text-muted-foreground'
            )}>
              {completionPct}%
            </span>
          </div>
          <div className="h-2 bg-secondary rounded-full overflow-hidden">
            <div
              className="h-full gradient-arcane rounded-full transition-all duration-500"
              style={{ width: `${completionPct}%` }}
            />
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function SetProgressSkeleton() {
  return (
    <Card className="glow-accent">
      <CardContent className="p-4">
        <div className="flex items-start justify-between mb-3">
          <div>
            <Skeleton className="h-5 w-12 mb-1" />
            <Skeleton className="h-5 w-40" />
          </div>
        </div>
        <div className="space-y-2">
          <div className="flex justify-between">
            <Skeleton className="h-4 w-24" />
            <Skeleton className="h-4 w-8" />
          </div>
          <Skeleton className="h-2 w-full" />
        </div>
      </CardContent>
    </Card>
  );
}

function SetsView() {
  const { data: setCompletions, isLoading, error } = useQuery({
    queryKey: ['setCompletions'],
    queryFn: () => getSetCompletions({ limit: 50, sortBy: 'completion' }),
  });

  if (isLoading) {
    return (
      <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
        {Array.from({ length: 6 }).map((_, i) => (
          <SetProgressSkeleton key={i} />
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <Card className="glow-accent">
        <CardContent className="py-12 text-center">
          <AlertCircle className="w-12 h-12 mx-auto text-[rgb(var(--warning))] mb-4" />
          <p className="text-muted-foreground">
            Failed to load set completion data. Please try again later.
          </p>
        </CardContent>
      </Card>
    );
  }

  if (!setCompletions || setCompletions.items.length === 0) {
    return (
      <Card className="glow-accent">
        <CardContent className="py-12 text-center">
          <Package className="w-12 h-12 mx-auto text-muted-foreground mb-4" />
          <p className="text-muted-foreground">
            No sets in your collection yet. Import cards to see set completion progress.
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
      {setCompletions.items.map((set) => (
        <SetProgressCard key={set.set_code} set={set} />
      ))}
    </div>
  );
}

function BinderView() {
  // Fetch inventory for binder display
  const { data: inventory, isLoading } = useQuery({
    queryKey: ['inventory', 1, '', undefined, undefined],
    queryFn: () => getInventory({ page: 1, pageSize: 60 }),
  });

  if (isLoading) {
    return (
      <div className="grid grid-cols-6 md:grid-cols-8 lg:grid-cols-10 gap-2">
        {Array.from({ length: 30 }).map((_, i) => (
          <Skeleton key={i} className="aspect-[63/88] rounded" />
        ))}
      </div>
    );
  }

  if (!inventory || inventory.items.length === 0) {
    return (
      <Card className="glow-accent">
        <CardContent className="py-12 text-center">
          <Layers className="w-12 h-12 mx-auto text-muted-foreground mb-4" />
          <p className="text-muted-foreground">
            No cards in your collection yet. Import cards to see them in binder view.
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="grid grid-cols-5 sm:grid-cols-6 md:grid-cols-8 lg:grid-cols-10 gap-2">
      {inventory.items.map((item) => (
        <div
          key={item.id}
          className="aspect-[63/88] rounded overflow-hidden bg-secondary relative group cursor-pointer"
        >
          {item.card_image_url ? (
            <img
              src={item.card_image_url}
              alt={item.card_name}
              className="w-full h-full object-cover transition-transform group-hover:scale-105"
            />
          ) : (
            <div className="w-full h-full flex items-center justify-center">
              <Package className="w-6 h-6 text-muted-foreground" />
            </div>
          )}
          {item.quantity > 1 && (
            <Badge className="absolute top-1 right-1 text-[10px] px-1.5 py-0">
              x{item.quantity}
            </Badge>
          )}
          {item.is_foil && (
            <div className="absolute bottom-0 left-0 right-0 h-1 bg-gradient-to-r from-[rgb(var(--foil-1))] via-[rgb(var(--foil-2))] to-[rgb(var(--foil-3))]" />
          )}
        </div>
      ))}
    </div>
  );
}

function MilestoneItem({ milestone }: { milestone: Milestone }) {
  const formattedDate = new Date(milestone.achieved_at).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });

  return (
    <div className="flex items-center gap-3 p-3 rounded-lg bg-[rgb(var(--success))]/10 border border-[rgb(var(--success))]/20">
      <CheckCircle className="w-5 h-5 text-[rgb(var(--success))] shrink-0" />
      <div className="flex-1 min-w-0">
        <p className="font-medium text-foreground">{milestone.name}</p>
        {milestone.description && (
          <p className="text-sm text-muted-foreground">{milestone.description}</p>
        )}
      </div>
      <Badge variant="outline" className="shrink-0">
        {formattedDate}
      </Badge>
    </div>
  );
}

function StatsView({ stats }: { stats: CollectionStats | undefined }) {
  const { data: milestones, isLoading: milestonesLoading } = useQuery({
    queryKey: ['milestones'],
    queryFn: getMilestones,
  });

  // Calculate average completion if we have sets data
  const avgCompletion = stats?.top_set_completion
    ? Math.round(Number(stats.top_set_completion))
    : 0;

  return (
    <div className="space-y-6">
      {/* Summary Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card className="glow-accent">
          <CardContent className="p-4 text-center">
            <p className="text-3xl font-bold text-foreground">
              {stats?.total_cards.toLocaleString() ?? '-'}
            </p>
            <p className="text-sm text-muted-foreground">Total Cards</p>
          </CardContent>
        </Card>
        <Card className="glow-accent">
          <CardContent className="p-4 text-center">
            <p className="text-3xl font-bold text-foreground">
              {stats?.sets_started ?? '-'}
            </p>
            <p className="text-sm text-muted-foreground">Sets Started</p>
          </CardContent>
        </Card>
        <Card className="glow-accent">
          <CardContent className="p-4 text-center">
            <p className="text-3xl font-bold text-[rgb(var(--success))]">
              {stats ? formatCurrency(Number(stats.total_value)) : '-'}
            </p>
            <p className="text-sm text-muted-foreground">Total Value</p>
          </CardContent>
        </Card>
        <Card className="glow-accent">
          <CardContent className="p-4 text-center">
            <p className="text-3xl font-bold text-[rgb(var(--accent))]">
              {stats?.sets_completed ?? 0}
            </p>
            <p className="text-sm text-muted-foreground">Sets Completed</p>
          </CardContent>
        </Card>
      </div>

      {/* Milestones */}
      <Card className="glow-accent">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Trophy className="w-5 h-5 text-[rgb(var(--magic-gold))]" />
            Collection Milestones
          </CardTitle>
        </CardHeader>
        <CardContent>
          {milestonesLoading ? (
            <div className="space-y-3">
              {Array.from({ length: 3 }).map((_, i) => (
                <Skeleton key={i} className="h-16 w-full" />
              ))}
            </div>
          ) : milestones && milestones.items.length > 0 ? (
            <div className="space-y-3">
              {milestones.items.map((milestone) => (
                <MilestoneItem key={milestone.id} milestone={milestone} />
              ))}
            </div>
          ) : (
            <div className="text-center py-8">
              <Circle className="w-12 h-12 mx-auto text-muted-foreground mb-4" />
              <p className="text-muted-foreground">
                No milestones achieved yet. Keep collecting!
              </p>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Additional Stats */}
      <Card className="glow-accent">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <BarChart3 className="w-5 h-5 text-[rgb(var(--accent))]" />
            Collection Summary
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <div className="flex items-center justify-between p-3 bg-secondary/50 rounded-lg">
              <span className="text-muted-foreground">Unique Cards</span>
              <span className="font-medium text-foreground">
                {stats?.unique_cards.toLocaleString() ?? '-'}
              </span>
            </div>
            {stats?.top_set_code && (
              <div className="flex items-center justify-between p-3 bg-secondary/50 rounded-lg">
                <span className="text-muted-foreground">Top Set</span>
                <span className="font-medium text-foreground">
                  {stats.top_set_code.toUpperCase()} ({avgCompletion}%)
                </span>
              </div>
            )}
            <div className="flex items-center justify-between p-3 bg-secondary/50 rounded-lg">
              <span className="text-muted-foreground">Sets Completed</span>
              <span className="font-medium text-[rgb(var(--success))]">
                {stats?.sets_completed ?? 0}
              </span>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

export default function CollectionPage() {
  const [activeTab, setActiveTab] = useState<TabType>('sets');
  const queryClient = useQueryClient();

  // Fetch collection stats
  const { data: stats, isLoading: statsLoading, error: statsError } = useQuery({
    queryKey: ['collectionStats'],
    queryFn: getCollectionStats,
  });

  // Refresh mutation
  const refreshMutation = useMutation({
    mutationFn: refreshCollectionStats,
    onSuccess: () => {
      // Invalidate all collection-related queries
      queryClient.invalidateQueries({ queryKey: ['collectionStats'] });
      queryClient.invalidateQueries({ queryKey: ['setCompletions'] });
      queryClient.invalidateQueries({ queryKey: ['milestones'] });
    },
  });

  const tabs = [
    { id: 'sets' as const, label: 'Set Progress', icon: Package },
    { id: 'binder' as const, label: 'Binder View', icon: LayoutGrid },
    { id: 'stats' as const, label: 'Stats', icon: BarChart3 },
  ];

  return (
    <div className="space-y-6 animate-in">
      <PageHeader
        title="My Collection"
        subtitle="Track your set completion and collection milestones"
      >
        <div className="flex items-center gap-2">
          {stats?.is_stale && (
            <Badge variant="outline" className="text-[rgb(var(--warning))]">
              Updating...
            </Badge>
          )}
          <Button
            variant="secondary"
            size="sm"
            className="glow-accent"
            onClick={() => refreshMutation.mutate()}
            disabled={refreshMutation.isPending}
          >
            <RefreshCw className={cn(
              "w-4 h-4 mr-1",
              refreshMutation.isPending && "animate-spin"
            )} />
            Refresh Stats
          </Button>
          <Button variant="secondary" size="sm" className="glow-accent">
            <TrendingUp className="w-4 h-4 mr-1" />
            Value History
          </Button>
        </div>
      </PageHeader>

      {/* Stats Overview Bar */}
      {!statsLoading && stats && (
        <div className="flex items-center gap-4 text-sm text-muted-foreground bg-secondary/30 rounded-lg p-3">
          <span>
            <strong className="text-foreground">{stats.total_cards.toLocaleString()}</strong> cards
          </span>
          <span className="text-border">|</span>
          <span>
            <strong className="text-foreground">{stats.unique_cards.toLocaleString()}</strong> unique
          </span>
          <span className="text-border">|</span>
          <span>
            <strong className="text-[rgb(var(--success))]">{formatCurrency(Number(stats.total_value))}</strong> value
          </span>
          <span className="text-border">|</span>
          <span>
            <strong className="text-foreground">{stats.sets_started}</strong> sets started
          </span>
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-2 border-b border-border">
        {tabs.map((tab) => {
          const TabIcon = tab.icon;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={cn(
                'flex items-center gap-2 px-4 py-3 text-sm font-medium transition-colors border-b-2 -mb-[2px]',
                activeTab === tab.id
                  ? 'text-[rgb(var(--accent))] border-[rgb(var(--accent))]'
                  : 'text-muted-foreground border-transparent hover:text-foreground'
              )}
            >
              <TabIcon className="w-4 h-4" />
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* Tab Content */}
      {activeTab === 'sets' && <SetsView />}

      {activeTab === 'binder' && <BinderView />}

      {activeTab === 'stats' && <StatsView stats={stats} />}
    </div>
  );
}
