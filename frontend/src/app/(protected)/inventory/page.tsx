'use client';

import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Package,
  Upload,
  Download,
  ChevronDown,
  TrendingUp,
  TrendingDown,
  AlertTriangle,
  RefreshCw,
  Zap,
  DollarSign,
  BarChart3,
  Filter,
  X,
} from 'lucide-react';
import { MarketIndexChart } from '@/components/charts/MarketIndexChart';
import {
  getInventoryMarketIndex,
  getInventoryTopMovers,
} from '@/lib/api';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { LoadingPage, Loading } from '@/components/ui/Loading';
import { SearchBar } from '@/components/cards/SearchBar';
import { InventoryImportModal } from '@/components/inventory/InventoryImportModal';
import { InventoryItemCard } from '@/components/inventory/InventoryItemCard';
import { InventoryRecommendationCard } from '@/components/inventory/InventoryRecommendationCard';
import { PageHeader } from '@/components/ornate/page-header';
import { PriceChange } from '@/components/ornate/price-change';
import {
  getInventory,
  getInventoryAnalytics,
  getInventoryRecommendations,
  refreshInventoryValuations,
  runInventoryRecommendations,
  deleteInventoryItem,
  updateInventoryItem,
  exportInventory,
} from '@/lib/api';
import { formatCurrency, cn } from '@/lib/utils';
import type { InventoryCondition } from '@/types';

type TabType = 'overview' | 'items' | 'recommendations';

