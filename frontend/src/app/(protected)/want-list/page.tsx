'use client';

import React, { useState, useEffect, useCallback } from 'react';
import {
  Star,
  Plus,
  Bell,
  BellOff,
  ExternalLink,
  Trash2,
  AlertCircle,
  Loader2,
  RefreshCw,
  DollarSign,
} from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
  DialogClose,
} from '@/components/ui/dialog';
import { PageHeader } from '@/components/ornate/page-header';
import { PriceChange } from '@/components/ornate/price-change';
import { formatCurrency, cn } from '@/lib/utils';
import { SearchAutocomplete } from '@/components/search/SearchAutocomplete';
import {
  getWantList,
  addToWantList,
  updateWantListItem,
  deleteWantListItem,
  checkWantListPrices,
  ApiError,
} from '@/lib/api';
import type { WantListItem, WantListPriority, WantListDeal } from '@/types';

const priorityColors = {
  high: 'bg-[rgb(var(--destructive))]/20 text-[rgb(var(--destructive))] border-[rgb(var(--destructive))]/30',
  medium: 'bg-[rgb(var(--warning))]/20 text-[rgb(var(--warning))] border-[rgb(var(--warning))]/30',
  low: 'bg-[rgb(var(--muted))]/20 text-muted-foreground border-border',
};

interface WantListItemCardProps {
  item: WantListItem;
  onToggleAlert: (id: number, enabled: boolean) => Promise<void>;
  onDelete: (id: number) => Promise<void>;
  isDeleting: boolean;
}

