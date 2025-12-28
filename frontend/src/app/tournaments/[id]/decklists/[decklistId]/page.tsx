'use client';

import { useParams } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import { useQueryClient } from '@tanstack/react-query';
import Link from 'next/link';
import Image from 'next/image';
import { ArrowLeft, ExternalLink, Trophy, FileText, Layers } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { LoadingPage } from '@/components/ui/Loading';
import { ErrorDisplay } from '@/components/ui/ErrorDisplay';
import { getDecklist } from '@/lib/api';
import type { DecklistCard } from '@/types';

export default function DecklistDetailPage() {
  const params = useParams();
  const queryClient = useQueryClient();
  const tournamentId = Number(params.id);
  const decklistId = Number(params.decklistId);

  const { data: decklist, isLoading, error } = useQuery({
    queryKey: ['decklist', tournamentId, decklistId],
    queryFn: () => getDecklist(tournamentId, decklistId),
    enabled: !isNaN(tournamentId) && !isNaN(decklistId),
  });

  const getRankBadge = (rank: number) => {
    if (rank === 1) return <Badge variant="success">1st Place</Badge>;
    if (rank === 2) return <Badge variant="info">2nd Place</Badge>;
    if (rank === 3) return <Badge variant="info">3rd Place</Badge>;
    if (rank <= 8) return <Badge variant="accent">Top 8</Badge>;
    return <Badge variant="default">{rank}th Place</Badge>;
  };

  // Group cards by quantity for compact display
  const groupCardsByQuantity = (cards: DecklistCard[]) => {
    const grouped: { [key: string]: DecklistCard[] } = {
      '4': [],
      '3': [],
      '2': [],
      '1': [],
    };
    cards.forEach((card) => {
      const qty = String(card.quantity);
      if (grouped[qty]) {
        grouped[qty].push(card);
      }
    });
    return grouped;
  };

  if (isNaN(tournamentId) || isNaN(decklistId)) {
    return (
      <ErrorDisplay
        message="Invalid tournament or decklist ID"
        status={400}
      />
    );
  }

  if (isLoading) {
    return <LoadingPage />;
  }

  if (error) {
    return (
      <ErrorDisplay
        message={error instanceof Error ? error.message : 'Failed to load decklist'}
        status={error instanceof Error && 'status' in error ? (error as any).status : undefined}
        onRetry={() => queryClient.invalidateQueries({ queryKey: ['decklist', tournamentId, decklistId] })}
      />
    );
  }

  if (!decklist) {
    return (
      <ErrorDisplay
        message="Decklist not found"
        status={404}
      />
    );
  }

  const mainboardCards = decklist.cards.filter((c) => c.section === 'mainboard');
  const sideboardCards = decklist.cards.filter((c) => c.section === 'sideboard');
  const commanderCards = decklist.cards.filter((c) => c.section === 'commander');

  const mainboardGrouped = groupCardsByQuantity(mainboardCards);
  const sideboardGrouped = groupCardsByQuantity(sideboardCards);

  return (
    <div className="space-y-6 animate-in">
      {/* Back Navigation */}
      <Link
        href={`/tournaments/${tournamentId}`}
        className="inline-flex items-center gap-2 text-[rgb(var(--accent))] hover:underline"
      >
        <ArrowLeft className="w-4 h-4" />
        Back to Tournament
      </Link>

      {/* Header */}
      <div>
        <div className="flex items-start justify-between mb-4">
          <div className="flex items-start gap-3 flex-1">
            <Trophy className="w-8 h-8 text-[rgb(var(--accent))] mt-1 flex-shrink-0" />
            <div className="min-w-0">
              <h1 className="text-3xl font-bold text-[rgb(var(--foreground))] break-words">
                {decklist.archetype_name || 'Unknown Archetype'}
              </h1>
              <div className="mt-2 space-y-1">
                <div className="text-lg text-[rgb(var(--muted-foreground))]">
                  {decklist.player_name}
                </div>
                <Link
                  href={`/tournaments/${tournamentId}`}
                  className="text-sm text-[rgb(var(--accent))] hover:underline inline-flex items-center gap-1"
                >
                  {decklist.tournament_name}
                </Link>
              </div>
            </div>
          </div>
          <div className="flex-shrink-0 text-right">
            <div className="mb-2">
              {getRankBadge(decklist.rank)}
            </div>
            <div className="text-sm text-[rgb(var(--muted-foreground))]">
              {decklist.wins}-{decklist.losses}
              {decklist.draws > 0 && `-${decklist.draws}`}
            </div>
          </div>
        </div>

        {/* Deck Stats */}
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="accent" size="md">
            {decklist.tournament_format}
          </Badge>
          <Badge variant="default" size="md">
            <FileText className="w-3 h-3 mr-1" />
            {decklist.mainboard_count} mainboard
          </Badge>
          <Badge variant="default" size="md">
            <Layers className="w-3 h-3 mr-1" />
            {decklist.sideboard_count} sideboard
          </Badge>
        </div>

        {/* Attribution */}
        <div className="mt-4 text-sm text-[rgb(var(--muted-foreground))]">
          Data provided by{' '}
          <a
            href="https://topdeck.gg"
            target="_blank"
            rel="noopener noreferrer"
            className="text-[rgb(var(--accent))] hover:underline inline-flex items-center gap-1"
          >
            TopDeck.gg
            <ExternalLink className="w-3 h-3" />
          </a>
        </div>
      </div>

      {/* Commander (if applicable) */}
      {commanderCards.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Trophy className="w-5 h-5" />
              Commander
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {commanderCards.map((card) => (
                <div
                  key={card.card_id}
                  className="flex items-center gap-3 p-3 bg-[rgb(var(--surface))] rounded-lg border border-[rgb(var(--border))]"
                >
                  {card.card_image_url && (
                    <div className="relative w-16 h-22 flex-shrink-0 rounded overflow-hidden">
                      <Image
                        src={card.card_image_url}
                        alt={card.card_name}
                        fill
                        className="object-cover"
                        unoptimized
                      />
                    </div>
                  )}
                  <div className="flex-1">
                    <div className="font-semibold text-[rgb(var(--foreground))]">
                      {card.card_name}
                    </div>
                    {card.card_set && (
                      <div className="text-sm text-[rgb(var(--muted-foreground))]">
                        {card.card_set}
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Mainboard */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <FileText className="w-5 h-5" />
            Mainboard ({decklist.mainboard_count})
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-6">
            {Object.entries(mainboardGrouped).map(([quantity, cards]) => {
              if (cards.length === 0) return null;
              return (
                <div key={quantity}>
                  <h4 className="text-sm font-semibold text-[rgb(var(--muted-foreground))] mb-2">
                    {quantity}x ({cards.length} cards)
                  </h4>
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2">
                    {cards.map((card) => (
                      <div
                        key={card.card_id}
                        className="flex items-start gap-2 p-2 bg-[rgb(var(--surface))] rounded border border-[rgb(var(--border))] hover:border-[rgb(var(--accent))] transition-colors"
                      >
                        <span className="text-[rgb(var(--muted-foreground))] font-mono text-sm flex-shrink-0 mt-0.5">
                          {card.quantity}x
                        </span>
                        <div className="flex-1 min-w-0">
                          <Link
                            href={`/cards/${card.card_id}`}
                            className="text-sm text-[rgb(var(--foreground))] hover:text-[rgb(var(--accent))] hover:underline truncate block"
                          >
                            {card.card_name}
                          </Link>
                          {card.card_set && (
                            <div className="text-xs text-[rgb(var(--muted-foreground))] truncate">
                              {card.card_set}
                            </div>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        </CardContent>
      </Card>

      {/* Sideboard */}
      {sideboardCards.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Layers className="w-5 h-5" />
              Sideboard ({decklist.sideboard_count})
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-6">
              {Object.entries(sideboardGrouped).map(([quantity, cards]) => {
                if (cards.length === 0) return null;
                return (
                  <div key={quantity}>
                    <h4 className="text-sm font-semibold text-[rgb(var(--muted-foreground))] mb-2">
                      {quantity}x ({cards.length} cards)
                    </h4>
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2">
                      {cards.map((card) => (
                        <div
                          key={card.card_id}
                          className="flex items-start gap-2 p-2 bg-[rgb(var(--surface))] rounded border border-[rgb(var(--border))] hover:border-[rgb(var(--accent))] transition-colors"
                        >
                          <span className="text-[rgb(var(--muted-foreground))] font-mono text-sm flex-shrink-0 mt-0.5">
                            {card.quantity}x
                          </span>
                          <div className="flex-1 min-w-0">
                            <Link
                              href={`/cards/${card.card_id}`}
                              className="text-sm text-[rgb(var(--foreground))] hover:text-[rgb(var(--accent))] hover:underline truncate block"
                            >
                              {card.card_name}
                            </Link>
                            {card.card_set && (
                              <div className="text-xs text-[rgb(var(--muted-foreground))] truncate">
                                {card.card_set}
                              </div>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
