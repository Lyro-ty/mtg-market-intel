'use client';

import { useParams } from 'next/navigation';
import { useQuery, useQueryClient, useMutation } from '@tanstack/react-query';
import { useState } from 'react';
import Image from 'next/image';
import { ArrowLeft, Package, Plus, X, Heart, ExternalLink } from 'lucide-react';
import Link from 'next/link';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Badge, ActionBadge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { LoadingPage } from '@/components/ui/Loading';
import { PriceChart } from '@/components/charts/PriceChart';
import { SpreadChart } from '@/components/charts/SpreadChart';
import { getCard, getCardHistory, refreshCard, createInventoryItem, getSimilarCards, addToWantList } from '@/lib/api';
import { formatCurrency, formatPercent, getRarityColor, getTcgPlayerUrl } from '@/lib/utils';
import type { InventoryCondition, WantListPriority } from '@/types';

const CONDITION_OPTIONS: { value: InventoryCondition; label: string }[] = [
  { value: 'MINT', label: 'Mint' },
  { value: 'NEAR_MINT', label: 'Near Mint' },
  { value: 'LIGHTLY_PLAYED', label: 'Lightly Played' },
  { value: 'MODERATELY_PLAYED', label: 'Moderately Played' },
  { value: 'HEAVILY_PLAYED', label: 'Heavily Played' },
  { value: 'DAMAGED', label: 'Damaged' },
];

const PRIORITY_OPTIONS: { value: WantListPriority; label: string }[] = [
  { value: 'low', label: 'Low' },
  { value: 'medium', label: 'Medium' },
  { value: 'high', label: 'High' },
];

