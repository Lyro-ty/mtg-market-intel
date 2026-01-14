import Link from 'next/link';
import { Package } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { formatCurrency } from '@/lib/utils';
import type { TradeItem } from '@/types';

interface TradeItemCardProps {
  item: TradeItem;
}

const CONDITION_LABELS: Record<string, string> = {
  MINT: 'M',
  NEAR_MINT: 'NM',
  LIGHTLY_PLAYED: 'LP',
  MODERATELY_PLAYED: 'MP',
  HEAVILY_PLAYED: 'HP',
  DAMAGED: 'DMG',
  // Also support short versions directly
  M: 'M',
  NM: 'NM',
  LP: 'LP',
  MP: 'MP',
  HP: 'HP',
  DMG: 'DMG',
};

const CONDITION_COLORS: Record<string, string> = {
  MINT: 'bg-emerald-500/20 text-emerald-400',
  NEAR_MINT: 'bg-green-500/20 text-green-400',
  LIGHTLY_PLAYED: 'bg-yellow-500/20 text-yellow-400',
  MODERATELY_PLAYED: 'bg-orange-500/20 text-orange-400',
  HEAVILY_PLAYED: 'bg-red-500/20 text-red-400',
  DAMAGED: 'bg-red-700/20 text-red-500',
  // Short versions
  M: 'bg-emerald-500/20 text-emerald-400',
  NM: 'bg-green-500/20 text-green-400',
  LP: 'bg-yellow-500/20 text-yellow-400',
  MP: 'bg-orange-500/20 text-orange-400',
  HP: 'bg-red-500/20 text-red-400',
  DMG: 'bg-red-700/20 text-red-500',
};

/**
 * Compact card component for displaying a single trade item.
 * Used in trade lists and trade detail views.
 */
export function TradeItemCard({ item }: TradeItemCardProps) {
  const conditionLabel = item.condition ? CONDITION_LABELS[item.condition] ?? item.condition : null;
  const conditionColor = item.condition ? CONDITION_COLORS[item.condition] ?? 'bg-gray-500/20 text-gray-400' : null;

  return (
    <div className="flex items-center gap-3 p-2 rounded-lg bg-[rgb(var(--secondary))]/50 hover:bg-[rgb(var(--secondary))] transition-colors">
      {/* Card Image Placeholder */}
      <div className="w-10 h-14 shrink-0 rounded bg-gradient-to-br from-amber-900/40 to-amber-700/20 flex items-center justify-center">
        <span className="text-[10px] text-amber-500/60 font-medium">MTG</span>
      </div>

      {/* Card Info */}
      <div className="flex-1 min-w-0">
        <Link
          href={`/cards/${item.card_id}`}
          className="text-sm font-medium text-[rgb(var(--foreground))] hover:text-amber-500 transition-colors line-clamp-1"
        >
          {item.card_name}
        </Link>

        {/* Badges Row */}
        <div className="flex items-center gap-1.5 mt-1">
          {/* Quantity Badge */}
          <Badge variant="secondary" size="sm" className="gap-0.5">
            <Package className="w-3 h-3" />
            <span>x{item.quantity}</span>
          </Badge>

          {/* Condition Badge */}
          {conditionLabel && conditionColor && (
            <span className={`px-1.5 py-0.5 rounded text-xs font-medium ${conditionColor}`}>
              {conditionLabel}
            </span>
          )}
        </div>
      </div>

      {/* Price */}
      {item.price_at_proposal !== null && (
        <div className="text-right shrink-0">
          <div className="text-sm font-medium text-[rgb(var(--foreground))]">
            {formatCurrency(item.price_at_proposal)}
          </div>
          {item.quantity > 1 && (
            <div className="text-xs text-[rgb(var(--muted-foreground))]">
              {formatCurrency(item.price_at_proposal * item.quantity)} total
            </div>
          )}
        </div>
      )}
    </div>
  );
}
