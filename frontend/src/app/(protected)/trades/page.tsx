'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import {
  Plus,
  ArrowLeftRight,
  Loader2,
  AlertCircle,
  Inbox,
  Send,
  CheckCircle,
  XCircle,
} from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { PageHeader } from '@/components/ornate/page-header';
import { TradeProposalCard } from '@/components/trades/TradeProposalCard';
import { getTrades, getTradeStats, ApiError } from '@/lib/api';
import { formatCurrency } from '@/lib/utils';
import { useAuth } from '@/contexts/AuthContext';
import type { TradeProposal, TradeStats, TradeListResponse } from '@/types';

const ITEMS_PER_PAGE = 12;

type TabValue = 'all' | 'received' | 'sent' | 'completed' | 'cancelled';

interface TabConfig {
  value: TabValue;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  getParams: () => { status?: string; direction?: 'sent' | 'received' | 'all' };
}

const tabs: TabConfig[] = [
  {
    value: 'all',
    label: 'All',
    icon: ArrowLeftRight,
    getParams: () => ({ direction: 'all' }),
  },
  {
    value: 'received',
    label: 'Received',
    icon: Inbox,
    getParams: () => ({ direction: 'received' }),
  },
  {
    value: 'sent',
    label: 'Sent',
    icon: Send,
    getParams: () => ({ direction: 'sent' }),
  },
  {
    value: 'completed',
    label: 'Completed',
    icon: CheckCircle,
    getParams: () => ({ status: 'completed' }),
  },
  {
    value: 'cancelled',
    label: 'Cancelled',
    icon: XCircle,
    getParams: () => ({ status: 'cancelled' }),
  },
];

function NewTradeButton() {
  const router = useRouter();

  return (
    <Button
      className="gradient-arcane text-white glow-accent"
      onClick={() => router.push('/trades/new')}
    >
      <Plus className="w-4 h-4 mr-1" />
      New Trade
    </Button>
  );
}

interface StatsCardProps {
  label: string;
  value: number | string;
  highlight?: boolean;
}

function StatsCard({ label, value, highlight }: StatsCardProps) {
  return (
    <Card className="glow-accent">
      <CardContent className="p-4 text-center">
        <p
          className={`text-3xl font-bold ${
            highlight
              ? 'text-[rgb(var(--accent))]'
              : 'text-foreground'
          }`}
        >
          {value}
        </p>
        <p className="text-sm text-muted-foreground">{label}</p>
      </CardContent>
    </Card>
  );
}

function EmptyState({ tab }: { tab: TabValue }) {
  const messages: Record<TabValue, string> = {
    all: 'No trade proposals yet. Start trading with other collectors!',
    received: 'No incoming trade proposals.',
    sent: 'You haven\'t sent any trade proposals yet.',
    completed: 'No completed trades yet.',
    cancelled: 'No cancelled trades.',
  };

  return (
    <Card className="glow-accent">
      <CardContent className="py-12 text-center">
        <ArrowLeftRight className="w-12 h-12 mx-auto text-muted-foreground mb-4" />
        <p className="text-muted-foreground mb-4">{messages[tab]}</p>
        {tab === 'all' && <NewTradeButton />}
      </CardContent>
    </Card>
  );
}

