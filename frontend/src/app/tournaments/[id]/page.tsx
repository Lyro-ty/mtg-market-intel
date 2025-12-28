'use client';

import { useParams } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import { Trophy, Calendar, MapPin, Users, ExternalLink, Award, TrendingUp, ChevronRight } from 'lucide-react';
import Link from 'next/link';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { LoadingPage } from '@/components/ui/Loading';
import { ErrorDisplay } from '@/components/ui/ErrorDisplay';
import { useQueryClient } from '@tanstack/react-query';
import { getTournament } from '@/lib/api';

export default function TournamentDetailPage() {
  const params = useParams();
  const queryClient = useQueryClient();
  const tournamentId = Number(params.id);

  const { data: tournament, isLoading, error } = useQuery({
    queryKey: ['tournament', tournamentId],
    queryFn: () => getTournament(tournamentId),
    enabled: !isNaN(tournamentId),
  });

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-US', {
      month: 'long',
      day: 'numeric',
      year: 'numeric',
    });
  };

  const formatWinRate = (winRate: number) => {
    return `${(winRate * 100).toFixed(1)}%`;
  };

  const getRankBadge = (rank: number) => {
    if (rank === 1) return <Badge variant="success">1st</Badge>;
    if (rank === 2) return <Badge variant="info">2nd</Badge>;
    if (rank === 3) return <Badge variant="info">3rd</Badge>;
    if (rank <= 8) return <Badge variant="accent">Top 8</Badge>;
    return <Badge variant="default">{rank}th</Badge>;
  };

  if (isNaN(tournamentId)) {
    return (
      <ErrorDisplay
        message="Invalid tournament ID"
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
        message={error instanceof Error ? error.message : 'Failed to load tournament'}
        status={error instanceof Error && 'status' in error ? (error as any).status : undefined}
        onRetry={() => queryClient.invalidateQueries({ queryKey: ['tournament', tournamentId] })}
      />
    );
  }

  if (!tournament) {
    return (
      <ErrorDisplay
        message="Tournament not found"
        status={404}
      />
    );
  }

  return (
    <div className="space-y-6 animate-in">
      {/* Header */}
      <div>
        <div className="flex items-start justify-between mb-2">
          <div className="flex items-start gap-3">
            <Trophy className="w-8 h-8 text-[rgb(var(--accent))] mt-1" />
            <div>
              <h1 className="text-3xl font-bold text-[rgb(var(--foreground))]">
                {tournament.name}
              </h1>
              <div className="flex flex-wrap items-center gap-2 mt-2 text-[rgb(var(--muted-foreground))]">
                <div className="flex items-center gap-1">
                  <Calendar className="w-4 h-4" />
                  {formatDate(tournament.date)}
                </div>
                {tournament.city && (
                  <>
                    <span>·</span>
                    <div className="flex items-center gap-1">
                      <MapPin className="w-4 h-4" />
                      {tournament.city}
                    </div>
                  </>
                )}
                {tournament.venue && (
                  <>
                    <span>·</span>
                    <span>{tournament.venue}</span>
                  </>
                )}
              </div>
            </div>
          </div>
          <div className="text-sm text-[rgb(var(--muted-foreground))] text-right">
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

        {/* Tournament Info Badges */}
        <div className="flex flex-wrap items-center gap-2 mt-4">
          <Badge variant="accent" size="md">{tournament.format}</Badge>
          <Badge variant="default" size="md">
            <Users className="w-3 h-3 mr-1" />
            {tournament.player_count} players
          </Badge>
          {tournament.swiss_rounds && (
            <Badge variant="default" size="md">
              {tournament.swiss_rounds} rounds
            </Badge>
          )}
          {tournament.top_cut_size && (
            <Badge variant="default" size="md">
              Top {tournament.top_cut_size}
            </Badge>
          )}
          <a
            href={tournament.topdeck_url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-sm text-[rgb(var(--accent))] hover:underline inline-flex items-center gap-1"
          >
            View on TopDeck
            <ExternalLink className="w-3 h-3" />
          </a>
        </div>
      </div>

      {/* Standings */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Award className="w-5 h-5" />
            Standings
          </CardTitle>
        </CardHeader>
        <CardContent>
          {tournament.standings.length === 0 ? (
            <p className="text-[rgb(var(--muted-foreground))] text-center py-8">
              No standings available for this tournament
            </p>
          ) : (
            <div className="space-y-2">
              {tournament.standings.map((standing) => (
                <div
                  key={standing.id}
                  className="flex items-center justify-between p-4 bg-[rgb(var(--surface))] rounded-lg border border-[rgb(var(--border))] hover:border-[rgb(var(--accent))] transition-colors"
                >
                  <div className="flex items-center gap-4 flex-1">
                    {/* Rank */}
                    <div className="w-16 flex-shrink-0">
                      {getRankBadge(standing.rank)}
                    </div>

                    {/* Player Info */}
                    <div className="flex-1 min-w-0">
                      <div className="font-semibold text-[rgb(var(--foreground))] truncate">
                        {standing.player_name}
                      </div>
                      {standing.decklist && (
                        <div className="text-sm text-[rgb(var(--muted-foreground))] mt-0.5">
                          {standing.decklist.archetype_name || 'Unknown Archetype'}
                          {standing.decklist.card_count && (
                            <span className="ml-2">
                              ({standing.decklist.card_count} cards)
                            </span>
                          )}
                        </div>
                      )}
                    </div>

                    {/* Record */}
                    <div className="flex items-center gap-4 text-sm">
                      <div className="text-center">
                        <div className="text-[rgb(var(--muted-foreground))]">Record</div>
                        <div className="font-semibold text-[rgb(var(--foreground))]">
                          {standing.wins}-{standing.losses}
                          {standing.draws > 0 && `-${standing.draws}`}
                        </div>
                      </div>
                      <div className="text-center">
                        <div className="text-[rgb(var(--muted-foreground))]">Win Rate</div>
                        <div className="font-semibold text-[rgb(var(--foreground))]">
                          {formatWinRate(standing.win_rate)}
                        </div>
                      </div>
                    </div>

                    {/* View Decklist Link */}
                    {standing.decklist && (
                      <Link
                        href={`/tournaments/${tournament.id}/decklists/${standing.decklist.id}`}
                        className="text-sm text-[rgb(var(--accent))] hover:underline flex items-center gap-1 flex-shrink-0"
                      >
                        View Decklist
                        <ChevronRight className="w-3 h-3" />
                      </Link>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Top Performers Summary */}
      {tournament.standings.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <TrendingUp className="w-5 h-5" />
              Top 3 Finishers
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {tournament.standings.slice(0, 3).map((standing, idx) => (
                <div
                  key={standing.id}
                  className="p-4 bg-[rgb(var(--surface))] rounded-lg border border-[rgb(var(--border))]"
                >
                  <div className="flex items-center gap-2 mb-2">
                    {idx === 0 && <Trophy className="w-5 h-5 text-yellow-500" />}
                    {idx === 1 && <Trophy className="w-5 h-5 text-gray-400" />}
                    {idx === 2 && <Trophy className="w-5 h-5 text-orange-600" />}
                    <span className="font-semibold text-[rgb(var(--foreground))]">
                      {standing.rank === 1 ? '1st Place' : standing.rank === 2 ? '2nd Place' : '3rd Place'}
                    </span>
                  </div>
                  <div className="text-[rgb(var(--foreground))] font-medium mb-1">
                    {standing.player_name}
                  </div>
                  {standing.decklist?.archetype_name && (
                    <div className="text-sm text-[rgb(var(--muted-foreground))] mb-2">
                      {standing.decklist.archetype_name}
                    </div>
                  )}
                  <div className="text-sm text-[rgb(var(--muted-foreground))]">
                    Record: {standing.wins}-{standing.losses}
                    {standing.draws > 0 && `-${standing.draws}`}
                    {' · '}
                    {formatWinRate(standing.win_rate)}
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