export default function CardDetailPage() {
  const params = useParams();
  const cardId = Number(params.id);

  const [isRefreshing, setIsRefreshing] = useState(false);
  const [showAddInventory, setShowAddInventory] = useState(false);
  const [showAddWantList, setShowAddWantList] = useState(false);
  const [selectedCondition, setSelectedCondition] = useState<string>('');  // Empty = all conditions
  const [selectedFoil, setSelectedFoil] = useState<string>('');  // Empty = all, 'false' = non-foil, 'true' = foil
  const [inventoryForm, setInventoryForm] = useState({
    quantity: 1,
    condition: 'NEAR_MINT' as InventoryCondition,
    is_foil: false,
    acquisition_price: '',
  });
  const [wantListForm, setWantListForm] = useState({
    target_price: '',
    priority: 'medium' as WantListPriority,
    alert_enabled: true,
    notes: '',
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

  const addToWantListMutation = useMutation({
    mutationFn: () => addToWantList({
      card_id: cardId,
      target_price: parseFloat(wantListForm.target_price) || 0,
      priority: wantListForm.priority,
      alert_enabled: wantListForm.alert_enabled,
      notes: wantListForm.notes || undefined,
    }),
    onSuccess: () => {
      setShowAddWantList(false);
      setWantListForm({ target_price: '', priority: 'medium', alert_enabled: true, notes: '' });
      queryClient.invalidateQueries({ queryKey: ['want-list'] });
    },
  });

  const { data: cardDetail, isLoading, error } = useQuery({
    queryKey: ['card', cardId],
    queryFn: () => getCard(cardId),
    enabled: !!cardId,
    refetchInterval: 60000,  // Auto-refresh every 60 seconds for live data
    refetchIntervalInBackground: true,  // Continue refreshing when tab is in background
  });

  // Parse foil filter value for consistent query key and API call
  const isFoilValue = selectedFoil === '' ? undefined : selectedFoil === 'true';

  const { data: history, refetch: refetchHistory } = useQuery({
    queryKey: ['card', cardId, 'history', selectedCondition, isFoilValue],
    queryFn: () => getCardHistory(cardId, {
      days: 30,
      condition: selectedCondition || undefined,
      isFoil: isFoilValue
    }),
    enabled: !!cardId,
    refetchInterval: 60000,  // Auto-refresh every 60 seconds for live data
    refetchIntervalInBackground: true,
  });

  const { data: similarCardsData, isLoading: loadingSimilar } = useQuery({
    queryKey: ['card', cardId, 'similar'],
    queryFn: () => getSimilarCards(cardId, 8),
    enabled: !!cardId,
    staleTime: 5 * 60 * 1000,  // Cache for 5 minutes - similar cards don't change often
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
      // Use sync=true and force=true to always fetch fresh data
      const updatedData = await refreshCard(cardId, { sync: true, force: true });
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
              <Button
                variant="primary"
                size="sm"
                onClick={() => setShowAddWantList(true)}
                className="bg-gradient-to-r from-pink-500 to-rose-600 hover:from-pink-600 hover:to-rose-700"
              >
                <Heart className="w-4 h-4 mr-1" />
                Add to Want List
              </Button>
              <Button
                variant="secondary"
                size="sm"
                asChild
              >
                <a
                  href={getTcgPlayerUrl(card.name, card.set_code)}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  <ExternalLink className="w-4 h-4 mr-1" />
                  Buy on TCGPlayer
                </a>
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
                aria-label="Close add to inventory modal"
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

      {/* Add to Want List Modal */}
      {showAddWantList && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
          <Card className="w-full max-w-md bg-[rgb(var(--card))] border-[rgb(var(--border))]">
            <div className="flex items-center justify-between p-4 border-b border-[rgb(var(--border))]">
              <div className="flex items-center gap-3">
                <div className="p-2 rounded-lg bg-gradient-to-br from-pink-500 to-rose-600">
                  <Heart className="w-5 h-5 text-white" />
                </div>
                <h2 className="text-lg font-semibold text-[rgb(var(--foreground))]">Add to Want List</h2>
              </div>
              <button
                onClick={() => setShowAddWantList(false)}
                className="p-2 rounded-lg hover:bg-[rgb(var(--secondary))] transition-colors"
                aria-label="Close add to want list modal"
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
                  <label className="block text-sm font-medium text-[rgb(var(--foreground))] mb-1">Target Price *</label>
                  <input
                    type="number"
                    step="0.01"
                    min="0"
                    placeholder="$0.00"
                    value={wantListForm.target_price}
                    onChange={(e) => setWantListForm(f => ({ ...f, target_price: e.target.value }))}
                    className="w-full px-3 py-2 rounded-lg bg-[rgb(var(--secondary))] border border-[rgb(var(--border))] text-[rgb(var(--foreground))] placeholder:text-[rgb(var(--muted-foreground))] focus:outline-none focus:ring-2 focus:ring-pink-500/50"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-[rgb(var(--foreground))] mb-1">Priority</label>
                  <select
                    value={wantListForm.priority}
                    onChange={(e) => setWantListForm(f => ({ ...f, priority: e.target.value as WantListPriority }))}
                    className="w-full px-3 py-2 rounded-lg bg-[rgb(var(--secondary))] border border-[rgb(var(--border))] text-[rgb(var(--foreground))] focus:outline-none focus:ring-2 focus:ring-pink-500/50"
                  >
                    {PRIORITY_OPTIONS.map((opt) => (
                      <option key={opt.value} value={opt.value}>{opt.label}</option>
                    ))}
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-[rgb(var(--foreground))] mb-1">Notes (optional)</label>
                <textarea
                  placeholder="Why do you want this card?"
                  value={wantListForm.notes}
                  onChange={(e) => setWantListForm(f => ({ ...f, notes: e.target.value }))}
                  rows={2}
                  className="w-full px-3 py-2 rounded-lg bg-[rgb(var(--secondary))] border border-[rgb(var(--border))] text-[rgb(var(--foreground))] placeholder:text-[rgb(var(--muted-foreground))] focus:outline-none focus:ring-2 focus:ring-pink-500/50 resize-none"
                />
              </div>

              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="alert_enabled"
                  checked={wantListForm.alert_enabled}
                  onChange={(e) => setWantListForm(f => ({ ...f, alert_enabled: e.target.checked }))}
                  className="w-4 h-4 rounded border-[rgb(var(--border))] bg-[rgb(var(--secondary))] text-pink-500 focus:ring-pink-500/50"
                />
                <label htmlFor="alert_enabled" className="text-sm text-[rgb(var(--foreground))]">Alert me when price drops below target</label>
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <Button variant="secondary" onClick={() => setShowAddWantList(false)}>
                  Cancel
                </Button>
                <Button
                  variant="primary"
                  onClick={() => addToWantListMutation.mutate()}
                  disabled={addToWantListMutation.isPending || !wantListForm.target_price}
                  className="bg-gradient-to-r from-pink-500 to-rose-600 hover:from-pink-600 hover:to-rose-700"
                >
                  {addToWantListMutation.isPending ? 'Adding...' : 'Add to Want List'}
                </Button>
              </div>

              {addToWantListMutation.isSuccess && (
                <div className="p-3 rounded-lg bg-green-500/10 border border-green-500/30 text-green-400 text-sm text-center">
                  Added to want list!
                </div>
              )}

              {addToWantListMutation.isError && (
                <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/30 text-red-400 text-sm text-center">
                  Failed to add: {(addToWantListMutation.error as Error).message}
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

      {/* Similar Cards Section */}
      <section className="mt-8">
        <h2 className="text-xl font-bold text-[rgb(var(--foreground))] mb-4">Similar Cards</h2>
        {loadingSimilar ? (
          <div className="flex gap-4 overflow-x-auto pb-4">
            {[...Array(4)].map((_, idx) => (
              <div key={idx} className="flex-shrink-0 w-40">
                <div className="aspect-[5/7] rounded-lg bg-[rgb(var(--secondary))] animate-pulse" />
                <div className="h-4 mt-2 rounded bg-[rgb(var(--secondary))] animate-pulse" />
                <div className="h-3 mt-1 rounded bg-[rgb(var(--secondary))] animate-pulse w-2/3" />
              </div>
            ))}
          </div>
        ) : similarCardsData && similarCardsData.similar_cards.length > 0 ? (
          <div className="flex gap-4 overflow-x-auto pb-4 scrollbar-thin scrollbar-thumb-[rgb(var(--border))] scrollbar-track-transparent">
            {similarCardsData.similar_cards.map((similarCard) => (
              <Link key={similarCard.id} href={`/cards/${similarCard.id}`}>
                <div className="flex-shrink-0 w-40 group cursor-pointer">
                  <div className="relative aspect-[5/7] rounded-lg overflow-hidden bg-[rgb(var(--secondary))] shadow-md group-hover:shadow-xl transition-shadow">
                    {similarCard.image_url ? (
                      <Image
                        src={similarCard.image_url}
                        alt={similarCard.name}
                        fill
                        className="object-cover group-hover:scale-105 transition-transform duration-200"
                        sizes="160px"
                        unoptimized
                      />
                    ) : (
                      <div className="absolute inset-0 flex items-center justify-center text-[rgb(var(--muted-foreground))] text-sm">
                        No Image
                      </div>
                    )}
                    <span className="absolute top-2 right-2 px-2 py-0.5 rounded-full bg-amber-500 text-white text-xs font-semibold shadow">
                      {Math.round((similarCard.similarity_score ?? 0) * 100)}%
                    </span>
                  </div>
                  <div className="mt-2">
                    <p className="text-sm font-medium text-[rgb(var(--foreground))] truncate group-hover:text-amber-500 transition-colors">
                      {similarCard.name}
                    </p>
                    <p className="text-xs text-[rgb(var(--muted-foreground))] uppercase">
                      {similarCard.set_code}
                    </p>
                  </div>
                </div>
              </Link>
            ))}
          </div>
        ) : (
          <p className="text-[rgb(var(--muted-foreground))] text-center py-8">
            No similar cards found
          </p>
        )}
      </section>
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

