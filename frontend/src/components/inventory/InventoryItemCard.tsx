'use client';

import Image from 'next/image';
import Link from 'next/link';
import { Sparkles, TrendingUp, TrendingDown, Package, Trash2, Edit2 } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { formatCurrency, formatRelativeTime } from '@/lib/utils';
import type { InventoryItem } from '@/types';

interface InventoryItemCardProps {
  item: InventoryItem;
  onClick?: () => void;
  onDelete?: (itemId: number) => void;
  onToggleFoil?: (itemId: number, isFoil: boolean) => void;
  onEdit?: (item: InventoryItem) => void;
}

const CONDITION_LABELS: Record<string, string> = {
  MINT: 'M',
  NEAR_MINT: 'NM',
  LIGHTLY_PLAYED: 'LP',
  MODERATELY_PLAYED: 'MP',
  HEAVILY_PLAYED: 'HP',
  DAMAGED: 'DMG',
};

const CONDITION_COLORS: Record<string, string> = {
  MINT: 'bg-emerald-500/20 text-emerald-400',
  NEAR_MINT: 'bg-green-500/20 text-green-400',
  LIGHTLY_PLAYED: 'bg-yellow-500/20 text-yellow-400',
  MODERATELY_PLAYED: 'bg-orange-500/20 text-orange-400',
  HEAVILY_PLAYED: 'bg-red-500/20 text-red-400',
  DAMAGED: 'bg-red-700/20 text-red-500',
};

export function InventoryItemCard({ item, onClick, onDelete, onToggleFoil, onEdit }: InventoryItemCardProps) {
  const profitLoss = item.profit_loss ?? (
    item.current_value && item.acquisition_price
      ? (item.current_value - item.acquisition_price) * item.quantity
      : null
  );
  
  const profitLossPct = item.profit_loss_pct ?? (
    item.current_value && item.acquisition_price && item.acquisition_price > 0
      ? ((item.current_value - item.acquisition_price) / item.acquisition_price) * 100
      : null
  );
  
  const isProfit = profitLoss !== null && profitLoss >= 0;
  
  return (
    <div onClick={onClick} className={onClick ? 'cursor-pointer' : ''}>
      <Card className="group hover:border-amber-500/50 transition-all">
        <CardContent className="p-0">
        <div className="flex gap-4 p-4">
          {/* Card Image */}
          <Link href={`/cards/${item.card_id}`} className="shrink-0" onClick={(e) => e.stopPropagation()}>
            <div className="w-20 h-28 relative rounded-lg overflow-hidden bg-[rgb(var(--secondary))]">
              {item.card_image_url ? (
                <Image
                  src={item.card_image_url}
                  alt={item.card_name}
                  fill
                  className="object-cover"
                  sizes="80px"
                />
              ) : (
                <div className="absolute inset-0 flex items-center justify-center text-xs text-[rgb(var(--muted-foreground))]">
                  No Image
                </div>
              )}
              {item.is_foil && (
                <div className="absolute top-1 right-1 p-0.5 rounded bg-gradient-to-br from-purple-500 to-pink-500">
                  <Sparkles className="w-3 h-3 text-white" />
                </div>
              )}
            </div>
          </Link>
          
          {/* Content */}
          <div className="flex-1 min-w-0">
            {/* Header */}
            <div className="flex items-start justify-between gap-2 mb-2">
              <div>
                <Link
                  href={`/cards/${item.card_id}`}
                  className="font-semibold text-[rgb(var(--foreground))] hover:text-amber-500 transition-colors line-clamp-1"
                  onClick={(e) => e.stopPropagation()}
                >
                  {item.card_name}
                </Link>
                <div className="flex items-center gap-2 text-sm text-[rgb(var(--muted-foreground))]">
                  <span>{item.card_set}</span>
                  <span className={`px-1.5 py-0.5 rounded text-xs font-medium ${CONDITION_COLORS[item.condition]}`}>
                    {CONDITION_LABELS[item.condition]}
                  </span>
                </div>
              </div>
              <div className="flex items-center gap-1 text-[rgb(var(--foreground))]">
                <Package className="w-4 h-4 text-[rgb(var(--muted-foreground))]" />
                <span className="font-bold">{item.quantity}x</span>
              </div>
            </div>
            
            {/* Price Info */}
            <div className="grid grid-cols-2 gap-3 mb-3 text-sm">
              <div>
                <span className="text-[rgb(var(--muted-foreground))]">Current: </span>
                <span className="font-medium text-[rgb(var(--foreground))]">
                  {formatCurrency(item.current_value)}
                </span>
              </div>
              <div>
                <span className="text-[rgb(var(--muted-foreground))]">Paid: </span>
                <span className="font-medium text-[rgb(var(--foreground))]">
                  {formatCurrency(item.acquisition_price)}
                </span>
              </div>
            </div>
            
            {/* Profit/Loss */}
            {profitLoss !== null && (
              <div className={`flex items-center gap-2 p-2 rounded-lg ${
                isProfit ? 'bg-green-500/10' : 'bg-red-500/10'
              }`}>
                {isProfit ? (
                  <TrendingUp className="w-4 h-4 text-green-500" />
                ) : (
                  <TrendingDown className="w-4 h-4 text-red-500" />
                )}
                <span className={`font-semibold ${isProfit ? 'text-green-500' : 'text-red-500'}`}>
                  {isProfit ? '+' : ''}{formatCurrency(profitLoss)}
                </span>
                {profitLossPct !== null && (
                  <Badge
                    variant={isProfit ? 'success' : 'danger'}
                    size="sm"
                  >
                    {isProfit ? '+' : ''}{profitLossPct.toFixed(1)}%
                  </Badge>
                )}
              </div>
            )}
            
            {/* Footer */}
            <div className="flex items-center justify-between mt-2">
              <div className="flex items-center gap-2 text-xs text-[rgb(var(--muted-foreground))]">
                {item.acquisition_source && (
                  <span>From: {item.acquisition_source}</span>
                )}
                <span>{formatRelativeTime(item.created_at)}</span>
              </div>
              
              {/* Action Buttons */}
              <div className="flex items-center gap-1">
                {onToggleFoil && (
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={(e) => {
                      e.stopPropagation();
                      onToggleFoil(item.id, !item.is_foil);
                    }}
                    className="h-7 px-2"
                    title={item.is_foil ? 'Mark as non-foil' : 'Mark as foil'}
                  >
                    <Sparkles className={`w-3 h-3 ${item.is_foil ? 'text-purple-500' : ''}`} />
                  </Button>
                )}
                {onEdit && (
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={(e) => {
                      e.stopPropagation();
                      onEdit(item);
                    }}
                    className="h-7 px-2"
                    title="Edit item"
                  >
                    <Edit2 className="w-3 h-3" />
                  </Button>
                )}
                {onDelete && (
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={(e) => {
                      e.stopPropagation();
                      if (confirm(`Are you sure you want to remove ${item.card_name} from your inventory?`)) {
                        onDelete(item.id);
                      }
                    }}
                    className="h-7 px-2 text-red-500 hover:text-red-600 hover:bg-red-500/10"
                    title="Remove from inventory"
                  >
                    <Trash2 className="w-3 h-3" />
                  </Button>
                )}
              </div>
            </div>
          </div>
        </div>
      </CardContent>
      </Card>
    </div>
  );
}
