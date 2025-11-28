'use client';

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Search as SearchIcon } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/Card';
import { LoadingPage } from '@/components/ui/Loading';
import { CardGrid } from '@/components/cards/CardGrid';
import { SearchBar } from '@/components/cards/SearchBar';
import { Button } from '@/components/ui/Button';
import { searchCards } from '@/lib/api';

export default function CardsPage() {
  const [query, setQuery] = useState('');
  const [page, setPage] = useState(1);

  const { data, isLoading, error } = useQuery({
    queryKey: ['cards', 'search', query, page],
    queryFn: () => searchCards(query || 'a', { page, pageSize: 20 }),
    enabled: true,
  });

  return (
    <div className="space-y-6 animate-in">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-[rgb(var(--foreground))]">Search Cards</h1>
        <p className="text-[rgb(var(--muted-foreground))] mt-1">
          Find MTG cards and view their market data
        </p>
      </div>

      {/* Search */}
      <Card>
        <CardContent className="p-4">
          <SearchBar
            onSearch={(q) => {
              setQuery(q);
              setPage(1);
            }}
            placeholder="Search by card name..."
          />
        </CardContent>
      </Card>

      {/* Results */}
      {isLoading ? (
        <LoadingPage />
      ) : error ? (
        <Card>
          <CardContent className="py-12 text-center">
            <p className="text-red-500">Failed to search cards</p>
          </CardContent>
        </Card>
      ) : data?.cards.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center">
            <SearchIcon className="w-12 h-12 mx-auto text-[rgb(var(--muted-foreground))] mb-4" />
            <p className="text-[rgb(var(--muted-foreground))]">
              {query ? 'No cards found matching your search' : 'Start typing to search for cards'}
            </p>
          </CardContent>
        </Card>
      ) : (
        <>
          {/* Results count */}
          <div className="flex items-center justify-between">
            <p className="text-sm text-[rgb(var(--muted-foreground))]">
              Found {data?.total || 0} cards
            </p>
          </div>

          {/* Card Grid */}
          <CardGrid cards={data?.cards || []} />

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

