// frontend/src/components/ornate/rarity-badge.tsx
import { cn } from '@/lib/utils';
import { type CardRarity } from './ornate-card';

interface RarityBadgeProps {
  rarity: CardRarity;
  className?: string;
}

const rarityStyles: Record<CardRarity, string> = {
  common: 'bg-[rgb(var(--border))] text-muted-foreground',
  uncommon: 'bg-[rgb(var(--silver))]/20 text-[rgb(var(--silver))] border-[rgb(var(--silver))]/30',
  rare: 'bg-[rgb(var(--gold))]/20 text-[rgb(var(--gold))] border-[rgb(var(--gold))]/30',
  mythic: 'bg-[rgb(var(--mythic-orange))]/20 text-[rgb(var(--mythic-orange))] border-[rgb(var(--mythic-orange))]/30',
};

const rarityLabels: Record<CardRarity, string> = {
  common: 'Common',
  uncommon: 'Uncommon',
  rare: 'Rare',
  mythic: 'Mythic',
};

export function RarityBadge({ rarity, className }: RarityBadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center px-2 py-0.5 rounded text-xs font-medium border',
        rarityStyles[rarity],
        className
      )}
    >
      {rarityLabels[rarity]}
    </span>
  );
}
