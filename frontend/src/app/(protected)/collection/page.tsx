'use client';

import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  Package,
  LayoutGrid,
  BarChart3,
  Trophy,
  TrendingUp,
  CheckCircle,
  Circle,
  Layers,
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { Badge } from '@/components/ui/badge';
import { PageHeader } from '@/components/ornate/page-header';
import { getInventory } from '@/lib/api';
import { formatCurrency, cn } from '@/lib/utils';

type TabType = 'sets' | 'binder' | 'stats';

// Mock data for set completion (until backend API exists)
const mockSetProgress = [
  { code: 'OTJ', name: 'Outlaws of Thunder Junction', owned: 187, total: 276, value: 142.50 },
  { code: 'MKM', name: 'Murders at Karlov Manor', owned: 156, total: 302, value: 98.75 },
  { code: 'LCI', name: 'The Lost Caverns of Ixalan', owned: 203, total: 291, value: 187.30 },
  { code: 'WOE', name: 'Wilds of Eldraine', owned: 178, total: 266, value: 134.20 },
  { code: 'MOM', name: "March of the Machine", owned: 234, total: 381, value: 245.80 },
  { code: 'ONE', name: 'Phyrexia: All Will Be One', owned: 201, total: 271, value: 167.40 },
];

const mockMilestones = [
  { title: 'First Rare', description: 'Collected your first rare card', achieved: true, date: '2024-01-15' },
  { title: 'Set Starter', description: 'Own 50% of any set', achieved: true, date: '2024-02-20' },
  { title: 'Mythic Hunter', description: 'Collect 10 mythic rares', achieved: true, date: '2024-03-10' },
  { title: 'Complete Set', description: 'Own 100% of any set', achieved: false },
  { title: 'Value Collector', description: 'Portfolio value exceeds $1,000', achieved: false },
];

function SetProgressCard({ set }: { set: typeof mockSetProgress[0] }) {
  const completionPct = Math.round((set.owned / set.total) * 100);

  return (
    <Card className="glow-accent hover:border-[rgb(var(--accent))]/30 transition-colors">
      <CardContent className="p-4">
        <div className="flex items-start justify-between mb-3">
          <div>
            <Badge variant="outline" className="mb-1 text-xs">
              {set.code}
            </Badge>
            <h3 className="font-heading text-foreground font-medium">{set.name}</h3>
          </div>
          <div className="text-right">
            <p className="text-lg font-bold text-[rgb(var(--success))]">
              {formatCurrency(set.value)}
            </p>
            <p className="text-xs text-muted-foreground">set value</p>
          </div>
        </div>

        {/* Progress bar */}
        <div className="space-y-2">
          <div className="flex justify-between text-sm">
            <span className="text-muted-foreground">
              {set.owned} / {set.total} cards
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

function StatsView() {
  return (
    <div className="space-y-6">
      {/* Summary Stats */}
      <div className="grid grid-cols-4 gap-4">
        <Card className="glow-accent">
          <CardContent className="p-4 text-center">
            <p className="text-3xl font-bold text-foreground">1,159</p>
            <p className="text-sm text-muted-foreground">Total Cards</p>
          </CardContent>
        </Card>
        <Card className="glow-accent">
          <CardContent className="p-4 text-center">
            <p className="text-3xl font-bold text-foreground">6</p>
            <p className="text-sm text-muted-foreground">Sets Started</p>
          </CardContent>
        </Card>
        <Card className="glow-accent">
          <CardContent className="p-4 text-center">
            <p className="text-3xl font-bold text-[rgb(var(--success))]">$975.95</p>
            <p className="text-sm text-muted-foreground">Total Value</p>
          </CardContent>
        </Card>
        <Card className="glow-accent">
          <CardContent className="p-4 text-center">
            <p className="text-3xl font-bold text-[rgb(var(--accent))]">61%</p>
            <p className="text-sm text-muted-foreground">Avg Completion</p>
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
          <div className="space-y-3">
            {mockMilestones.map((milestone, i) => (
              <div
                key={i}
                className={cn(
                  'flex items-center gap-3 p-3 rounded-lg',
                  milestone.achieved
                    ? 'bg-[rgb(var(--success))]/10 border border-[rgb(var(--success))]/20'
                    : 'bg-secondary/50'
                )}
              >
                {milestone.achieved ? (
                  <CheckCircle className="w-5 h-5 text-[rgb(var(--success))] shrink-0" />
                ) : (
                  <Circle className="w-5 h-5 text-muted-foreground shrink-0" />
                )}
                <div className="flex-1 min-w-0">
                  <p className={cn(
                    'font-medium',
                    milestone.achieved ? 'text-foreground' : 'text-muted-foreground'
                  )}>
                    {milestone.title}
                  </p>
                  <p className="text-sm text-muted-foreground">{milestone.description}</p>
                </div>
                {milestone.achieved && milestone.date && (
                  <Badge variant="outline" className="shrink-0">
                    {milestone.date}
                  </Badge>
                )}
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Rarity Distribution */}
      <Card className="glow-accent">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <BarChart3 className="w-5 h-5 text-[rgb(var(--accent))]" />
            Rarity Distribution
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {[
              { rarity: 'Mythic Rare', count: 47, color: 'mythic-orange' },
              { rarity: 'Rare', count: 234, color: 'magic-gold' },
              { rarity: 'Uncommon', count: 412, color: 'silver' },
              { rarity: 'Common', count: 466, color: 'border' },
            ].map(({ rarity, count, color }) => (
              <div key={rarity} className="flex items-center gap-3">
                <span className="w-24 text-sm text-muted-foreground">{rarity}</span>
                <div className="flex-1 h-6 bg-secondary rounded-full overflow-hidden">
                  <div
                    className="h-full rounded-full"
                    style={{
                      width: `${(count / 466) * 100}%`,
                      backgroundColor: `rgb(var(--${color}))`,
                    }}
                  />
                </div>
                <span className="w-12 text-sm text-foreground text-right">{count}</span>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

export default function CollectionPage() {
  const [activeTab, setActiveTab] = useState<TabType>('sets');

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
        <Button variant="secondary" size="sm" className="glow-accent">
          <TrendingUp className="w-4 h-4 mr-1" />
          Value History
        </Button>
      </PageHeader>

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
      {activeTab === 'sets' && (
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
          {mockSetProgress.map((set) => (
            <SetProgressCard key={set.code} set={set} />
          ))}
        </div>
      )}

      {activeTab === 'binder' && <BinderView />}

      {activeTab === 'stats' && <StatsView />}
    </div>
  );
}