function InventoryPageContent(): JSX.Element {
  const [activeTab, setActiveTab] = useState<TabType>('overview');
  const [isImportOpen, setIsImportOpen] = useState(false);
  const [page, setPage] = useState(1);
  const [recPage, setRecPage] = useState(1);
  const [marketIndexRange, setMarketIndexRange] = useState<'7d' | '30d' | '90d' | '1y'>('7d');
  const [marketIndexFoil, setMarketIndexFoil] = useState<boolean | undefined>(undefined);

  // Search and filter state
  const [searchQuery, setSearchQuery] = useState('');
  const [searchKey, setSearchKey] = useState(0); // Key to reset SearchBar
  const [filterFoil, setFilterFoil] = useState<boolean | undefined>(undefined);
  const [filterCondition, setFilterCondition] = useState<InventoryCondition | undefined>(undefined);

  // Export dropdown state
  const [isExportDropdownOpen, setIsExportDropdownOpen] = useState(false);

  const queryClient = useQueryClient();

  const { data: inventoryData, isLoading: inventoryLoading } = useQuery({
    queryKey: ['inventory', page, searchQuery, filterFoil, filterCondition],
    queryFn: () => getInventory({
      page,
      pageSize: 20,
      search: searchQuery || undefined,
      isFoil: filterFoil,
      condition: filterCondition,
    }),
    enabled: true,
  });

  const { data: analytics, isLoading: analyticsLoading } = useQuery({
    queryKey: ['inventory-analytics'],
    queryFn: getInventoryAnalytics,
    refetchInterval: 15 * 60 * 1000,
  });

  const { data: recommendations, isLoading: recsLoading } = useQuery({
    queryKey: ['inventory-recommendations', recPage],
    queryFn: () => getInventoryRecommendations({ page: recPage, pageSize: 20 }),
    refetchInterval: 15 * 60 * 1000,
  });

  const { data: inventoryMarketIndex, isLoading: indexLoading } = useQuery({
    queryKey: ['inventory-market-index', marketIndexRange, marketIndexFoil],
    queryFn: () => getInventoryMarketIndex(marketIndexRange, marketIndexFoil),
    refetchInterval: 2 * 60 * 1000,
    refetchIntervalInBackground: true,
  });

  const { data: inventoryTopMovers, isLoading: moversLoading } = useQuery({
    queryKey: ['inventory-top-movers', '24h'],
    queryFn: () => getInventoryTopMovers('24h'),
    refetchInterval: 2 * 60 * 1000,
    refetchIntervalInBackground: true,
  });

  const refreshMutation = useMutation({
    mutationFn: refreshInventoryValuations,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['inventory'] });
      queryClient.invalidateQueries({ queryKey: ['inventory-analytics'] });
    },
  });

  const runRecsMutation = useMutation({
    mutationFn: () => runInventoryRecommendations(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['inventory-recommendations'] });
      queryClient.invalidateQueries({ queryKey: ['inventory-analytics'] });
    },
  });

  const deleteItemMutation = useMutation({
    mutationFn: deleteInventoryItem,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['inventory'] });
      queryClient.invalidateQueries({ queryKey: ['inventory-analytics'] });
    },
  });

  const toggleFoilMutation = useMutation({
    mutationFn: ({ itemId, isFoil }: { itemId: number; isFoil: boolean }) =>
      updateInventoryItem(itemId, { is_foil: isFoil }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['inventory'] });
      queryClient.invalidateQueries({ queryKey: ['inventory-analytics'] });
    },
  });

  const exportMutation = useMutation({
    mutationFn: (format: 'csv' | 'txt' | 'cardtrader') => exportInventory(format),
  });

  const handleDelete = (itemId: number) => {
    deleteItemMutation.mutate(itemId);
  };

  const handleToggleFoil = (itemId: number, isFoil: boolean) => {
    toggleFoilMutation.mutate({ itemId, isFoil });
  };

  const handleExport = (format: 'csv' | 'txt' | 'cardtrader') => {
    exportMutation.mutate(format);
    setIsExportDropdownOpen(false);
  };

  const handleClearFilters = () => {
    setSearchQuery('');
    setSearchKey((k) => k + 1); // Reset SearchBar component
    setFilterFoil(undefined);
    setFilterCondition(undefined);
    setPage(1);
  };

  const isLoading = inventoryLoading || analyticsLoading;

  const tabs = [
    { id: 'overview' as const, label: 'Overview', icon: BarChart3 },
    { id: 'items' as const, label: 'All Items', icon: Package },
    { id: 'recommendations' as const, label: 'Recommendations', icon: Zap },
  ];

  const conditionLabels: Record<string, string> = {
    MINT: 'Mint',
    NEAR_MINT: 'Near Mint',
    LIGHTLY_PLAYED: 'Lightly Played',
    MODERATELY_PLAYED: 'Mod. Played',
    HEAVILY_PLAYED: 'Heavily Played',
    DAMAGED: 'Damaged',
  };

  return (
    <div className="space-y-6 animate-in">
      {/* Header */}
      <PageHeader
        title="My Inventory"
        subtitle="Track your collection with aggressive analytics and recommendations"
      >
        <Button
          variant="secondary"
          size="sm"
          onClick={() => refreshMutation.mutate()}
          disabled={refreshMutation.isPending}
          className="glow-accent"
        >
          {refreshMutation.isPending ? (
            <Loading size="sm" className="mr-1" />
          ) : (
            <RefreshCw className="w-4 h-4 mr-1" />
          )}
          Refresh Values
        </Button>
        <Button
          variant="secondary"
          size="sm"
          onClick={() => runRecsMutation.mutate()}
          disabled={runRecsMutation.isPending}
          className="glow-accent"
        >
          {runRecsMutation.isPending ? (
            <Loading size="sm" className="mr-1" />
          ) : (
            <Zap className="w-4 h-4 mr-1" />
          )}
          Run Analysis
        </Button>
        <Button
          size="sm"
          onClick={() => setIsImportOpen(true)}
          className="gradient-arcane text-white glow-accent"
        >
          <Upload className="w-4 h-4 mr-1" />
          Import Cards
        </Button>
        <div className="relative">
          <Button
            variant="secondary"
            size="sm"
            onClick={() => setIsExportDropdownOpen(!isExportDropdownOpen)}
            disabled={exportMutation.isPending}
            className="glow-accent"
          >
            {exportMutation.isPending ? (
              <Loading size="sm" className="mr-1" />
            ) : (
              <Download className="w-4 h-4 mr-1" />
            )}
            Export
            <ChevronDown className="w-4 h-4 ml-1" />
          </Button>
          {isExportDropdownOpen && (
            <>
              <div
                className="fixed inset-0 z-10"
                onClick={() => setIsExportDropdownOpen(false)}
              />
              <div className="absolute right-0 top-full mt-1 w-56 bg-card border border-border rounded-md shadow-lg z-20">
                <button
                  onClick={() => handleExport('cardtrader')}
                  className="w-full text-left px-4 py-2.5 text-sm hover:bg-secondary rounded-t-md flex items-center gap-2"
                >
                  <Download className="w-4 h-4" />
                  <div>
                    <div className="font-medium text-foreground">Export to CardTrader</div>
                    <div className="text-xs text-muted-foreground">CSV format for CardTrader import</div>
                  </div>
                </button>
                <button
                  onClick={() => handleExport('csv')}
                  className="w-full text-left px-4 py-2.5 text-sm hover:bg-secondary flex items-center gap-2"
                >
                  <Download className="w-4 h-4" />
                  <div>
                    <div className="font-medium text-foreground">Export as CSV</div>
                    <div className="text-xs text-muted-foreground">Standard CSV format</div>
                  </div>
                </button>
                <button
                  onClick={() => handleExport('txt')}
                  className="w-full text-left px-4 py-2.5 text-sm hover:bg-secondary rounded-b-md flex items-center gap-2"
                >
                  <Download className="w-4 h-4" />
                  <div>
                    <div className="font-medium text-foreground">Export as Plain Text</div>
                    <div className="text-xs text-muted-foreground">Simple text format</div>
                  </div>
                </button>
              </div>
            </>
          )}
        </div>
      </PageHeader>

      {/* Quick Stats */}
      {analytics && (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4">
          <Card className="bg-gradient-to-br from-[rgb(var(--magic-blue))]/10 to-[rgb(var(--magic-blue))]/5 border-[rgb(var(--magic-blue))]/20 glow-accent">
            <CardContent className="p-4">
              <div className="flex items-center gap-2 mb-2">
                <Package className="w-5 h-5 text-[rgb(var(--magic-blue))]" />
                <span className="text-sm text-muted-foreground">Total Cards</span>
              </div>
              <p className="text-2xl font-bold text-foreground">
                {analytics.total_quantity}
              </p>
              <p className="text-xs text-muted-foreground">
                {analytics.total_unique_cards} unique
              </p>
            </CardContent>
          </Card>

          <Card className="bg-gradient-to-br from-[rgb(var(--success))]/10 to-[rgb(var(--success))]/5 border-[rgb(var(--success))]/20 glow-accent">
            <CardContent className="p-4">
              <div className="flex items-center gap-2 mb-2">
                <DollarSign className="w-5 h-5 text-[rgb(var(--success))]" />
                <span className="text-sm text-muted-foreground">Total Value</span>
              </div>
              <p className="text-2xl font-bold text-foreground">
                {formatCurrency(analytics.total_current_value)}
              </p>
              <p className="text-xs text-muted-foreground">
                Cost: {formatCurrency(analytics.total_acquisition_cost)}
              </p>
            </CardContent>
          </Card>

          <Card className={cn(
            'glow-accent',
            analytics.total_profit_loss >= 0
              ? 'bg-gradient-to-br from-[rgb(var(--success))]/10 to-[rgb(var(--success))]/5 border-[rgb(var(--success))]/20'
              : 'bg-gradient-to-br from-[rgb(var(--destructive))]/10 to-[rgb(var(--destructive))]/5 border-[rgb(var(--destructive))]/20'
          )}>
            <CardContent className="p-4">
              <div className="flex items-center gap-2 mb-2">
                {analytics.total_profit_loss >= 0 ? (
                  <TrendingUp className="w-5 h-5 text-[rgb(var(--success))]" />
                ) : (
                  <TrendingDown className="w-5 h-5 text-[rgb(var(--destructive))]" />
                )}
                <span className="text-sm text-muted-foreground">Profit/Loss</span>
              </div>
              <p className={cn(
                'text-2xl font-bold',
                analytics.total_profit_loss >= 0 ? 'text-[rgb(var(--success))]' : 'text-[rgb(var(--destructive))]'
              )}>
                {analytics.total_profit_loss >= 0 ? '+' : ''}{formatCurrency(analytics.total_profit_loss)}
              </p>
              {analytics.profit_loss_pct !== null && analytics.profit_loss_pct !== undefined && (
                <PriceChange value={analytics.profit_loss_pct} format="percent" size="sm" showIcon={false} />
              )}
            </CardContent>
          </Card>

          <Card className="bg-gradient-to-br from-[rgb(var(--magic-gold))]/10 to-[rgb(var(--magic-gold))]/5 border-[rgb(var(--magic-gold))]/20 glow-accent">
            <CardContent className="p-4">
              <div className="flex items-center gap-2 mb-2">
                <Zap className="w-5 h-5 text-[rgb(var(--magic-gold))]" />
                <span className="text-sm text-muted-foreground">Sell Signals</span>
              </div>
              <p className="text-2xl font-bold text-foreground">
                {analytics.sell_recommendations}
              </p>
              <p className="text-xs text-muted-foreground">
                {analytics.hold_recommendations} holds
              </p>
            </CardContent>
          </Card>

          <Card className={cn(
            'glow-accent',
            analytics.critical_alerts > 0
              ? 'bg-gradient-to-br from-[rgb(var(--destructive))]/10 to-[rgb(var(--destructive))]/5 border-[rgb(var(--destructive))]/20'
              : 'bg-gradient-to-br from-[rgb(var(--muted))]/10 to-[rgb(var(--muted))]/5 border-[rgb(var(--border))]'
          )}>
            <CardContent className="p-4">
              <div className="flex items-center gap-2 mb-2">
                <AlertTriangle className={cn(
                  'w-5 h-5',
                  analytics.critical_alerts > 0 ? 'text-[rgb(var(--destructive))]' : 'text-muted-foreground'
                )} />
                <span className="text-sm text-muted-foreground">Critical Alerts</span>
              </div>
              <p className={cn(
                'text-2xl font-bold',
                analytics.critical_alerts > 0 ? 'text-[rgb(var(--destructive))]' : 'text-foreground'
              )}>
                {analytics.critical_alerts}
              </p>
              <p className="text-xs text-muted-foreground">
                Needs attention
              </p>
            </CardContent>
          </Card>
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
      {isLoading ? (
        <LoadingPage />
      ) : (
        <>
          {/* Overview Tab */}
          {activeTab === 'overview' && analytics && (
            <div className="space-y-6">
              {/* Inventory Market Index Chart */}
              {indexLoading && !inventoryMarketIndex ? (
                <Card>
                  <CardContent className="p-4">
                    <div className="h-64 animate-pulse bg-secondary rounded"></div>
                  </CardContent>
                </Card>
              ) : inventoryMarketIndex ? (
                <MarketIndexChart
                  data={inventoryMarketIndex}
                  title="Inventory Value Index"
                  onRangeChange={(range) => setMarketIndexRange(range)}
                  onFoilChange={(isFoil) => setMarketIndexFoil(isFoil)}
                  showFoilToggle={true}
                />
              ) : null}

              {/* Top Movers */}
              {moversLoading && !inventoryTopMovers ? (
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                  {[1, 2].map((i) => (
                    <Card key={i}>
                      <CardContent className="p-4">
                        <div className="h-64 animate-pulse bg-secondary rounded"></div>
                      </CardContent>
                    </Card>
                  ))}
                </div>
              ) : inventoryTopMovers ? (
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                  {/* Top Gainers */}
                  <Card className="glow-accent">
                    <CardContent className="p-4">
                      <div className="flex items-center gap-2 mb-4">
                        <TrendingUp className="w-5 h-5 text-[rgb(var(--success))]" />
                        <h3 className="font-semibold text-foreground">Top Gainers (24h)</h3>
                      </div>
                      <div className="space-y-3">
                        {inventoryTopMovers.gainers.length > 0 ? (
                          inventoryTopMovers.gainers.map((mover, index) => (
                            <div key={`gainer-${index}`} className="flex items-center justify-between p-2 rounded-lg bg-secondary/50 hover:bg-secondary transition-colors">
                              <div>
                                <p className="font-medium text-foreground">{mover.cardName}</p>
                                <p className="text-xs text-muted-foreground uppercase">{mover.setCode}</p>
                              </div>
                              <div className="text-right">
                                <p className="font-medium text-foreground">
                                  {formatCurrency(mover.currentPriceUsd)}
                                </p>
                                <PriceChange value={mover.changePct} format="percent" size="sm" />
                              </div>
                            </div>
                          ))
                        ) : (
                          <p className="text-sm text-muted-foreground text-center py-4">
                            No gainers to show
                          </p>
                        )}
                      </div>
                    </CardContent>
                  </Card>

                  {/* Top Losers */}
                  <Card className="glow-accent">
                    <CardContent className="p-4">
                      <div className="flex items-center gap-2 mb-4">
                        <TrendingDown className="w-5 h-5 text-[rgb(var(--destructive))]" />
                        <h3 className="font-semibold text-foreground">Top Losers (24h)</h3>
                      </div>
                      <div className="space-y-3">
                        {inventoryTopMovers.losers.length > 0 ? (
                          inventoryTopMovers.losers.map((mover, index) => (
                            <div key={`loser-${index}`} className="flex items-center justify-between p-2 rounded-lg bg-secondary/50 hover:bg-secondary transition-colors">
                              <div>
                                <p className="font-medium text-foreground">{mover.cardName}</p>
                                <p className="text-xs text-muted-foreground uppercase">{mover.setCode}</p>
                              </div>
                              <div className="text-right">
                                <p className="font-medium text-foreground">
                                  {formatCurrency(mover.currentPriceUsd)}
                                </p>
                                <PriceChange value={mover.changePct} format="percent" size="sm" />
                              </div>
                            </div>
                          ))
                        ) : (
                          <p className="text-sm text-muted-foreground text-center py-4">
                            No losers to show
                          </p>
                        )}
                      </div>
                    </CardContent>
                  </Card>
                </div>
              ) : null}

              {/* Analytics Cards */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
                {/* Value Distribution */}
                <Card className="glow-accent">
                  <CardContent className="p-4">
                    <div className="flex items-center gap-2 mb-4">
                      <BarChart3 className="w-5 h-5 text-[rgb(var(--magic-gold))]" />
                      <h3 className="font-semibold text-foreground">Value Distribution</h3>
                    </div>
                    <div className="space-y-3">
                      {Object.entries(analytics.value_distribution).map(([range, count]) => {
                        const maxCount = Math.max(...Object.values(analytics.value_distribution), 1);
                        const widthPercent = Math.max(5, (count / maxCount) * 100);
                        return (
                          <div key={range} className="flex items-center gap-3">
                            <span className="w-16 text-sm text-muted-foreground">{range}</span>
                            <div className="flex-1 h-6 bg-secondary rounded-full overflow-hidden">
                              <div
                                className="h-full gradient-arcane rounded-full"
                                style={{ width: `${widthPercent}%` }}
                              />
                            </div>
                            <span className="w-12 text-sm text-foreground text-right">{count}</span>
                          </div>
                        );
                      })}
                    </div>
                  </CardContent>
                </Card>

                {/* Condition Breakdown */}
                <Card className="glow-accent">
                  <CardContent className="p-4">
                    <div className="flex items-center gap-2 mb-4">
                      <Filter className="w-5 h-5 text-[rgb(var(--magic-blue))]" />
                      <h3 className="font-semibold text-foreground">Condition Breakdown</h3>
                    </div>
                    <div className="space-y-3">
                      {Object.entries(analytics.condition_breakdown).map(([condition, count]) => (
                        <div key={condition} className="flex items-center justify-between p-2 rounded-lg bg-secondary/50 hover:bg-secondary transition-colors">
                          <span className="text-sm text-foreground">
                            {conditionLabels[condition] || condition}
                          </span>
                          <span className="font-medium text-foreground">{count}</span>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              </div>
            </div>
          )}

          {/* Items Tab */}
          {activeTab === 'items' && inventoryData && (
            <div className="space-y-4">
              {/* Search and Filters */}
              <Card className="glow-accent">
                <CardContent className="p-4">
                  <div className="space-y-4">
                    {/* Search Bar */}
                    <SearchBar
                      key={searchKey}
                      value={searchQuery}
                      onSearch={(query) => {
                        setSearchQuery(query);
                        setPage(1);
                      }}
                      placeholder="Search by card name..."
                    />

                    {/* Filters */}
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-sm text-muted-foreground">Filters:</span>

                      {/* Foil Filter */}
                      <div className="flex items-center gap-1">
                        <Button
                          variant={filterFoil === undefined ? 'default' : 'secondary'}
                          size="sm"
                          onClick={() => setFilterFoil(undefined)}
                          className={filterFoil === undefined ? 'gradient-arcane text-white' : ''}
                        >
                          All
                        </Button>
                        <Button
                          variant={filterFoil === false ? 'default' : 'secondary'}
                          size="sm"
                          onClick={() => setFilterFoil(false)}
                          className={filterFoil === false ? 'gradient-arcane text-white' : ''}
                        >
                          Non-Foil
                        </Button>
                        <Button
                          variant={filterFoil === true ? 'default' : 'secondary'}
                          size="sm"
                          onClick={() => setFilterFoil(true)}
                          className={filterFoil === true ? 'gradient-arcane text-white' : ''}
                        >
                          Foil
                        </Button>
                      </div>

                      {/* Condition Filter */}
                      <select
                        value={filterCondition || ''}
                        onChange={(e) => {
                          setFilterCondition(e.target.value ? (e.target.value as InventoryCondition) : undefined);
                          setPage(1);
                        }}
                        className="px-3 py-1.5 text-sm rounded-lg border border-border bg-card text-foreground focus:outline-none focus:ring-2 focus:ring-[rgb(var(--accent))]/50"
                      >
                        <option value="">All Conditions</option>
                        <option value="MINT">Mint</option>
                        <option value="NEAR_MINT">Near Mint</option>
                        <option value="LIGHTLY_PLAYED">Lightly Played</option>
                        <option value="MODERATELY_PLAYED">Moderately Played</option>
                        <option value="HEAVILY_PLAYED">Heavily Played</option>
                        <option value="DAMAGED">Damaged</option>
                      </select>

                      {/* Clear Filters */}
                      {(searchQuery || filterFoil !== undefined || filterCondition) && (
                        <Button
                          variant="secondary"
                          size="sm"
                          onClick={handleClearFilters}
                          className="ml-auto"
                        >
                          <X className="w-4 h-4 mr-1" />
                          Clear
                        </Button>
                      )}
                    </div>
                  </div>
                </CardContent>
              </Card>

              <div className="text-sm text-muted-foreground">
                Showing {inventoryData.items.length} of {inventoryData.total} items
              </div>

              {inventoryData.items.length === 0 ? (
                <Card className="glow-accent">
                  <CardContent className="py-12 text-center">
                    <Package className="w-12 h-12 mx-auto text-muted-foreground mb-4" />
                    <p className="text-muted-foreground">
                      No items in your inventory yet.
                    </p>
                    <Button
                      size="sm"
                      onClick={() => setIsImportOpen(true)}
                      className="mt-4 gradient-arcane text-white"
                    >
                      <Upload className="w-4 h-4 mr-1" />
                      Import Cards
                    </Button>
                  </CardContent>
                </Card>
              ) : (
                <>
                  <div className="grid gap-4">
                    {inventoryData.items.map((item) => (
                      <InventoryItemCard
                        key={item.id}
                        item={item}
                        onDelete={handleDelete}
                        onToggleFoil={handleToggleFoil}
                      />
                    ))}
                  </div>

                  {inventoryData.total > 20 && (
                    <div className="flex items-center justify-center gap-2">
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => setPage((p) => Math.max(1, p - 1))}
                        disabled={page === 1}
                        className="glow-accent"
                      >
                        Previous
                      </Button>
                      <span className="text-sm text-muted-foreground">
                        Page {page} of {Math.ceil(inventoryData.total / 20)}
                      </span>
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => setPage((p) => p + 1)}
                        disabled={!inventoryData.has_more}
                        className="glow-accent"
                      >
                        Next
                      </Button>
                    </div>
                  )}
                </>
              )}
            </div>
          )}

          {/* Recommendations Tab */}
          {activeTab === 'recommendations' && recommendations && (
            <div className="space-y-4">
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <Card className={cn(
                  'glow-accent',
                  recommendations.critical_count > 0 && 'border-[rgb(var(--destructive))]/50'
                )}>
                  <CardContent className="p-3 text-center">
                    <p className="text-2xl font-bold text-[rgb(var(--destructive))]">{recommendations.critical_count}</p>
                    <p className="text-xs text-muted-foreground">Critical</p>
                  </CardContent>
                </Card>
                <Card className="glow-accent">
                  <CardContent className="p-3 text-center">
                    <p className="text-2xl font-bold text-[rgb(var(--mythic-orange))]">{recommendations.high_count}</p>
                    <p className="text-xs text-muted-foreground">High Priority</p>
                  </CardContent>
                </Card>
                <Card className="glow-accent">
                  <CardContent className="p-3 text-center">
                    <p className="text-2xl font-bold text-[rgb(var(--magic-gold))]">{recommendations.sell_count}</p>
                    <p className="text-xs text-muted-foreground">Sell Signals</p>
                  </CardContent>
                </Card>
                <Card className="glow-accent">
                  <CardContent className="p-3 text-center">
                    <p className="text-2xl font-bold text-[rgb(var(--warning))]">{recommendations.hold_count}</p>
                    <p className="text-xs text-muted-foreground">Hold Signals</p>
                  </CardContent>
                </Card>
              </div>

              <Card className="bg-gradient-to-r from-[rgb(var(--magic-gold))]/10 to-[rgb(var(--mythic-orange))]/10 border-[rgb(var(--magic-gold))]/30 glow-accent">
                <CardContent className="p-4 flex items-center gap-3">
                  <Zap className="w-5 h-5 text-[rgb(var(--magic-gold))] shrink-0" />
                  <p className="text-sm text-foreground">
                    <span className="font-semibold">Aggressive Analysis:</span> These recommendations use lower thresholds (5% ROI, 40% confidence) and shorter horizons (3 days) for faster decision-making on your inventory.
                  </p>
                </CardContent>
              </Card>

              {recommendations.recommendations.length === 0 ? (
                <Card className="glow-accent">
                  <CardContent className="py-12 text-center">
                    <Zap className="w-12 h-12 mx-auto text-muted-foreground mb-4" />
                    <p className="text-muted-foreground">
                      No recommendations available. Click &quot;Run Analysis&quot; to generate recommendations.
                    </p>
                  </CardContent>
                </Card>
              ) : (
                <>
                  <div className="space-y-4">
                    {recommendations.recommendations.map((rec) => (
                      <InventoryRecommendationCard key={rec.id} recommendation={rec} />
                    ))}
                  </div>

                  {recommendations.total > 20 && (
                    <div className="flex items-center justify-center gap-2">
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => setRecPage((p) => Math.max(1, p - 1))}
                        disabled={recPage === 1}
                        className="glow-accent"
                      >
                        Previous
                      </Button>
                      <span className="text-sm text-muted-foreground">
                        Page {recPage} of {Math.ceil(recommendations.total / 20)}
                      </span>
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => setRecPage((p) => p + 1)}
                        disabled={!recommendations.has_more}
                        className="glow-accent"
                      >
                        Next
                      </Button>
                    </div>
                  )}
                </>
              )}
            </div>
          )}
        </>
      )}

      {/* Import Modal */}
      <InventoryImportModal isOpen={isImportOpen} onClose={() => setIsImportOpen(false)} />
    </div>
  );
}

export default function InventoryPage(): JSX.Element {
  return <InventoryPageContent />;
}
