'use client';

import React, { useState } from 'react';
import {
  Star,
  Plus,
  Bell,
  BellOff,
  ExternalLink,
  Trash2,
  ChevronDown,
  TrendingDown,
  TrendingUp,
  Target,
  AlertCircle,
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import { PageHeader } from '@/components/ornate/page-header';
import { PriceChange } from '@/components/ornate/price-change';
import { formatCurrency, cn } from '@/lib/utils';

interface WantListItem {
  id: number;
  cardName: string;
  setCode: string;
  setName: string;
  imageUrl?: string;
  currentPrice: number;
  targetPrice: number;
  priority: 'high' | 'medium' | 'low';
  alertEnabled: boolean;
  addedDate: string;
  notes?: string;
}

// Mock data for want list
const mockWantList: WantListItem[] = [
  {
    id: 1,
    cardName: 'Force of Will',
    setCode: 'ALL',
    setName: 'Alliances',
    currentPrice: 89.99,
    targetPrice: 75.00,
    priority: 'high',
    alertEnabled: true,
    addedDate: '2024-01-15',
    notes: 'Need for Legacy deck',
  },
  {
    id: 2,
    cardName: 'Ragavan, Nimble Pilferer',
    setCode: 'MH2',
    setName: 'Modern Horizons 2',
    currentPrice: 52.50,
    targetPrice: 45.00,
    priority: 'high',
    alertEnabled: true,
    addedDate: '2024-02-01',
  },
  {
    id: 3,
    cardName: 'The One Ring',
    setCode: 'LTR',
    setName: 'Lord of the Rings',
    currentPrice: 68.00,
    targetPrice: 50.00,
    priority: 'medium',
    alertEnabled: false,
    addedDate: '2024-02-20',
    notes: 'Wait for rotation dip',
  },
  {
    id: 4,
    cardName: 'Seasoned Dungeoneer',
    setCode: 'CLB',
    setName: "Commander Legends: Baldur's Gate",
    currentPrice: 12.50,
    targetPrice: 10.00,
    priority: 'low',
    alertEnabled: true,
    addedDate: '2024-03-01',
  },
  {
    id: 5,
    cardName: 'Wrenn and Six',
    setCode: 'MH1',
    setName: 'Modern Horizons',
    currentPrice: 45.00,
    targetPrice: 35.00,
    priority: 'medium',
    alertEnabled: true,
    addedDate: '2024-03-10',
  },
];

const priorityColors = {
  high: 'bg-[rgb(var(--destructive))]/20 text-[rgb(var(--destructive))] border-[rgb(var(--destructive))]/30',
  medium: 'bg-[rgb(var(--warning))]/20 text-[rgb(var(--warning))] border-[rgb(var(--warning))]/30',
  low: 'bg-[rgb(var(--muted))]/20 text-muted-foreground border-border',
};

function WantListItemCard({ item }: { item: WantListItem }) {
  const priceDiff = item.currentPrice - item.targetPrice;
  const priceDiffPct = (priceDiff / item.currentPrice) * 100;
  const isNearTarget = priceDiff <= item.targetPrice * 0.1; // Within 10% of target

  return (
    <Card className={cn(
      'glow-accent transition-all hover:border-[rgb(var(--accent))]/30',
      isNearTarget && 'border-[rgb(var(--success))]/50 bg-[rgb(var(--success))]/5'
    )}>
      <CardContent className="p-4">
        <div className="flex gap-4">
          {/* Card Image */}
          <div className="w-16 h-22 shrink-0 rounded overflow-hidden bg-secondary">
            {item.imageUrl ? (
              <img src={item.imageUrl} alt={item.cardName} className="w-full h-full object-cover" />
            ) : (
              <div className="w-full h-full flex items-center justify-center">
                <Star className="w-6 h-6 text-muted-foreground" />
              </div>
            )}
          </div>

          {/* Content */}
          <div className="flex-1 min-w-0">
            <div className="flex items-start justify-between gap-2">
              <div>
                <h3 className="font-heading text-foreground font-medium truncate">{item.cardName}</h3>
                <p className="text-sm text-muted-foreground">{item.setName}</p>
              </div>
              <Badge className={priorityColors[item.priority]}>
                {item.priority}
              </Badge>
            </div>

            {/* Price Info */}
            <div className="mt-3 grid grid-cols-3 gap-4">
              <div>
                <p className="text-xs text-muted-foreground">Current</p>
                <p className="font-medium text-foreground">{formatCurrency(item.currentPrice)}</p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Target</p>
                <p className="font-medium text-[rgb(var(--success))]">{formatCurrency(item.targetPrice)}</p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Difference</p>
                <PriceChange value={-priceDiffPct} format="percent" size="sm" />
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
                  item.alertEnabled ? 'text-[rgb(var(--accent))]' : 'text-muted-foreground'
                )}
              >
                {item.alertEnabled ? <Bell className="w-4 h-4" /> : <BellOff className="w-4 h-4" />}
              </Button>
              <Button
                variant="ghost"
                size="sm"
                className="h-8 text-muted-foreground hover:text-foreground"
                asChild
              >
                <a
                  href={`https://www.tcgplayer.com/search/all/product?q=${encodeURIComponent(item.cardName)}`}
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
              >
                <Trash2 className="w-4 h-4" />
              </Button>
            </div>
          </div>
        </div>

        {/* Near Target Alert */}
        {isNearTarget && (
          <div className="mt-3 flex items-center gap-2 p-2 rounded-lg bg-[rgb(var(--success))]/10 border border-[rgb(var(--success))]/20">
            <AlertCircle className="w-4 h-4 text-[rgb(var(--success))] shrink-0" />
            <p className="text-sm text-[rgb(var(--success))]">
              Price is within 10% of your target!
            </p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function AddCardDialog() {
  return (
    <Dialog>
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
            <Input placeholder="Search for a card..." />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <label className="text-sm font-medium text-foreground">Target Price</label>
              <Input type="number" placeholder="0.00" />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium text-foreground">Priority</label>
              <select className="w-full px-3 py-2 rounded-lg border border-border bg-card text-foreground">
                <option value="high">High</option>
                <option value="medium">Medium</option>
                <option value="low">Low</option>
              </select>
            </div>
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium text-foreground">Notes (optional)</label>
            <Input placeholder="Why do you want this card?" />
          </div>
          <div className="flex items-center gap-2">
            <input type="checkbox" id="alert" className="rounded" defaultChecked />
            <label htmlFor="alert" className="text-sm text-foreground">
              Alert me when price reaches target
            </label>
          </div>
          <div className="flex justify-end gap-2 pt-2">
            <Button variant="secondary">Cancel</Button>
            <Button className="gradient-arcane text-white">Add to List</Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

export default function WantListPage() {
  const [sortBy, setSortBy] = useState<'priority' | 'price' | 'date'>('priority');
  const [filterPriority, setFilterPriority] = useState<'all' | 'high' | 'medium' | 'low'>('all');

  // Filter and sort items
  const filteredItems = mockWantList
    .filter(item => filterPriority === 'all' || item.priority === filterPriority)
    .sort((a, b) => {
      if (sortBy === 'priority') {
        const order = { high: 0, medium: 1, low: 2 };
        return order[a.priority] - order[b.priority];
      }
      if (sortBy === 'price') return b.currentPrice - a.currentPrice;
      return new Date(b.addedDate).getTime() - new Date(a.addedDate).getTime();
    });

  const nearTargetCount = mockWantList.filter(
    item => (item.currentPrice - item.targetPrice) <= item.targetPrice * 0.1
  ).length;

  const totalValue = mockWantList.reduce((sum, item) => sum + item.currentPrice, 0);
  const totalTargetValue = mockWantList.reduce((sum, item) => sum + item.targetPrice, 0);

  return (
    <div className="space-y-6 animate-in">
      <PageHeader
        title="Want List"
        subtitle="Track cards you want and get alerted when they hit your target price"
      >
        <AddCardDialog />
      </PageHeader>

      {/* Summary Stats */}
      <div className="grid grid-cols-4 gap-4">
        <Card className="glow-accent">
          <CardContent className="p-4 text-center">
            <p className="text-3xl font-bold text-foreground">{mockWantList.length}</p>
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
              onClick={() => setFilterPriority(priority)}
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
      {filteredItems.length === 0 ? (
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
          {filteredItems.map((item) => (
            <WantListItemCard key={item.id} item={item} />
          ))}
        </div>
      )}
    </div>
  );
}