function WantListItemCard({ item, onToggleAlert, onDelete, isDeleting }: WantListItemCardProps) {
  const [isTogglingAlert, setIsTogglingAlert] = useState(false);

  const targetPrice = parseFloat(item.target_price);
  const currentPrice = item.card.current_price != null ? parseFloat(item.card.current_price) : null;

  const priceDiff = currentPrice != null ? currentPrice - targetPrice : null;
  const priceDiffPct = priceDiff != null && currentPrice != null && currentPrice > 0
    ? (priceDiff / currentPrice) * 100
    : null;
  const isNearTarget = priceDiff != null && priceDiff <= targetPrice * 0.1;
  const isAtTarget = currentPrice != null && currentPrice <= targetPrice;

  const handleToggleAlert = async () => {
    setIsTogglingAlert(true);
    try {
      await onToggleAlert(item.id, !item.alert_enabled);
    } finally {
      setIsTogglingAlert(false);
    }
  };

  const handleDelete = async () => {
    await onDelete(item.id);
  };

  return (
    <Card className={cn(
      'glow-accent transition-all hover:border-[rgb(var(--accent))]/30',
      isAtTarget && 'border-[rgb(var(--success))]/50 bg-[rgb(var(--success))]/5',
      isNearTarget && !isAtTarget && 'border-[rgb(var(--warning))]/50 bg-[rgb(var(--warning))]/5'
    )}>
      <CardContent className="p-4">
        <div className="flex gap-4">
          {/* Card Image Placeholder */}
          <div className="w-16 h-22 shrink-0 rounded overflow-hidden bg-secondary">
            <div className="w-full h-full flex items-center justify-center">
              <Star className="w-6 h-6 text-muted-foreground" />
            </div>
          </div>

          {/* Content */}
          <div className="flex-1 min-w-0">
            <div className="flex items-start justify-between gap-2">
              <div>
                <h3 className="font-heading text-foreground font-medium truncate">{item.card.name}</h3>
                <p className="text-sm text-muted-foreground">{item.card.set_code}</p>
              </div>
              <Badge className={priorityColors[item.priority]}>
                {item.priority}
              </Badge>
            </div>

            {/* Price Info */}
            <div className="mt-3 grid grid-cols-3 gap-4">
              <div>
                <p className="text-xs text-muted-foreground">Current</p>
                <p className="font-medium text-foreground">
                  {currentPrice != null ? formatCurrency(currentPrice) : 'N/A'}
                </p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Target</p>
                <p className="font-medium text-[rgb(var(--success))]">{formatCurrency(targetPrice)}</p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Difference</p>
                {priceDiffPct != null ? (
                  <PriceChange value={-priceDiffPct} format="percent" size="sm" />
                ) : (
                  <span className="text-sm text-muted-foreground">--</span>
                )}
              </div>
            </div>

            {/* Notes */}
            {item.notes && (
              <p className="mt-2 text-sm text-muted-foreground italic truncate">
                &quot;{item.notes}&quot;
              </p>
            )}

            {/* Actions */}
            <div className="mt-3 flex items-center gap-2">
              <Button
                variant="ghost"
                size="sm"
                className={cn(
                  'h-8',
                  item.alert_enabled ? 'text-[rgb(var(--accent))]' : 'text-muted-foreground'
                )}
                onClick={handleToggleAlert}
                disabled={isTogglingAlert}
              >
                {isTogglingAlert ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : item.alert_enabled ? (
                  <Bell className="w-4 h-4" />
                ) : (
                  <BellOff className="w-4 h-4" />
                )}
              </Button>
              <Button
                variant="ghost"
                size="sm"
                className="h-8 text-muted-foreground hover:text-foreground"
                asChild
              >
                <a
                  href={`https://www.tcgplayer.com/search/all/product?q=${encodeURIComponent(item.card.name)}`}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  <ExternalLink className="w-4 h-4 mr-1" />
                  TCGPlayer
                </a>
              </Button>
              <Button
                variant="ghost"
                size="sm"
                className="h-8 text-muted-foreground hover:text-[rgb(var(--destructive))] ml-auto"
                onClick={handleDelete}
                disabled={isDeleting}
              >
                {isDeleting ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Trash2 className="w-4 h-4" />
                )}
              </Button>
            </div>
          </div>
        </div>

        {/* At/Near Target Alert */}
        {isAtTarget && (
          <div className="mt-3 flex items-center gap-2 p-2 rounded-lg bg-[rgb(var(--success))]/10 border border-[rgb(var(--success))]/20">
            <DollarSign className="w-4 h-4 text-[rgb(var(--success))] shrink-0" />
            <p className="text-sm text-[rgb(var(--success))]">
              Price is at or below your target! Time to buy!
            </p>
          </div>
        )}
        {isNearTarget && !isAtTarget && (
          <div className="mt-3 flex items-center gap-2 p-2 rounded-lg bg-[rgb(var(--warning))]/10 border border-[rgb(var(--warning))]/20">
            <AlertCircle className="w-4 h-4 text-[rgb(var(--warning))] shrink-0" />
            <p className="text-sm text-[rgb(var(--warning))]">
              Price is within 10% of your target!
            </p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

interface AddCardDialogProps {
  onAdd: (data: { card_id: number; target_price: number; priority: WantListPriority; alert_enabled: boolean; notes?: string }) => Promise<void>;
  isAdding: boolean;
}

function AddCardDialog({ onAdd, isAdding }: AddCardDialogProps) {
  const [selectedCard, setSelectedCard] = useState<{ id: number; name: string; set_code: string } | null>(null);
  const [targetPrice, setTargetPrice] = useState('');
  const [priority, setPriority] = useState<WantListPriority>('medium');
  const [alertEnabled, setAlertEnabled] = useState(true);
  const [notes, setNotes] = useState('');
  const [isOpen, setIsOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async () => {
    if (!selectedCard) {
      setError('Please select a card');
      return;
    }

    const price = parseFloat(targetPrice);
    if (isNaN(price) || price <= 0) {
      setError('Please enter a valid target price');
      return;
    }

    setError(null);

    try {
      await onAdd({
        card_id: selectedCard.id,
        target_price: price,
        priority,
        alert_enabled: alertEnabled,
        notes: notes || undefined,
      });

      // Reset form and close dialog
      setSelectedCard(null);
      setTargetPrice('');
      setPriority('medium');
      setAlertEnabled(true);
      setNotes('');
      setIsOpen(false);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError('Failed to add card to want list');
      }
    }
  };

  const handleCardSelect = (card: { id: number; name: string; set_code: string }) => {
    setSelectedCard(card);
    setError(null);
  };

  return (
    <Dialog open={isOpen} onOpenChange={setIsOpen}>
      <DialogTrigger asChild>
        <Button className="gradient-arcane text-white glow-accent">
          <Plus className="w-4 h-4 mr-1" />
          Add Card
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Add to Want List</DialogTitle>
        </DialogHeader>
        <div className="space-y-4 pt-4">
          <div className="space-y-2">
            <label className="text-sm font-medium text-foreground">Card Name</label>
            {selectedCard ? (
              <div className="flex items-center justify-between p-2 border rounded-lg bg-secondary">
                <div>
                  <p className="font-medium">{selectedCard.name}</p>
                  <p className="text-sm text-muted-foreground">{selectedCard.set_code}</p>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setSelectedCard(null)}
                >
                  Change
                </Button>
              </div>
            ) : (
              <SearchAutocomplete
                placeholder="Search for a card..."
                onSelect={handleCardSelect}
              />
            )}
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <label className="text-sm font-medium text-foreground">Target Price ($)</label>
              <Input
                type="number"
                placeholder="0.00"
                min="0.01"
                step="0.01"
                value={targetPrice}
                onChange={(e) => setTargetPrice(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium text-foreground">Priority</label>
              <select
                className="w-full px-3 py-2 rounded-lg border border-border bg-card text-foreground"
                value={priority}
                onChange={(e) => setPriority(e.target.value as WantListPriority)}
              >
                <option value="high">High</option>
                <option value="medium">Medium</option>
                <option value="low">Low</option>
              </select>
            </div>
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium text-foreground">Notes (optional)</label>
            <Input
              placeholder="Why do you want this card?"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
            />
          </div>
          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              id="alert"
              className="rounded"
              checked={alertEnabled}
              onChange={(e) => setAlertEnabled(e.target.checked)}
            />
            <label htmlFor="alert" className="text-sm text-foreground">
              Alert me when price reaches target
            </label>
          </div>
          {error && (
            <p className="text-sm text-[rgb(var(--destructive))]">{error}</p>
          )}
          <div className="flex justify-end gap-2 pt-2">
            <DialogClose asChild>
              <Button variant="secondary">Cancel</Button>
            </DialogClose>
            <Button
              className="gradient-arcane text-white"
              onClick={handleSubmit}
              disabled={isAdding}
            >
              {isAdding ? (
                <>
                  <Loader2 className="w-4 h-4 mr-1 animate-spin" />
                  Adding...
                </>
              ) : (
                'Add to List'
              )}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

export default function WantListPage() {
  const [items, setItems] = useState<WantListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [isAdding, setIsAdding] = useState(false);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [sortBy, setSortBy] = useState<'priority' | 'price' | 'date'>('priority');
  const [filterPriority, setFilterPriority] = useState<'all' | WantListPriority>('all');
  const [deals, setDeals] = useState<WantListDeal[]>([]);
  const [isCheckingPrices, setIsCheckingPrices] = useState(false);

  const fetchWantList = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      const response = await getWantList({
        page,
        pageSize: 50,
        priority: filterPriority === 'all' ? undefined : filterPriority,
      });

      setItems(response.items);
      setTotal(response.total);
      setHasMore(response.has_more);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError('Failed to load want list');
      }
    } finally {
      setIsLoading(false);
    }
  }, [page, filterPriority]);

  useEffect(() => {
    fetchWantList();
  }, [fetchWantList]);

  const handleAddCard = async (data: { card_id: number; target_price: number; priority: WantListPriority; alert_enabled: boolean; notes?: string }) => {
    setIsAdding(true);
    try {
      await addToWantList(data);
      await fetchWantList();
    } finally {
      setIsAdding(false);
    }
  };

  const handleToggleAlert = async (id: number, enabled: boolean) => {
    try {
      await updateWantListItem(id, { alert_enabled: enabled });
      setItems(prev => prev.map(item =>
        item.id === id ? { ...item, alert_enabled: enabled } : item
      ));
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError('Failed to update alert setting');
      }
    }
  };

  const handleDelete = async (id: number) => {
    setDeletingId(id);
    try {
      await deleteWantListItem(id);
      setItems(prev => prev.filter(item => item.id !== id));
      setTotal(prev => prev - 1);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError('Failed to delete item');
      }
    } finally {
      setDeletingId(null);
    }
  };

  const handleCheckPrices = async () => {
    setIsCheckingPrices(true);
    try {
      const response = await checkWantListPrices();
      setDeals(response.deals);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError('Failed to check prices');
      }
    } finally {
      setIsCheckingPrices(false);
    }
  };

  // Sort items client-side
  const sortedItems = [...items].sort((a, b) => {
    if (sortBy === 'priority') {
      const order = { high: 0, medium: 1, low: 2 };
      return order[a.priority] - order[b.priority];
    }
    if (sortBy === 'price') {
      const aPrice = a.card.current_price != null ? parseFloat(a.card.current_price) : 0;
      const bPrice = b.card.current_price != null ? parseFloat(b.card.current_price) : 0;
      return bPrice - aPrice;
    }
    return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
  });

  const nearTargetCount = items.filter(item => {
    const currentPrice = item.card.current_price != null ? parseFloat(item.card.current_price) : null;
    const targetPrice = parseFloat(item.target_price);
    if (currentPrice == null) return false;
    return (currentPrice - targetPrice) <= targetPrice * 0.1;
  }).length;

  const totalValue = items.reduce((sum, item) =>
    sum + (item.card.current_price != null ? parseFloat(item.card.current_price) : 0), 0
  );

  const totalTargetValue = items.reduce((sum, item) =>
    sum + parseFloat(item.target_price), 0
  );

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Loader2 className="w-8 h-8 animate-spin text-[rgb(var(--accent))]" />
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-in">
      <PageHeader
        title="Want List"
        subtitle="Track cards you want and get alerted when they hit your target price"
      >
        <div className="flex items-center gap-2">
          <Button
            variant="secondary"
            onClick={handleCheckPrices}
            disabled={isCheckingPrices || items.length === 0}
          >
            {isCheckingPrices ? (
              <>
                <Loader2 className="w-4 h-4 mr-1 animate-spin" />
                Checking...
              </>
            ) : (
              <>
                <RefreshCw className="w-4 h-4 mr-1" />
                Check Prices
              </>
            )}
          </Button>
          <AddCardDialog onAdd={handleAddCard} isAdding={isAdding} />
        </div>
      </PageHeader>

      {error && (
        <div className="p-4 rounded-lg bg-[rgb(var(--destructive))]/10 border border-[rgb(var(--destructive))]/20">
          <p className="text-[rgb(var(--destructive))]">{error}</p>
        </div>
      )}

      {/* Deals Alert */}
      {deals.length > 0 && (
        <Card className="border-[rgb(var(--success))]/50 bg-[rgb(var(--success))]/5">
          <CardContent className="p-4">
            <div className="flex items-start gap-3">
              <DollarSign className="w-5 h-5 text-[rgb(var(--success))] shrink-0 mt-0.5" />
              <div>
                <h3 className="font-heading font-medium text-[rgb(var(--success))]">
                  {deals.length} Deal{deals.length !== 1 ? 's' : ''} Found!
                </h3>
                <p className="text-sm text-muted-foreground mt-1">
                  The following cards are at or below your target price:
                </p>
                <ul className="mt-2 space-y-1">
                  {deals.map(deal => (
                    <li key={deal.id} className="text-sm">
                      <span className="font-medium">{deal.card_name}</span>
                      <span className="text-muted-foreground"> - </span>
                      <span className="text-[rgb(var(--success))]">{formatCurrency(deal.current_price)}</span>
                      <span className="text-muted-foreground"> (target: {formatCurrency(deal.target_price)}, save {deal.savings_pct}%)</span>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Summary Stats */}
      <div className="grid grid-cols-4 gap-4">
        <Card className="glow-accent">
          <CardContent className="p-4 text-center">
            <p className="text-3xl font-bold text-foreground">{total}</p>
            <p className="text-sm text-muted-foreground">Cards Wanted</p>
          </CardContent>
        </Card>
        <Card className="glow-accent">
          <CardContent className="p-4 text-center">
            <p className="text-3xl font-bold text-[rgb(var(--success))]">{nearTargetCount}</p>
            <p className="text-sm text-muted-foreground">Near Target</p>
          </CardContent>
        </Card>
        <Card className="glow-accent">
          <CardContent className="p-4 text-center">
            <p className="text-3xl font-bold text-foreground">{formatCurrency(totalValue)}</p>
            <p className="text-sm text-muted-foreground">Current Total</p>
          </CardContent>
        </Card>
        <Card className="glow-accent">
          <CardContent className="p-4 text-center">
            <p className="text-3xl font-bold text-[rgb(var(--accent))]">{formatCurrency(totalTargetValue)}</p>
            <p className="text-sm text-muted-foreground">Target Total</p>
          </CardContent>
        </Card>
      </div>

      {/* Filters & Sort */}
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2">
          <span className="text-sm text-muted-foreground">Priority:</span>
          {(['all', 'high', 'medium', 'low'] as const).map((priority) => (
            <Button
              key={priority}
              variant={filterPriority === priority ? 'default' : 'secondary'}
              size="sm"
              onClick={() => {
                setFilterPriority(priority);
                setPage(1);
              }}
              className={filterPriority === priority ? 'gradient-arcane text-white' : ''}
            >
              {priority === 'all' ? 'All' : priority.charAt(0).toUpperCase() + priority.slice(1)}
            </Button>
          ))}
        </div>

        <div className="flex items-center gap-2 ml-auto">
          <span className="text-sm text-muted-foreground">Sort:</span>
          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value as typeof sortBy)}
            className="px-3 py-1.5 text-sm rounded-lg border border-border bg-card text-foreground"
          >
            <option value="priority">Priority</option>
            <option value="price">Price</option>
            <option value="date">Date Added</option>
          </select>
        </div>
      </div>

      {/* Want List Items */}
      {sortedItems.length === 0 ? (
        <Card className="glow-accent">
          <CardContent className="py-12 text-center">
            <Star className="w-12 h-12 mx-auto text-muted-foreground mb-4" />
            <p className="text-muted-foreground">
              {filterPriority === 'all'
                ? 'Your want list is empty. Add cards to track their prices!'
                : `No ${filterPriority} priority cards in your want list.`}
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="grid md:grid-cols-2 gap-4">
          {sortedItems.map((item) => (
            <WantListItemCard
              key={item.id}
              item={item}
              onToggleAlert={handleToggleAlert}
              onDelete={handleDelete}
              isDeleting={deletingId === item.id}
            />
          ))}
        </div>
      )}

      {/* Pagination */}
      {hasMore && (
        <div className="flex justify-center">
          <Button
            variant="secondary"
            onClick={() => setPage(prev => prev + 1)}
          >
            Load More
          </Button>
        </div>
      )}
    </div>
  );
}
