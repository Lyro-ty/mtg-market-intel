'use client';

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Trophy, Calendar, MapPin, Users, ExternalLink } from 'lucide-react';
import Link from 'next/link';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { LoadingPage } from '@/components/ui/Loading';
import { ErrorDisplay } from '@/components/ui/ErrorDisplay';
import { useQueryClient } from '@tanstack/react-query';
import { getTournaments } from '@/lib/api';

const FORMAT_OPTIONS = [
  { value: '', label: 'All Formats' },
  { value: 'Standard', label: 'Standard' },
  { value: 'Modern', label: 'Modern' },
  { value: 'Pioneer', label: 'Pioneer' },
  { value: 'Legacy', label: 'Legacy' },
  { value: 'Vintage', label: 'Vintage' },
  { value: 'Pauper', label: 'Pauper' },
];

const DATE_OPTIONS = [
  { value: 0, label: 'All Time' },
  { value: 7, label: 'Last 7 Days' },
  { value: 30, label: 'Last 30 Days' },
  { value: 90, label: 'Last 90 Days' },
];

export default function TournamentsPage() {
  const queryClient = useQueryClient();
  const [formatFilter, setFormatFilter] = useState('');
  const [daysFilter, setDaysFilter] = useState(30);
  const [page, setPage] = useState(1);

  const { data, isLoading, error } = useQuery({
    queryKey: ['tournaments', formatFilter, daysFilter, page],
    queryFn: () =>
      getTournaments({
        format: formatFilter || undefined,
        days: daysFilter || undefined,
        page,
        pageSize: 20,
      }),
  });

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    });
  };

  return (
    <div className="space-y-6 animate-in">
      {/* Header with Attribution */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-3xl font-bold text-[rgb(var(--foreground))]">Tournament Results</h1>
          <p className="text-[rgb(var(--muted-foreground))] mt-1">
            Recent competitive tournament data and standings
          </p>
        </div>
        <div className="text-sm text-[rgb(var(--muted-foreground))]">
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

      {/* Filters */}
      <Card>
        <CardContent className="p-4">
          <div className="flex flex-col sm:flex-row gap-4">
            {/* Format Filter */}
            <div className="flex-1">
              <label className="text-sm text-[rgb(var(--muted-foreground))] mb-2 block">
                Format
              </label>
              <select
                value={formatFilter}
                onChange={(e) => {
                  setFormatFilter(e.target.value);
                  setPage(1);
                }}
                className="w-full px-3 py-2 bg-[rgb(var(--surface))] border border-[rgb(var(--border))] rounded-md text-[rgb(var(--foreground))] focus:outline-none focus:ring-2 focus:ring-[rgb(var(--accent))]"
              >
                {FORMAT_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </div>

            {/* Date Filter */}
            <div className="flex-1">
              <label className="text-sm text-[rgb(var(--muted-foreground))] mb-2 block">
                Date Range
              </label>
              <select
                value={daysFilter}
                onChange={(e) => {
                  setDaysFilter(Number(e.target.value));
                  setPage(1);
                }}
                className="w-full px-3 py-2 bg-[rgb(var(--surface))] border border-[rgb(var(--border))] rounded-md text-[rgb(var(--foreground))] focus:outline-none focus:ring-2 focus:ring-[rgb(var(--accent))]"
              >
                {DATE_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Tournament List */}
      {isLoading ? (
        <LoadingPage />
      ) : error ? (
        <ErrorDisplay
          message={error instanceof Error ? error.message : 'Failed to load tournaments'}
          status={error instanceof Error && 'status' in error ? (error as any).status : undefined}
          onRetry={() => queryClient.invalidateQueries({ queryKey: ['tournaments', formatFilter, daysFilter, page] })}
        />
      ) : data?.tournaments.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center">
            <Trophy className="w-12 h-12 mx-auto text-[rgb(var(--muted-foreground))] mb-4" />
            <p className="text-[rgb(var(--muted-foreground))]">
              No tournaments found matching your filters
            </p>
          </CardContent>
        </Card>
      ) : (
        <>
          <div className="text-sm text-[rgb(var(--muted-foreground))]">
            Showing {data?.tournaments.length} of {data?.total} tournaments
          </div>

          <div className="space-y-4">
            {data?.tournaments.map((tournament) => (
              <Card key={tournament.id} interactive>
                <Link href={`/tournaments/${tournament.id}`}>
                  <CardContent className="p-6">
                    <div className="flex items-start justify-between gap-4">
                      <div className="flex-1">
                        {/* Tournament Header */}
                        <div className="flex items-start gap-3 mb-3">
                          <Trophy className="w-5 h-5 text-[rgb(var(--accent))] mt-0.5 flex-shrink-0" />
                          <div className="flex-1">
                            <h3 className="text-lg font-semibold text-[rgb(var(--foreground))] mb-1">
                              {tournament.name}
                            </h3>
                            <div className="flex flex-wrap items-center gap-2 text-sm text-[rgb(var(--muted-foreground))]">
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
                            </div>
                          </div>
                        </div>

                        {/* Tournament Info */}
                        <div className="flex flex-wrap items-center gap-2">
                          <Badge variant="accent">{tournament.format}</Badge>
                          <Badge variant="default">
                            <Users className="w-3 h-3 mr-1" />
                            {tournament.player_count} players
                          </Badge>
                          {tournament.swiss_rounds && (
                            <Badge variant="default">
                              {tournament.swiss_rounds} rounds
                            </Badge>
                          )}
                          {tournament.top_cut_size && (
                            <Badge variant="default">
                              Top {tournament.top_cut_size}
                            </Badge>
                          )}
                        </div>
                      </div>
                    </div>
                  </CardContent>
                </Link>
              </Card>
            ))}
          </div>

          {/* Pagination */}
          {data && data.total > 20 && (
            <div className="flex items-center justify-center gap-2">
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
              >
                Previous
              </Button>
              <span className="text-sm text-[rgb(var(--muted-foreground))]">
                Page {page} of {Math.ceil(data.total / 20)}
              </span>
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setPage((p) => p + 1)}
                disabled={!data.has_more}
              >
                Next
              </Button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