export default function TradesPage() {
  const router = useRouter();
  const { user } = useAuth();
  const [activeTab, setActiveTab] = useState<TabValue>('all');
  const [page, setPage] = useState(1);

  // Get the current tab configuration
  const currentTab = tabs.find((t) => t.value === activeTab) || tabs[0];
  const queryParams = currentTab.getParams();

  // Fetch trade stats
  const {
    data: stats,
    isLoading: statsLoading,
    error: statsError,
  } = useQuery<TradeStats, ApiError>({
    queryKey: ['tradeStats'],
    queryFn: getTradeStats,
  });

  // Fetch trades with pagination
  const {
    data: tradesData,
    isLoading: tradesLoading,
    error: tradesError,
  } = useQuery<TradeListResponse, ApiError>({
    queryKey: ['trades', activeTab, page],
    queryFn: () =>
      getTrades({
        ...queryParams,
        limit: ITEMS_PER_PAGE,
        offset: (page - 1) * ITEMS_PER_PAGE,
      }),
  });

  const handleTabChange = (value: string) => {
    setActiveTab(value as TabValue);
    setPage(1); // Reset to first page on tab change
  };

  const handleViewTradeDetails = (tradeId: number) => {
    router.push(`/trades/${tradeId}`);
  };

  const isLoading = statsLoading || tradesLoading;
  const error = statsError || tradesError;

  // Loading state
  if (isLoading && !tradesData) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Loader2 className="w-8 h-8 animate-spin text-[rgb(var(--accent))]" />
      </div>
    );
  }

  const trades = tradesData?.proposals ?? [];
  const totalTrades = tradesData?.total ?? 0;
  const totalPages = Math.ceil(totalTrades / ITEMS_PER_PAGE);

  return (
    <div className="space-y-6 animate-in">
      <PageHeader
        title="Trade Proposals"
        subtitle="Manage your card trades with other collectors"
      >
        <NewTradeButton />
      </PageHeader>

      {/* Error Alert */}
      {error && (
        <div className="p-4 rounded-lg bg-[rgb(var(--destructive))]/10 border border-[rgb(var(--destructive))]/20">
          <div className="flex items-center gap-2">
            <AlertCircle className="w-5 h-5 text-[rgb(var(--destructive))]" />
            <p className="text-[rgb(var(--destructive))]">
              {error.message || 'Failed to load trades'}
            </p>
          </div>
        </div>
      )}

      {/* Stats Row */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4">
        <StatsCard
          label="Total Trades"
          value={stats?.total_trades ?? 0}
        />
        <StatsCard
          label="Pending"
          value={stats?.pending_trades ?? 0}
          highlight
        />
        <StatsCard
          label="Completed"
          value={stats?.completed_trades ?? 0}
        />
        <StatsCard
          label="Total Value"
          value={formatCurrency(stats?.total_value_traded ?? 0)}
        />
        <StatsCard
          label="Avg Trade Value"
          value={formatCurrency(stats?.average_trade_value ?? 0)}
        />
      </div>

      {/* Tabs */}
      <Tabs value={activeTab} onValueChange={handleTabChange}>
        <TabsList className="w-full sm:w-auto grid grid-cols-5 sm:inline-flex">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            return (
              <TabsTrigger
                key={tab.value}
                value={tab.value}
                className="gap-1.5"
              >
                <Icon className="w-4 h-4 hidden sm:inline" />
                <span>{tab.label}</span>
              </TabsTrigger>
            );
          })}
        </TabsList>

        {/* Tab Content */}
        {tabs.map((tab) => (
          <TabsContent key={tab.value} value={tab.value}>
            {trades.length === 0 ? (
              <EmptyState tab={tab.value} />
            ) : (
              <div className="space-y-4">
                {/* Trade Cards Grid */}
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {trades.map((trade: TradeProposal) => (
                    <TradeProposalCard
                      key={trade.id}
                      proposal={trade}
                      currentUserId={user?.id ?? 0}
                      onViewDetails={() => handleViewTradeDetails(trade.id)}
                    />
                  ))}
                </div>

                {/* Pagination */}
                {totalPages > 1 && (
                  <div className="flex justify-center gap-2 pt-4">
                    <Button
                      variant="secondary"
                      disabled={page === 1}
                      onClick={() => setPage((p) => p - 1)}
                    >
                      Previous
                    </Button>
                    <span className="flex items-center px-4 text-sm text-muted-foreground">
                      Page {page} of {totalPages}
                    </span>
                    <Button
                      variant="secondary"
                      disabled={page >= totalPages}
                      onClick={() => setPage((p) => p + 1)}
                    >
                      Next
                    </Button>
                  </div>
                )}
              </div>
            )}
          </TabsContent>
        ))}
      </Tabs>
    </div>
  );
}
