'use client';

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Package,
  Upload,
  TrendingUp,
  TrendingDown,
  AlertTriangle,
  RefreshCw,
  Zap,
  DollarSign,
  BarChart3,
  Filter,
} from 'lucide-react';
import { Card, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { LoadingPage, LoadingSpinner } from '@/components/ui/Loading';
import { InventoryImportModal } from '@/components/inventory/InventoryImportModal';
import { InventoryItemCard } from '@/components/inventory/InventoryItemCard';
import { InventoryRecommendationCard } from '@/components/inventory/InventoryRecommendationCard';
import {
  getInventory,
  getInventoryAnalytics,
  getInventoryRecommendations,
  refreshInventoryValuations,
  runInventoryRecommendations,
} from '@/lib/api';
import { formatCurrency } from '@/lib/utils';

type TabType = 'overview' | 'items' | 'recommendations';

export default function InventoryPage() {
  const [activeTab, setActiveTab] = useState<TabType>('overview');
  const [isImportOpen, setIsImportOpen] = useState(false);
  const [page, setPage] = useState(1);
  const [recPage, setRecPage] = useState(1);
  
  const queryClient = useQueryClient();
  
  // Fetch inventory data
  const { data: inventoryData, isLoading: inventoryLoading } = useQuery({
    queryKey: ['inventory', page],
    queryFn: () => getInventory({ page, pageSize: 20 }),
  });
  
  // Fetch analytics
  const { data: analytics, isLoading: analyticsLoading } = useQuery({
    queryKey: ['inventory-analytics'],
    queryFn: getInventoryAnalytics,
  });
  
  // Fetch recommendations
  const { data: recommendations, isLoading: recsLoading } = useQuery({
    queryKey: ['inventory-recommendations', recPage],
    queryFn: () => getInventoryRecommendations({ page: recPage, pageSize: 20 }),
  });
  
  // Mutations
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
  
  const isLoading = inventoryLoading || analyticsLoading;
  
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
              <LoadingSpinner className="w-4 h-4 mr-1" />
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
              <LoadingSpinner className="w-4 h-4 mr-1" />
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
          
          <Card className={`bg-gradient-to-br ${
            analytics.total_profit_loss >= 0
              ? 'from-emerald-500/10 to-emerald-600/5 border-emerald-500/20'
              : 'from-red-500/10 to-red-600/5 border-red-500/20'
          }`}>
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
          
          <Card className={`bg-gradient-to-br ${
            analytics.critical_alerts > 0
              ? 'from-red-500/10 to-red-600/5 border-red-500/20'
              : 'from-gray-500/10 to-gray-600/5 border-gray-500/20'
          }`}>
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
        {([
          { id: 'overview', label: 'Overview', icon: BarChart3 },
          { id: 'items', label: 'All Items', icon: Package },
          { id: 'recommendations', label: 'Recommendations', icon: Zap },
        ] as const).map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`flex items-center gap-2 px-4 py-3 text-sm font-medium transition-colors border-b-2 -mb-[2px] ${
              activeTab === tab.id
                ? 'text-amber-500 border-amber-500'
                : 'text-[rgb(var(--muted-foreground))] border-transparent hover:text-[rgb(var(--foreground))]'
            }`}
          >
            <tab.icon className="w-4 h-4" />
            {tab.label}
          </button>
        ))}
      </div>
      
      {/* Tab Content */}
      {isLoading ? (
        <LoadingPage />
      ) : (
        <>
          {/* Overview Tab */}
          {activeTab === 'overview' && analytics && (
            <div className="grid grid-cols-2 gap-6">
              {/* Top Gainers */}
              <Card>
                <CardContent className="p-4">
                  <div className="flex items-center gap-2 mb-4">
                    <TrendingUp className="w-5 h-5 text-green-500" />
                    <h3 className="font-semibold text-[rgb(var(--foreground))]">Top Gainers</h3>
                  </div>
                  <div className="space-y-3">
                    {analytics.top_gainers.length > 0 ? (
                      analytics.top_gainers.map((item) => (
                        <div key={item.id} className="flex items-center justify-between p-2 rounded-lg bg-[rgb(var(--secondary))]/50">
                          <div>
                            <p className="font-medium text-[rgb(var(--foreground))]">{item.card_name}</p>
                            <p className="text-xs text-[rgb(var(--muted-foreground))]">{item.card_set}</p>
                          </div>
                          <Badge variant="success">
                            +{item.value_change_pct?.toFixed(1)}%
                          </Badge>
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
                    <h3 className="font-semibold text-[rgb(var(--foreground))]">Top Losers</h3>
                  </div>
                  <div className="space-y-3">
                    {analytics.top_losers.length > 0 ? (
                      analytics.top_losers.map((item) => (
                        <div key={item.id} className="flex items-center justify-between p-2 rounded-lg bg-[rgb(var(--secondary))]/50">
                          <div>
                            <p className="font-medium text-[rgb(var(--foreground))]">{item.card_name}</p>
                            <p className="text-xs text-[rgb(var(--muted-foreground))]">{item.card_set}</p>
                          </div>
                          <Badge variant="danger">
                            {item.value_change_pct?.toFixed(1)}%
                          </Badge>
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
              
              {/* Value Distribution */}
              <Card>
                <CardContent className="p-4">
                  <div className="flex items-center gap-2 mb-4">
                    <BarChart3 className="w-5 h-5 text-amber-500" />
                    <h3 className="font-semibold text-[rgb(var(--foreground))]">Value Distribution</h3>
                  </div>
                  <div className="space-y-3">
                    {Object.entries(analytics.value_distribution).map(([range, count]) => (
                      <div key={range} className="flex items-center gap-3">
                        <span className="w-16 text-sm text-[rgb(var(--muted-foreground))]">{range}</span>
                        <div className="flex-1 h-6 bg-[rgb(var(--secondary))] rounded-full overflow-hidden">
                          <div
                            className="h-full bg-gradient-to-r from-amber-500 to-orange-600 rounded-full"
                            style={{
                              width: `${Math.max(5, (count / Math.max(...Object.values(analytics.value_distribution), 1)) * 100)}%`,
                            }}
                          />
                        </div>
                        <span className="w-12 text-sm text-[rgb(var(--foreground))] text-right">{count}</span>
                      </div>
                    ))}
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
                    {Object.entries(analytics.condition_breakdown).map(([condition, count]) => {
                      const labels: Record<string, string> = {
                        MINT: 'Mint',
                        NEAR_MINT: 'Near Mint',
                        LIGHTLY_PLAYED: 'Lightly Played',
                        MODERATELY_PLAYED: 'Mod. Played',
                        HEAVILY_PLAYED: 'Heavily Played',
                        DAMAGED: 'Damaged',
                      };
                      return (
                        <div key={condition} className="flex items-center justify-between p-2 rounded-lg bg-[rgb(var(--secondary))]/50">
                          <span className="text-sm text-[rgb(var(--foreground))]">{labels[condition] || condition}</span>
                          <span className="font-medium text-[rgb(var(--foreground))]">{count}</span>
                        </div>
                      );
                    })}
                  </div>
                </CardContent>
              </Card>
            </div>
          )}
          
          {/* Items Tab */}
          {activeTab === 'items' && inventoryData && (
            <div className="space-y-4">
              {/* Summary */}
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
                      <InventoryItemCard key={item.id} item={item} />
                    ))}
                  </div>
                  
                  {/* Pagination */}
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
              {/* Summary */}
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
              
              {/* Info Banner */}
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
                  
                  {/* Pagination */}
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
