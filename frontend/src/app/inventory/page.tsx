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
import { Card, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { LoadingPage, Loading } from '@/components/ui/Loading';
import { SearchBar } from '@/components/cards/SearchBar';
import { InventoryImportModal } from '@/components/inventory/InventoryImportModal';
import { InventoryItemCard } from '@/components/inventory/InventoryItemCard';
import { InventoryRecommendationCard } from '@/components/inventory/InventoryRecommendationCard';
import { ProtectedRoute } from '@/components/auth/ProtectedRoute';
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
import { formatCurrency } from '@/lib/utils';
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
    refetchInterval: 15 * 60 * 1000,
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
    queryFn: () => getInventoryMarketIndex(marketIndexRange, undefined, false, marketIndexFoil),
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
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-3xl font-bold text-[rgb(var(--foreground))] flex items-center gap-3">
            <div className="p-2 rounded-xl bg-gradient-to-br from-amber-500 to-orange-600">
              <Package className="w-6 h-6 text-white" />
            </div>
            My Inventory
          </h1>
          <p className="text-[rgb(var(--muted-foreground))] mt-1">
            Track your collection with aggressive analytics and recommendations
          </p>
        </div>
        <div className="flex gap-2">
          <Button
            variant="secondary"
            size="sm"
            onClick={() => refreshMutation.mutate()}
            disabled={refreshMutation.isPending}
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
          >
            {runRecsMutation.isPending ? (
              <Loading size="sm" className="mr-1" />
            ) : (
              <Zap className="w-4 h-4 mr-1" />
            )}
            Run Analysis
          </Button>
          <Button
            variant="primary"
            size="sm"
            onClick={() => setIsImportOpen(true)}
            className="bg-gradient-to-r from-amber-500 to-orange-600 hover:from-amber-600 hover:to-orange-700"
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
              className="bg-gradient-to-r from-blue-500 to-indigo-600 hover:from-blue-600 hover:to-indigo-700 text-white"
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
                <div className="absolute right-0 top-full mt-1 w-56 bg-[rgb(var(--background))] border border-[rgb(var(--border))] rounded-md shadow-lg z-20">
                  <button
                    onClick={() => handleExport('cardtrader')}
                    className="w-full text-left px-4 py-2.5 text-sm hover:bg-[rgb(var(--muted))] rounded-t-md flex items-center gap-2"
                  >
                    <Download className="w-4 h-4" />
                    <div>
                      <div className="font-medium">Export to CardTrader</div>
                      <div className="text-xs text-[rgb(var(--muted-foreground))]">CSV format for CardTrader import</div>
                    </div>
                  </button>
                  <button
                    onClick={() => handleExport('csv')}
                    className="w-full text-left px-4 py-2.5 text-sm hover:bg-[rgb(var(--muted))] flex items-center gap-2"
                  >
                    <Download className="w-4 h-4" />
                    <div>
                      <div className="font-medium">Export as CSV</div>
                      <div className="text-xs text-[rgb(var(--muted-foreground))]">Standard CSV format</div>
                    </div>
                  </button>
                  <button
                    onClick={() => handleExport('txt')}
                    className="w-full text-left px-4 py-2.5 text-sm hover:bg-[rgb(var(--muted))] rounded-b-md flex items-center gap-2"
                  >
                    <Download className="w-4 h-4" />
                    <div>
                      <div className="font-medium">Export as Plain Text</div>
                      <div className="text-xs text-[rgb(var(--muted-foreground))]">Simple text format</div>
                    </div>
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      </div>
      
      {/* Quick Stats */}
      {analytics && (
        <div className="grid grid-cols-5 gap-4">
          <Card className="bg-gradient-to-br from-blue-500/10 to-blue-600/5 border-blue-500/20">
            <CardContent className="p-4">
              <div className="flex items-center gap-2 mb-2">
                <Package className="w-5 h-5 text-blue-500" />
                <span className="text-sm text-[rgb(var(--muted-foreground))]">Total Cards</span>
              </div>
              <p className="text-2xl font-bold text-[rgb(var(--foreground))]">
                {analytics.total_quantity}
              </p>
              <p className="text-xs text-[rgb(var(--muted-foreground))]">
                {analytics.total_unique_cards} unique
              </p>
            </CardContent>
          </Card>
          
          <Card className="bg-gradient-to-br from-green-500/10 to-green-600/5 border-green-500/20">
            <CardContent className="p-4">
              <div className="flex items-center gap-2 mb-2">
                <DollarSign className="w-5 h-5 text-green-500" />
                <span className="text-sm text-[rgb(var(--muted-foreground))]">Total Value</span>
              </div>
              <p className="text-2xl font-bold text-[rgb(var(--foreground))]">
                {formatCurrency(analytics.total_current_value)}
              </p>
              <p className="text-xs text-[rgb(var(--muted-foreground))]">
                Cost: {formatCurrency(analytics.total_acquisition_cost)}
              </p>
            </CardContent>
          </Card>
          
          <Card className={analytics.total_profit_loss >= 0
            ? 'bg-gradient-to-br from-emerald-500/10 to-emerald-600/5 border-emerald-500/20'
            : 'bg-gradient-to-br from-red-500/10 to-red-600/5 border-red-500/20'
          }>
            <CardContent className="p-4">
              <div className="flex items-center gap-2 mb-2">
                {analytics.total_profit_loss >= 0 ? (
                  <TrendingUp className="w-5 h-5 text-emerald-500" />
                ) : (
                  <TrendingDown className="w-5 h-5 text-red-500" />
                )}
                <span className="text-sm text-[rgb(var(--muted-foreground))]">Profit/Loss</span>
              </div>
              <p className={`text-2xl font-bold ${
                analytics.total_profit_loss >= 0 ? 'text-emerald-500' : 'text-red-500'
              }`}>
                {analytics.total_profit_loss >= 0 ? '+' : ''}{formatCurrency(analytics.total_profit_loss)}
              </p>
              {analytics.profit_loss_pct !== null && analytics.profit_loss_pct !== undefined && (
                <p className={`text-xs ${
                  analytics.profit_loss_pct >= 0 ? 'text-emerald-400' : 'text-red-400'
                }`}>
                  {analytics.profit_loss_pct >= 0 ? '+' : ''}{analytics.profit_loss_pct.toFixed(1)}%
                </p>
              )}
            </CardContent>
          </Card>
          
          <Card className="bg-gradient-to-br from-amber-500/10 to-amber-600/5 border-amber-500/20">
            <CardContent className="p-4">
              <div className="flex items-center gap-2 mb-2">
                <Zap className="w-5 h-5 text-amber-500" />
                <span className="text-sm text-[rgb(var(--muted-foreground))]">Sell Signals</span>
              </div>
              <p className="text-2xl font-bold text-[rgb(var(--foreground))]">
                {analytics.sell_recommendations}
              </p>
              <p className="text-xs text-[rgb(var(--muted-foreground))]">
                {analytics.hold_recommendations} holds
              </p>
            </CardContent>
          </Card>
          
          <Card className={analytics.critical_alerts > 0
            ? 'bg-gradient-to-br from-red-500/10 to-red-600/5 border-red-500/20'
            : 'bg-gradient-to-br from-gray-500/10 to-gray-600/5 border-gray-500/20'
          }>
            <CardContent className="p-4">
              <div className="flex items-center gap-2 mb-2">
                <AlertTriangle className={`w-5 h-5 ${analytics.critical_alerts > 0 ? 'text-red-500' : 'text-gray-500'}`} />
                <span className="text-sm text-[rgb(var(--muted-foreground))]">Critical Alerts</span>
              </div>
              <p className={`text-2xl font-bold ${
                analytics.critical_alerts > 0 ? 'text-red-500' : 'text-[rgb(var(--foreground))]'
              }`}>
                {analytics.critical_alerts}
              </p>
              <p className="text-xs text-[rgb(var(--muted-foreground))]">
                Needs attention
              </p>
            </CardContent>
          </Card>
        </div>
      )}
      
      {/* Tabs */}
      <div className="flex gap-2 border-b border-[rgb(var(--border))]">
        {tabs.map((tab) => {
          const TabIcon = tab.icon;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-2 px-4 py-3 text-sm font-medium transition-colors border-b-2 -mb-[2px] ${
                activeTab === tab.id
                  ? 'text-amber-500 border-amber-500'
                  : 'text-[rgb(var(--muted-foreground))] border-transparent hover:text-[rgb(var(--foreground))]'
              }`}
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
                    <div className="h-64 animate-pulse bg-[rgb(var(--secondary))] rounded"></div>
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
                        <div className="h-64 animate-pulse bg-[rgb(var(--secondary))] rounded"></div>
                      </CardContent>
                    </Card>
                  ))}
                </div>
              ) : inventoryTopMovers ? (
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                  {/* Top Gainers */}
                  <Card>
                    <CardContent className="p-4">
                      <div className="flex items-center gap-2 mb-4">
                        <TrendingUp className="w-5 h-5 text-green-500" />
                        <h3 className="font-semibold text-[rgb(var(--foreground))]">Top Gainers (24h)</h3>
                      </div>
                      <div className="space-y-3">
                        {inventoryTopMovers.gainers.length > 0 ? (
                          inventoryTopMovers.gainers.map((mover, index) => (
                            <div key={`gainer-${index}`} className="flex items-center justify-between p-2 rounded-lg bg-[rgb(var(--secondary))]/50">
                              <div>
                                <p className="font-medium text-[rgb(var(--foreground))]">{mover.cardName}</p>
                                <p className="text-xs text-[rgb(var(--muted-foreground))]">{mover.setCode}</p>
                              </div>
                              <div className="text-right">
                                <p className="font-medium text-[rgb(var(--foreground))]">
                                  {formatCurrency(mover.currentPriceUsd)}
                                </p>
                                <p className="text-sm font-medium text-green-500">
                                  +{mover.changePct.toFixed(1)}%
                                </p>
                              </div>
                            </div>
                          ))
                        ) : (
                          <p className="text-sm text-[rgb(var(--muted-foreground))] text-center py-4">
                            No gainers to show
                          </p>
                        )}
                      </div>
                    </CardContent>
                  </Card>
                  
                  {/* Top Losers */}
                  <Card>
                    <CardContent className="p-4">
                      <div className="flex items-center gap-2 mb-4">
                        <TrendingDown className="w-5 h-5 text-red-500" />
                        <h3 className="font-semibold text-[rgb(var(--foreground))]">Top Losers (24h)</h3>
                      </div>
                      <div className="space-y-3">
                        {inventoryTopMovers.losers.length > 0 ? (
                          inventoryTopMovers.losers.map((mover, index) => (
                            <div key={`loser-${index}`} className="flex items-center justify-between p-2 rounded-lg bg-[rgb(var(--secondary))]/50">
                              <div>
                                <p className="font-medium text-[rgb(var(--foreground))]">{mover.cardName}</p>
                                <p className="text-xs text-[rgb(var(--muted-foreground))]">{mover.setCode}</p>
                              </div>
                              <div className="text-right">
                                <p className="font-medium text-[rgb(var(--foreground))]">
                                  {formatCurrency(mover.currentPriceUsd)}
                                </p>
                                <p className="text-sm font-medium text-red-500">
                                  {mover.changePct.toFixed(1)}%
                                </p>
                              </div>
                            </div>
                          ))
                        ) : (
                          <p className="text-sm text-[rgb(var(--muted-foreground))] text-center py-4">
                            No losers to show
                          </p>
                        )}
                      </div>
                    </CardContent>
                  </Card>
                </div>
              ) : null}
              
              {/* Analytics Cards */}
              <div className="grid grid-cols-2 gap-6">
                {/* Value Distribution */}
                <Card>
                  <CardContent className="p-4">
                    <div className="flex items-center gap-2 mb-4">
                      <BarChart3 className="w-5 h-5 text-amber-500" />
                      <h3 className="font-semibold text-[rgb(var(--foreground))]">Value Distribution</h3>
                    </div>
                    <div className="space-y-3">
                      {Object.entries(analytics.value_distribution).map(([range, count]) => {
                        const maxCount = Math.max(...Object.values(analytics.value_distribution), 1);
                        const widthPercent = Math.max(5, (count / maxCount) * 100);
                        return (
                          <div key={range} className="flex items-center gap-3">
                            <span className="w-16 text-sm text-[rgb(var(--muted-foreground))]">{range}</span>
                            <div className="flex-1 h-6 bg-[rgb(var(--secondary))] rounded-full overflow-hidden">
                              <div
                                className="h-full bg-gradient-to-r from-amber-500 to-orange-600 rounded-full"
                                style={{ width: `${widthPercent}%` }}
                              />
                            </div>
                            <span className="w-12 text-sm text-[rgb(var(--foreground))] text-right">{count}</span>
                          </div>
                        );
                      })}
                    </div>
                  </CardContent>
                </Card>
                
                {/* Condition Breakdown */}
                <Card>
                  <CardContent className="p-4">
                    <div className="flex items-center gap-2 mb-4">
                      <Filter className="w-5 h-5 text-blue-500" />
                      <h3 className="font-semibold text-[rgb(var(--foreground))]">Condition Breakdown</h3>
                    </div>
                    <div className="space-y-3">
                      {Object.entries(analytics.condition_breakdown).map(([condition, count]) => (
                        <div key={condition} className="flex items-center justify-between p-2 rounded-lg bg-[rgb(var(--secondary))]/50">
                          <span className="text-sm text-[rgb(var(--foreground))]">
                            {conditionLabels[condition] || condition}
                          </span>
                          <span className="font-medium text-[rgb(var(--foreground))]">{count}</span>
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
              <Card>
                <CardContent className="p-4">
                  <div className="space-y-4">
                    {/* Search Bar */}
                    <SearchBar
                      value={searchQuery}
                      onSearch={(query) => {
                        setSearchQuery(query);
                        setPage(1);
                      }}
                      placeholder="Search by card name..."
                    />
                    
                    {/* Filters */}
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-sm text-[rgb(var(--muted-foreground))]">Filters:</span>
                      
                      {/* Foil Filter */}
                      <div className="flex items-center gap-1">
                        <Button
                          variant={filterFoil === undefined ? 'primary' : 'secondary'}
                          size="sm"
                          onClick={() => setFilterFoil(undefined)}
                        >
                          All
                        </Button>
                        <Button
                          variant={filterFoil === false ? 'primary' : 'secondary'}
                          size="sm"
                          onClick={() => setFilterFoil(false)}
                        >
                          Non-Foil
                        </Button>
                        <Button
                          variant={filterFoil === true ? 'primary' : 'secondary'}
                          size="sm"
                          onClick={() => setFilterFoil(true)}
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
                        className="px-3 py-1.5 text-sm rounded-lg border border-[rgb(var(--border))] bg-[rgb(var(--card))] text-[rgb(var(--foreground))]"
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
              
              <div className="text-sm text-[rgb(var(--muted-foreground))]">
                Showing {inventoryData.items.length} of {inventoryData.total} items
              </div>
              
              {inventoryData.items.length === 0 ? (
                <Card>
                  <CardContent className="py-12 text-center">
                    <Package className="w-12 h-12 mx-auto text-[rgb(var(--muted-foreground))] mb-4" />
                    <p className="text-[rgb(var(--muted-foreground))]">
                      No items in your inventory yet.
                    </p>
                    <Button
                      variant="primary"
                      size="sm"
                      onClick={() => setIsImportOpen(true)}
                      className="mt-4 bg-gradient-to-r from-amber-500 to-orange-600"
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
                      >
                        Previous
                      </Button>
                      <span className="text-sm text-[rgb(var(--muted-foreground))]">
                        Page {page} of {Math.ceil(inventoryData.total / 20)}
                      </span>
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => setPage((p) => p + 1)}
                        disabled={!inventoryData.has_more}
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
              <div className="grid grid-cols-4 gap-4">
                <Card className={recommendations.critical_count > 0 ? 'border-red-500/50' : ''}>
                  <CardContent className="p-3 text-center">
                    <p className="text-2xl font-bold text-red-500">{recommendations.critical_count}</p>
                    <p className="text-xs text-[rgb(var(--muted-foreground))]">Critical</p>
                  </CardContent>
                </Card>
                <Card>
                  <CardContent className="p-3 text-center">
                    <p className="text-2xl font-bold text-orange-500">{recommendations.high_count}</p>
                    <p className="text-xs text-[rgb(var(--muted-foreground))]">High Priority</p>
                  </CardContent>
                </Card>
                <Card>
                  <CardContent className="p-3 text-center">
                    <p className="text-2xl font-bold text-amber-500">{recommendations.sell_count}</p>
                    <p className="text-xs text-[rgb(var(--muted-foreground))]">Sell Signals</p>
                  </CardContent>
                </Card>
                <Card>
                  <CardContent className="p-3 text-center">
                    <p className="text-2xl font-bold text-yellow-500">{recommendations.hold_count}</p>
                    <p className="text-xs text-[rgb(var(--muted-foreground))]">Hold Signals</p>
                  </CardContent>
                </Card>
              </div>
              
              <Card className="bg-gradient-to-r from-amber-500/10 to-orange-500/10 border-amber-500/30">
                <CardContent className="p-4 flex items-center gap-3">
                  <Zap className="w-5 h-5 text-amber-500 shrink-0" />
                  <p className="text-sm text-[rgb(var(--foreground))]">
                    <span className="font-semibold">Aggressive Analysis:</span> These recommendations use lower thresholds (5% ROI, 40% confidence) and shorter horizons (3 days) for faster decision-making on your inventory.
                  </p>
                </CardContent>
              </Card>
              
              {recommendations.recommendations.length === 0 ? (
                <Card>
                  <CardContent className="py-12 text-center">
                    <Zap className="w-12 h-12 mx-auto text-[rgb(var(--muted-foreground))] mb-4" />
                    <p className="text-[rgb(var(--muted-foreground))]">
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
                      >
                        Previous
                      </Button>
                      <span className="text-sm text-[rgb(var(--muted-foreground))]">
                        Page {recPage} of {Math.ceil(recommendations.total / 20)}
                      </span>
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => setRecPage((p) => p + 1)}
                        disabled={!recommendations.has_more}
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
  return (
    <ProtectedRoute>
      <InventoryPageContent />
    </ProtectedRoute>
  );
}
