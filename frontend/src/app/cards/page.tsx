'use client';

import { Suspense, useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import { Search as SearchIcon } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/Card';
import { LoadingPage } from '@/components/ui/Loading';
import { ErrorDisplay } from '@/components/ui/ErrorDisplay';
import { CardGrid } from '@/components/cards/CardGrid';
import { SearchBar } from '@/components/cards/SearchBar';
import { Button } from '@/components/ui/Button';
import { useQueryClient } from '@tanstack/react-query';
import { searchCards } from '@/lib/api';

export default function CardsPage() {
  return (
    <Suspense fallback={<LoadingPage />}>
      <CardsPageContent />
    </Suspense>
  );
}

function CardsPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const queryClient = useQueryClient();
  const initialQuery = searchParams.get('q') ?? '';
  const initialPage = Number(searchParams.get('page') ?? '1') || 1;
  
  const [query, setQuery] = useState(initialQuery);
  const [page, setPage] = useState(initialPage);
  
  useEffect(() => {
    const params = new URLSearchParams();
    if (query) {
      params.set('q', query);
    }
    if (page > 1) {
      params.set('page', String(page));
    }
    const search = params.toString();
    router.replace(`/cards${search ? `?${search}` : ''}`);
  }, [query, page, router]);

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
            value={query}
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
        <ErrorDisplay
          message={error instanceof Error ? error.message : 'Failed to search cards'}
          status={error instanceof Error && 'status' in error ? (error as any).status : undefined}
          onRetry={() => queryClient.invalidateQueries({ queryKey: ['cards', 'search', query, page] })}
        />
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

