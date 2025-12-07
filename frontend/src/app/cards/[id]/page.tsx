'use client';

import { useParams } from 'next/navigation';
import { useQuery, useQueryClient, useMutation } from '@tanstack/react-query';
import { useState } from 'react';
import Image from 'next/image';
import { ArrowLeft, Package, Plus, X } from 'lucide-react';
import Link from 'next/link';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { Badge, ActionBadge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { LoadingPage } from '@/components/ui/Loading';
import { PriceChart } from '@/components/charts/PriceChart';
import { SpreadChart } from '@/components/charts/SpreadChart';
import { getCard, getCardHistory, refreshCard, createInventoryItem } from '@/lib/api';
import { formatCurrency, formatPercent, getRarityColor } from '@/lib/utils';
import type { InventoryCondition } from '@/types';

const CONDITION_OPTIONS: { value: InventoryCondition; label: string }[] = [
  { value: 'MINT', label: 'Mint' },
  { value: 'NEAR_MINT', label: 'Near Mint' },
  { value: 'LIGHTLY_PLAYED', label: 'Lightly Played' },
  { value: 'MODERATELY_PLAYED', label: 'Moderately Played' },
  { value: 'HEAVILY_PLAYED', label: 'Heavily Played' },
  { value: 'DAMAGED', label: 'Damaged' },
];

export default function CardDetailPage() {
  const params = useParams();
  const cardId = Number(params.id);

  const [isRefreshing, setIsRefreshing] = useState(false);
  const [showAddInventory, setShowAddInventory] = useState(false);
  const [selectedCondition, setSelectedCondition] = useState<string>('');  // Empty = all conditions
  const [selectedFoil, setSelectedFoil] = useState<string>('');  // Empty = all, 'false' = non-foil, 'true' = foil
  const [inventoryForm, setInventoryForm] = useState({
    quantity: 1,
    condition: 'NEAR_MINT' as InventoryCondition,
    is_foil: false,
    acquisition_price: '',
  });

  const queryClient = useQueryClient();
  
  const addToInventoryMutation = useMutation({
    mutationFn: () => createInventoryItem({
      card_id: cardId,
      quantity: inventoryForm.quantity,
      condition: inventoryForm.condition,
      is_foil: inventoryForm.is_foil,
      acquisition_price: inventoryForm.acquisition_price ? parseFloat(inventoryForm.acquisition_price) : undefined,
    }),
    onSuccess: () => {
      setShowAddInventory(false);
      setInventoryForm({ quantity: 1, condition: 'NEAR_MINT', is_foil: false, acquisition_price: '' });
      queryClient.invalidateQueries({ queryKey: ['inventory'] });
    },
  });

  const { data: cardDetail, isLoading, error } = useQuery({
    queryKey: ['card', cardId],
    queryFn: () => getCard(cardId),
    enabled: !!cardId,
    refetchInterval: 60000,  // Auto-refresh every 60 seconds for live data
    refetchIntervalInBackground: true,  // Continue refreshing when tab is in background
  });

  const { data: history, refetch: refetchHistory } = useQuery({
    queryKey: ['card', cardId, 'history', selectedCondition, selectedFoil],
    queryFn: () => getCardHistory(cardId, { 
      days: 30,
      condition: selectedCondition || undefined,
      isFoil: selectedFoil === '' ? undefined : selectedFoil === 'true'
    }),
    enabled: !!cardId,
    refetchInterval: 60000,  // Auto-refresh every 60 seconds for live data
    refetchIntervalInBackground: true,
  });

  if (isLoading) return <LoadingPage />;

  if (error || !cardDetail) {
    return (
      <div className="text-center py-12">
        <p className="text-red-500 mb-4">Failed to load card details</p>
        <Link href="/cards">
          <Button variant="secondary">
            <ArrowLeft className="w-4 h-4 mr-2" />
            Back to Search
          </Button>
        </Link>
      </div>
    );
  }

  const { card, metrics, current_prices, recent_signals, active_recommendations, refresh_requested, refresh_reason } = cardDetail;

  const triggerRefresh = async () => {
    if (isRefreshing) return;
    setIsRefreshing(true);
    try {
      // Use sync=true to get immediate data back
      const updatedData = await refreshCard(cardId, { sync: true });
      // Update the cache with the new data
      queryClient.setQueryData(['card', cardId], updatedData);
      // Also refetch history to get new price points
      await queryClient.invalidateQueries({ queryKey: ['card', cardId, 'history'] });
    } catch (err) {
      console.error('Failed to refresh card', err);
    } finally {
      setIsRefreshing(false);
    }
  };

  return (
    <div className="space-y-6 animate-in">
      {/* Back Button */}
      <Link href="/cards" className="inline-flex items-center text-[rgb(var(--muted-foreground))] hover:text-[rgb(var(--foreground))] transition-colors">
        <ArrowLeft className="w-4 h-4 mr-2" />
        Back to Search
      </Link>

      {/* Card Header */}
      <div className="flex flex-col lg:flex-row gap-6">
        {/* Card Image */}
        <div className="lg:w-80 shrink-0">
          <div className="aspect-[5/7] relative rounded-xl overflow-hidden bg-[rgb(var(--secondary))] shadow-xl">
            {card.image_url ? (
              <Image
                src={card.image_url}
                alt={card.name}
                fill
                className="object-cover"
                priority
                sizes="320px"
              />
            ) : (
              <div className="absolute inset-0 flex items-center justify-center text-[rgb(var(--muted-foreground))]">
                No Image
              </div>
            )}
          </div>
        </div>

        {/* Card Info */}
        <div className="flex-1 space-y-6">
          <div>
            <div className="flex items-start justify-between gap-4">
              <div>
                <h1 className="text-3xl font-bold text-[rgb(var(--foreground))]">{card.name}</h1>
                <p className="text-lg text-[rgb(var(--muted-foreground))] mt-1">
                  {card.set_name || card.set_code} #{card.collector_number}
                </p>
              </div>
              {card.rarity && (
                <Badge className={getRarityColor(card.rarity)} size="md">
                  {card.rarity}
                </Badge>
              )}
            </div>
            <div className="flex items-center gap-3 mt-3">
              {refresh_requested && (
                <span className="text-sm text-[rgb(var(--muted-foreground))]">
                  Refreshing ({refresh_reason})
                </span>
              )}
              <Button variant="secondary" size="sm" disabled={isRefreshing} onClick={triggerRefresh}>
                {isRefreshing ? 'Refreshing…' : 'Refresh data'}
              </Button>
              <Button 
                variant="primary" 
                size="sm" 
                onClick={() => setShowAddInventory(true)}
                className="bg-gradient-to-r from-amber-500 to-orange-600 hover:from-amber-600 hover:to-orange-700"
              >
                <Plus className="w-4 h-4 mr-1" />
                Add to Inventory
              </Button>
            </div>

            {card.type_line && (
              <p className="text-[rgb(var(--muted-foreground))] mt-4">{card.type_line}</p>
            )}
            
            {card.mana_cost && (
              <p className="text-[rgb(var(--foreground))] mt-2">
                Mana Cost: {card.mana_cost}
              </p>
            )}

            {card.oracle_text && (
              <p className="text-[rgb(var(--muted-foreground))] mt-4 whitespace-pre-line">
                {card.oracle_text}
              </p>
            )}
          </div>

          {/* Quick Stats */}
          {metrics && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <StatBox
                label="Avg Price"
                value={formatCurrency(metrics.avg_price)}
              />
              <StatBox
                label="7d Change"
                value={formatPercent(metrics.price_change_7d)}
                valueColor={
                  (metrics.price_change_7d ?? 0) > 0
                    ? 'text-green-500'
                    : (metrics.price_change_7d ?? 0) < 0
                    ? 'text-red-500'
                    : undefined
                }
              />
              <StatBox
                label="Market Spread"
                value={formatPercent(metrics.spread_pct)}
              />
              <StatBox
                label="Listings"
                value={String(metrics.total_listings ?? '-')}
              />
            </div>
          )}
        </div>
      </div>

      {/* Price Comparison */}
      {current_prices.length > 0 && (
        <SpreadChart data={current_prices} title="Current Prices by Marketplace" />
      )}

      {/* Price History with Condition and Foil Filters */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between flex-wrap gap-4">
            <CardTitle>30-Day Price History</CardTitle>
            {/* Filters */}
            <div className="flex items-center gap-3 flex-wrap">
              {/* Condition Filter */}
              <div className="flex items-center gap-2">
                <label className="text-sm font-medium text-[rgb(var(--foreground))] whitespace-nowrap">
                  Condition:
                </label>
                <select
                  value={selectedCondition}
                  onChange={(e) => setSelectedCondition(e.target.value)}
                  className="px-4 py-2 rounded-lg bg-[rgb(var(--secondary))] border border-[rgb(var(--border))] text-[rgb(var(--foreground))] focus:outline-none focus:ring-2 focus:ring-amber-500/50 cursor-pointer hover:bg-[rgb(var(--secondary))]/80 transition-colors min-w-[160px]"
                >
                  <option value="">All Conditions</option>
                  <option value="Near Mint">Near Mint</option>
                  <option value="Lightly Played">Lightly Played</option>
                  <option value="Moderately Played">Moderately Played</option>
                  <option value="Heavily Played">Heavily Played</option>
                  <option value="Damaged">Damaged</option>
                </select>
              </div>
              {/* Foil Filter */}
              <div className="flex items-center gap-2">
                <label className="text-sm font-medium text-[rgb(var(--foreground))] whitespace-nowrap">
                  Type:
                </label>
                <select
                  value={selectedFoil}
                  onChange={(e) => setSelectedFoil(e.target.value)}
                  className="px-4 py-2 rounded-lg bg-[rgb(var(--secondary))] border border-[rgb(var(--border))] text-[rgb(var(--foreground))] focus:outline-none focus:ring-2 focus:ring-amber-500/50 cursor-pointer hover:bg-[rgb(var(--secondary))]/80 transition-colors min-w-[140px]"
                >
                  <option value="">All Types</option>
                  <option value="false">Non-Foil</option>
                  <option value="true">Foil</option>
                </select>
              </div>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {history && history.history.length > 0 ? (
            <PriceChart 
              data={history.history} 
              history={history}
              title=""  // Title is now in CardHeader
              showFreshness={true}
              autoRefresh={true}
              refreshInterval={60}
            />
          ) : (
            <div className="text-center py-12 text-[rgb(var(--muted-foreground))]">
              <p>No price history data available</p>
              {selectedCondition && (
                <p className="text-sm mt-2">Try selecting "All Conditions" or refresh the card data</p>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Add to Inventory Modal */}
      {showAddInventory && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
          <Card className="w-full max-w-md bg-[rgb(var(--card))] border-[rgb(var(--border))]">
            <div className="flex items-center justify-between p-4 border-b border-[rgb(var(--border))]">
              <div className="flex items-center gap-3">
                <div className="p-2 rounded-lg bg-gradient-to-br from-amber-500 to-orange-600">
                  <Package className="w-5 h-5 text-white" />
                </div>
                <h2 className="text-lg font-semibold text-[rgb(var(--foreground))]">Add to Inventory</h2>
              </div>
              <button
                onClick={() => setShowAddInventory(false)}
                className="p-2 rounded-lg hover:bg-[rgb(var(--secondary))] transition-colors"
              >
                <X className="w-5 h-5 text-[rgb(var(--muted-foreground))]" />
              </button>
            </div>
            <CardContent className="p-4 space-y-4">
              <div className="text-center mb-4">
                <p className="font-semibold text-[rgb(var(--foreground))]">{card.name}</p>
                <p className="text-sm text-[rgb(var(--muted-foreground))]">{card.set_name || card.set_code}</p>
              </div>
              
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-[rgb(var(--foreground))] mb-1">Quantity</label>
                  <input
                    type="number"
                    min="1"
                    value={inventoryForm.quantity}
                    onChange={(e) => setInventoryForm(f => ({ ...f, quantity: parseInt(e.target.value) || 1 }))}
                    className="w-full px-3 py-2 rounded-lg bg-[rgb(var(--secondary))] border border-[rgb(var(--border))] text-[rgb(var(--foreground))] focus:outline-none focus:ring-2 focus:ring-amber-500/50"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-[rgb(var(--foreground))] mb-1">Acquisition Price</label>
                  <input
                    type="number"
                    step="0.01"
                    min="0"
                    placeholder="$0.00"
                    value={inventoryForm.acquisition_price}
                    onChange={(e) => setInventoryForm(f => ({ ...f, acquisition_price: e.target.value }))}
                    className="w-full px-3 py-2 rounded-lg bg-[rgb(var(--secondary))] border border-[rgb(var(--border))] text-[rgb(var(--foreground))] placeholder:text-[rgb(var(--muted-foreground))] focus:outline-none focus:ring-2 focus:ring-amber-500/50"
                  />
                </div>
              </div>
              
              <div>
                <label className="block text-sm font-medium text-[rgb(var(--foreground))] mb-1">Condition</label>
                <select
                  value={inventoryForm.condition}
                  onChange={(e) => setInventoryForm(f => ({ ...f, condition: e.target.value as InventoryCondition }))}
                  className="w-full px-3 py-2 rounded-lg bg-[rgb(var(--secondary))] border border-[rgb(var(--border))] text-[rgb(var(--foreground))] focus:outline-none focus:ring-2 focus:ring-amber-500/50"
                >
                  {CONDITION_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>{opt.label}</option>
                  ))}
                </select>
              </div>
              
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="is_foil"
                  checked={inventoryForm.is_foil}
                  onChange={(e) => setInventoryForm(f => ({ ...f, is_foil: e.target.checked }))}
                  className="w-4 h-4 rounded border-[rgb(var(--border))] bg-[rgb(var(--secondary))] text-amber-500 focus:ring-amber-500/50"
                />
                <label htmlFor="is_foil" className="text-sm text-[rgb(var(--foreground))]">Foil</label>
              </div>
              
              <div className="flex justify-end gap-2 pt-2">
                <Button variant="secondary" onClick={() => setShowAddInventory(false)}>
                  Cancel
                </Button>
                <Button
                  variant="primary"
                  onClick={() => addToInventoryMutation.mutate()}
                  disabled={addToInventoryMutation.isPending}
                  className="bg-gradient-to-r from-amber-500 to-orange-600 hover:from-amber-600 hover:to-orange-700"
                >
                  {addToInventoryMutation.isPending ? 'Adding...' : 'Add to Inventory'}
                </Button>
              </div>
              
              {addToInventoryMutation.isSuccess && (
                <div className="p-3 rounded-lg bg-green-500/10 border border-green-500/30 text-green-400 text-sm text-center">
                  Added to inventory!
                </div>
              )}
              
              {addToInventoryMutation.isError && (
                <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/30 text-red-400 text-sm text-center">
                  Failed to add: {(addToInventoryMutation.error as Error).message}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      )}

      {/* Signals & Recommendations */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Signals */}
        <Card>
          <CardHeader>
            <CardTitle>Recent Signals</CardTitle>
          </CardHeader>
          <CardContent>
            {recent_signals.length > 0 ? (
              <div className="space-y-3">
                {recent_signals.map((signal, idx) => (
                  <div
                    key={idx}
                    className="flex items-center justify-between py-2 border-b border-[rgb(var(--border))] last:border-0"
                  >
                    <div>
                      <p className="font-medium text-[rgb(var(--foreground))]">
                        {signal.signal_type.replace(/_/g, ' ')}
                      </p>
                      <p className="text-xs text-[rgb(var(--muted-foreground))]">{signal.date}</p>
                    </div>
                    {signal.confidence && (
                      <Badge variant="info">{Math.round(signal.confidence * 100)}%</Badge>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-[rgb(var(--muted-foreground))] text-center py-4">
                No recent signals
              </p>
            )}
          </CardContent>
        </Card>

        {/* Recommendations */}
        <Card>
          <CardHeader>
            <CardTitle>Active Recommendations</CardTitle>
          </CardHeader>
          <CardContent>
            {active_recommendations.length > 0 ? (
              <div className="space-y-4">
                {active_recommendations.map((rec, idx) => (
                  <div
                    key={idx}
                    className="p-3 rounded-lg bg-[rgb(var(--secondary))]"
                  >
                    <div className="flex items-center justify-between mb-2">
                      <ActionBadge action={rec.action} />
                      <Badge variant="info">{Math.round(rec.confidence * 100)}% confidence</Badge>
                    </div>
                    <p className="text-sm text-[rgb(var(--muted-foreground))]">{rec.rationale}</p>
                    {rec.potential_profit_pct && (
                      <p className="text-sm mt-2">
                        <span className="text-[rgb(var(--muted-foreground))]">Potential: </span>
                        <span className="text-green-500 font-medium">
                          {formatPercent(rec.potential_profit_pct)}
                        </span>
                      </p>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-[rgb(var(--muted-foreground))] text-center py-4">
                No active recommendations
              </p>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function StatBox({
  label,
  value,
  valueColor,
}: {
  label: string;
  value: string;
  valueColor?: string;
}) {
  return (
    <div className="p-4 rounded-lg bg-[rgb(var(--secondary))]">
      <p className="text-xs text-[rgb(var(--muted-foreground))]">{label}</p>
      <p className={`text-xl font-bold mt-1 ${valueColor || 'text-[rgb(var(--foreground))]'}`}>
        {value}
      </p>
    </div>
  );
}

