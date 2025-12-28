// frontend/src/components/ornate/ornate-card.tsx
import { cn } from '@/lib/utils';
import { Flourish } from './flourish';

export type CardRarity = 'common' | 'uncommon' | 'rare' | 'mythic';

interface OrnateCardProps {
  children: React.ReactNode;
  rarity?: CardRarity;
  className?: string;
  hover?: boolean;
}

const rarityBorders: Record<CardRarity, string> = {
  common: 'border-[rgb(var(--border))]',
  uncommon: 'border-[rgb(var(--silver))]/40',
  rare: 'border-[rgb(var(--gold))]/50',
  mythic: 'border-[rgb(var(--mythic-orange))]/50',
};

const rarityGlows: Record<CardRarity, string> = {
  common: '',
  uncommon: 'hover:shadow-[0_0_15px_rgb(var(--silver)/0.2)]',
  rare: 'hover:shadow-[0_0_20px_rgb(var(--gold)/0.3)]',
  mythic: 'hover:shadow-[0_0_25px_rgb(var(--mythic-orange)/0.4)]',
};

export function OrnateCard({
  children,
  rarity = 'common',
  className,
  hover = true,
}: OrnateCardProps) {
  const showFlourishes = rarity === 'rare' || rarity === 'mythic';

  return (
    <div
      className={cn(
        'relative rounded-lg bg-[rgb(var(--card))] overflow-hidden',
        'transition-all duration-200',
        hover && 'hover:scale-[1.01]',
        hover && rarityGlows[rarity],
        className
      )}
    >
      {/* Outer border */}
      <div className="absolute inset-0 rounded-lg border border-[rgb(var(--border))]" />

      {/* Inner accent border */}
      <div
        className={cn(
          'absolute inset-[3px] rounded-md border',
          rarityBorders[rarity]
        )}
      />

      {/* Corner flourishes */}
      {showFlourishes && (
        <>
          <Flourish position="top-left" />
          <Flourish position="top-right" />
          <Flourish position="bottom-left" />
          <Flourish position="bottom-right" />
        </>
      )}

      {/* Content */}
      <div className="relative p-4">{children}</div>
    </div>
  );
}
