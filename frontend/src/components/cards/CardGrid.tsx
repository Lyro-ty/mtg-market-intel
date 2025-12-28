'use client';

import Image from 'next/image';
import Link from 'next/link';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { formatCurrency, getRarityColor } from '@/lib/utils';
import type { Card as CardType, TopCard } from '@/types';

interface CardGridProps {
  cards: (CardType | TopCard)[];
  showPrice?: boolean;
  showChange?: boolean;
}

function isTopCard(card: CardType | TopCard): card is TopCard {
  return 'card_id' in card;
}

export function CardGrid({ cards, showPrice = false, showChange = false }: CardGridProps) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
      {cards.map((card) => {
        const cardId = isTopCard(card) ? card.card_id : card.id;
        const cardName = isTopCard(card) ? card.card_name : card.name;
        const setCode = card.set_code;
        const imageUrl = isTopCard(card) ? card.image_url : card.image_url_small;
        
        return (
          <Link key={cardId} href={`/cards/${cardId}`}>
            <Card className="group hover:border-primary-500/50 transition-all cursor-pointer overflow-hidden p-0">
              {/* Card Image */}
              <div className="aspect-[5/7] relative bg-[rgb(var(--secondary))] overflow-hidden">
                {imageUrl ? (
                  <Image
                    src={imageUrl}
                    alt={cardName}
                    fill
                    className="object-cover group-hover:scale-105 transition-transform duration-300"
                    sizes="(max-width: 640px) 100vw, (max-width: 1024px) 50vw, 25vw"
                  />
                ) : (
                  <div className="absolute inset-0 flex items-center justify-center text-[rgb(var(--muted-foreground))]">
                    No Image
                  </div>
                )}
              </div>
              
              {/* Card Info */}
              <div className="p-4">
                <h3 className="font-semibold text-[rgb(var(--foreground))] truncate group-hover:text-primary-500 transition-colors">
                  {cardName}
                </h3>
                <div className="flex items-center justify-between mt-2">
                  <span className="text-sm text-[rgb(var(--muted-foreground))]">
                    {setCode}
                  </span>
                  {'rarity' in card && card.rarity && (
                    <Badge className={getRarityColor(card.rarity)}>
                      {card.rarity}
                    </Badge>
                  )}
                </div>
                
                {/* Price info for TopCard */}
                {'current_price' in card && showPrice && (
                  <div className="mt-3 flex items-center justify-between">
                    <span className="font-semibold text-[rgb(var(--foreground))]">
                      {formatCurrency(card.current_price)}
                    </span>
                    {showChange && 'price_change_pct' in card && (
                      <span
                        className={
                          card.price_change_pct > 0
                            ? 'text-green-500'
                            : card.price_change_pct < 0
                            ? 'text-red-500'
                            : 'text-[rgb(var(--muted-foreground))]'
                        }
                      >
                        {card.price_change_pct > 0 ? '+' : ''}
                        {card.price_change_pct.toFixed(1)}%
                      </span>
                    )}
                  </div>
                )}
              </div>
            </Card>
          </Link>
        );
      })}
    </div>
  );
}

