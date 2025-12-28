'use client';

import React, { useState } from 'react';
import {
  Lightbulb,
  Bell,
  TrendingUp,
  TrendingDown,
  AlertTriangle,
  Zap,
  BookOpen,
  Filter,
  Eye,
  EyeOff,
  ChevronRight,
  Clock,
  DollarSign,
  Target,
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { PageHeader } from '@/components/ornate/page-header';
import { PriceChange } from '@/components/ornate/price-change';
import { formatCurrency, cn } from '@/lib/utils';

type InsightType = 'alert' | 'opportunity' | 'educational';
type InsightPriority = 'critical' | 'high' | 'medium' | 'low';

interface Insight {
  id: number;
  type: InsightType;
  priority: InsightPriority;
  title: string;
  description: string;
  cardName?: string;
  setCode?: string;
  currentPrice?: number;
  priceChange?: number;
  action?: string;
  timestamp: string;
  read: boolean;
}

// Mock insights data
const mockInsights: Insight[] = [
  {
    id: 1,
    type: 'alert',
    priority: 'critical',
    title: 'Significant Price Drop Detected',
    description: 'Force of Will has dropped 15% in the last 24 hours. Consider selling if this is in your inventory.',
    cardName: 'Force of Will',
    setCode: 'ALL',
    currentPrice: 76.50,
    priceChange: -15.2,
    action: 'Review Position',
    timestamp: '2 hours ago',
    read: false,
  },
  {
    id: 2,
    type: 'opportunity',
    priority: 'high',
    title: 'Buy Window Opening',
    description: 'Ragavan has reached your target price of $45. This may be a good time to acquire.',
    cardName: 'Ragavan, Nimble Pilferer',
    setCode: 'MH2',
    currentPrice: 44.99,
    priceChange: -8.5,
    action: 'Buy on TCGPlayer',
    timestamp: '4 hours ago',
    read: false,
  },
  {
    id: 3,
    type: 'alert',
    priority: 'high',
    title: 'Portfolio Alert: Spike Detected',
    description: 'The One Ring in your inventory spiked 22% following Modern tournament results.',
    cardName: 'The One Ring',
    setCode: 'LTR',
    currentPrice: 82.50,
    priceChange: 22.3,
    action: 'Consider Selling',
    timestamp: '6 hours ago',
    read: true,
  },
  {
    id: 4,
    type: 'opportunity',
    priority: 'medium',
    title: 'Undervalued Card Alert',
    description: 'Seasoned Dungeoneer is seeing increased Commander play but price hasn\'t moved yet.',
    cardName: 'Seasoned Dungeoneer',
    setCode: 'CLB',
    currentPrice: 12.50,
    priceChange: 0.5,
    action: 'Add to Watch List',
    timestamp: '1 day ago',
    read: true,
  },
  {
    id: 5,
    type: 'educational',
    priority: 'low',
    title: 'Market Insight: Standard Rotation',
    description: 'Standard rotation is approaching in 3 months. Consider reviewing cards rotating out of your portfolio.',
    action: 'Learn More',
    timestamp: '2 days ago',
    read: true,
  },
  {
    id: 6,
    type: 'educational',
    priority: 'low',
    title: 'Tip: Optimize Your Collection',
    description: 'You have 12 cards worth under $1 each. Consider trading up to consolidate value.',
    action: 'View Suggestions',
    timestamp: '3 days ago',
    read: true,
  },
];

const typeIcons = {
  alert: AlertTriangle,
  opportunity: Target,
  educational: BookOpen,
};

const typeColors = {
  alert: 'text-[rgb(var(--destructive))]',
  opportunity: 'text-[rgb(var(--success))]',
  educational: 'text-[rgb(var(--accent))]',
};

const priorityStyles = {
  critical: {
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

function InsightCard({ insight }: { insight: Insight }) {
  const Icon = typeIcons[insight.type];

  return (
    <Card className={cn(
      'glow-accent border-l-4 transition-all hover:border-[rgb(var(--accent))]/30',
      priorityStyles[insight.priority].border,
      !insight.read && 'bg-[rgb(var(--accent))]/5'
    )}>
      <CardContent className="p-4">
        <div className="flex gap-4">
          {/* Icon */}
          <div className={cn(
            'w-10 h-10 rounded-lg flex items-center justify-center shrink-0',
            insight.type === 'alert' && 'bg-[rgb(var(--destructive))]/10',
            insight.type === 'opportunity' && 'bg-[rgb(var(--success))]/10',
            insight.type === 'educational' && 'bg-[rgb(var(--accent))]/10'
          )}>
            <Icon className={cn('w-5 h-5', typeColors[insight.type])} />
          </div>

          {/* Content */}
          <div className="flex-1 min-w-0">
            <div className="flex items-start justify-between gap-2">
              <div>
                <div className="flex items-center gap-2 mb-1">
                  <h3 className={cn(
                    'font-heading font-medium',
                    !insight.read ? 'text-foreground' : 'text-muted-foreground'
                  )}>
                    {insight.title}
                  </h3>
                  {!insight.read && (
                    <span className="w-2 h-2 rounded-full bg-[rgb(var(--accent))]" />
                  )}
                </div>
                <p className="text-sm text-muted-foreground">{insight.description}</p>
              </div>
              <Badge className={priorityStyles[insight.priority].badge}>
                {insight.priority}
              </Badge>
            </div>

            {/* Card Info (if applicable) */}
            {insight.cardName && (
              <div className="mt-3 flex items-center gap-4 p-2 rounded-lg bg-secondary/50">
                <div className="flex-1">
                  <p className="font-medium text-foreground">{insight.cardName}</p>
                  <p className="text-xs text-muted-foreground">{insight.setCode}</p>
                </div>
                {insight.currentPrice !== undefined && (
                  <div className="text-right">
                    <p className="font-medium text-foreground">
                      {formatCurrency(insight.currentPrice)}
                    </p>
                    {insight.priceChange !== undefined && (
                      <PriceChange value={insight.priceChange} format="percent" size="sm" />
                    )}
                  </div>
                )}
              </div>
            )}

            {/* Footer */}
            <div className="mt-3 flex items-center justify-between">
              <span className="text-xs text-muted-foreground flex items-center gap-1">
                <Clock className="w-3 h-3" />
                {insight.timestamp}
              </span>
              {insight.action && (
                <Button variant="ghost" size="sm" className="text-[rgb(var(--accent))] h-7">
                  {insight.action}
                  <ChevronRight className="w-4 h-4 ml-1" />
                </Button>
              )}
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

export default function InsightsPage() {
  const [filter, setFilter] = useState<'all' | InsightType>('all');
  const [showUnreadOnly, setShowUnreadOnly] = useState(false);

  const filteredInsights = mockInsights.filter(insight => {
    if (filter !== 'all' && insight.type !== filter) return false;
    if (showUnreadOnly && insight.read) return false;
    return true;
  });

  const unreadCount = mockInsights.filter(i => !i.read).length;
  const alertCount = mockInsights.filter(i => i.type === 'alert').length;
  const opportunityCount = mockInsights.filter(i => i.type === 'opportunity').length;

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
        <Button variant="secondary" size="sm" className="glow-accent">
          <Bell className="w-4 h-4 mr-1" />
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
            <p className="text-2xl font-bold text-foreground">{mockInsights.length}</p>
            <p className="text-sm text-muted-foreground">Total Insights</p>
          </CardContent>
        </Card>
        <Card className={cn(
          'glow-accent cursor-pointer transition-all',
          filter === 'alert' && 'ring-2 ring-[rgb(var(--destructive))]'
        )} onClick={() => setFilter('alert')}>
          <CardContent className="p-4 text-center">
            <AlertTriangle className="w-6 h-6 mx-auto text-[rgb(var(--destructive))] mb-2" />
            <p className="text-2xl font-bold text-[rgb(var(--destructive))]">{alertCount}</p>
            <p className="text-sm text-muted-foreground">Alerts</p>
          </CardContent>
        </Card>
        <Card className={cn(
          'glow-accent cursor-pointer transition-all',
          filter === 'opportunity' && 'ring-2 ring-[rgb(var(--success))]'
        )} onClick={() => setFilter('opportunity')}>
          <CardContent className="p-4 text-center">
            <Target className="w-6 h-6 mx-auto text-[rgb(var(--success))] mb-2" />
            <p className="text-2xl font-bold text-[rgb(var(--success))]">{opportunityCount}</p>
            <p className="text-sm text-muted-foreground">Opportunities</p>
          </CardContent>
        </Card>
        <Card className="glow-accent">
          <CardContent className="p-4 text-center">
            <Bell className="w-6 h-6 mx-auto text-[rgb(var(--magic-gold))] mb-2" />
            <p className="text-2xl font-bold text-[rgb(var(--magic-gold))]">{unreadCount}</p>
            <p className="text-sm text-muted-foreground">Unread</p>
          </CardContent>
        </Card>
      </div>

      {/* Filter Pills */}
      <div className="flex items-center gap-2">
        <Filter className="w-4 h-4 text-muted-foreground" />
        <span className="text-sm text-muted-foreground">Filter:</span>
        {(['all', 'alert', 'opportunity', 'educational'] as const).map((type) => (
          <Button
            key={type}
            variant={filter === type ? 'default' : 'secondary'}
            size="sm"
            onClick={() => setFilter(type)}
            className={filter === type ? 'gradient-arcane text-white' : ''}
          >
            {type === 'all' ? 'All' : type.charAt(0).toUpperCase() + type.slice(1) + 's'}
          </Button>
        ))}
      </div>

      {/* Insights List */}
      {filteredInsights.length === 0 ? (
        <Card className="glow-accent">
          <CardContent className="py-12 text-center">
            <Lightbulb className="w-12 h-12 mx-auto text-muted-foreground mb-4" />
            <p className="text-muted-foreground">
              {showUnreadOnly
                ? 'No unread insights. You\'re all caught up!'
                : 'No insights match your current filter.'}
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-4">
          {filteredInsights.map((insight) => (
            <InsightCard key={insight.id} insight={insight} />
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
              Check our guides on understanding price movements, rotation impacts, and meta shifts.
            </p>
          </div>
          <Button variant="secondary" size="sm" className="shrink-0 ml-auto">
            View Guides
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
