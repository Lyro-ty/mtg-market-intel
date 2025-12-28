'use client';

import { Suspense, useEffect, useState, useCallback } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Search as SearchIcon, Sparkles, Type, ChevronDown, ChevronUp, X } from 'lucide-react';
import Image from 'next/image';
import Link from 'next/link';
import { Card, CardContent } from '@/components/ui/card';
import { LoadingPage } from '@/components/ui/Loading';
import { ErrorDisplay } from '@/components/ui/ErrorDisplay';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { SearchAutocomplete } from '@/components/search/SearchAutocomplete';
import { formatCurrency, getRarityColor } from '@/lib/utils';
import type { Card as CardType } from '@/types';

// MTG color definitions with mana symbols
const MTG_COLORS = [
  { code: 'W', name: 'White', bgClass: 'bg-amber-50 dark:bg-amber-900/30', textClass: 'text-amber-800 dark:text-amber-200', borderClass: 'border-amber-300 dark:border-amber-700' },
  { code: 'U', name: 'Blue', bgClass: 'bg-blue-100 dark:bg-blue-900/30', textClass: 'text-blue-800 dark:text-blue-200', borderClass: 'border-blue-300 dark:border-blue-700' },
  { code: 'B', name: 'Black', bgClass: 'bg-gray-200 dark:bg-gray-700', textClass: 'text-gray-800 dark:text-gray-200', borderClass: 'border-gray-400 dark:border-gray-600' },
  { code: 'R', name: 'Red', bgClass: 'bg-red-100 dark:bg-red-900/30', textClass: 'text-red-800 dark:text-red-200', borderClass: 'border-red-300 dark:border-red-700' },
  { code: 'G', name: 'Green', bgClass: 'bg-green-100 dark:bg-green-900/30', textClass: 'text-green-800 dark:text-green-200', borderClass: 'border-green-300 dark:border-green-700' },
];

// Common card types
const CARD_TYPES = [
  'Creature',
  'Instant',
  'Sorcery',
  'Enchantment',
  'Artifact',
  'Planeswalker',
  'Land',
  'Battle',
];

// Search result with similarity score
interface SearchResultCard extends CardType {
  similarity_score?: number;
}

interface SearchResponse {
  cards: SearchResultCard[];
  total: number;
  page: number;
  page_size: number;
  has_more: boolean;
  search_mode?: string;
}

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

  // Parse initial state from URL
  const initialQuery = searchParams.get('q') ?? '';
  const initialPage = Number(searchParams.get('page') ?? '1') || 1;
  const initialMode = (searchParams.get('mode') as 'semantic' | 'text') ?? 'semantic';
  const initialColors = searchParams.get('colors')?.split(',').filter(Boolean) ?? [];
  const initialType = searchParams.get('card_type') ?? '';
  const initialCmcMin = searchParams.get('cmc_min') ? Number(searchParams.get('cmc_min')) : undefined;
  const initialCmcMax = searchParams.get('cmc_max') ? Number(searchParams.get('cmc_max')) : undefined;

  // State
  const [query, setQuery] = useState(initialQuery);
  const [page, setPage] = useState(initialPage);
  const [searchMode, setSearchMode] = useState<'semantic' | 'text'>(initialMode);
  const [selectedColors, setSelectedColors] = useState<string[]>(initialColors);
  const [cardType, setCardType] = useState(initialType);
  const [cmcMin, setCmcMin] = useState<number | undefined>(initialCmcMin);
  const [cmcMax, setCmcMax] = useState<number | undefined>(initialCmcMax);
  const [showFilters, setShowFilters] = useState(
    initialColors.length > 0 || initialType !== '' || initialCmcMin !== undefined || initialCmcMax !== undefined
  );

  // Update URL when state changes
  useEffect(() => {
    const params = new URLSearchParams();
    if (query) params.set('q', query);
    if (page > 1) params.set('page', String(page));
    if (searchMode !== 'semantic') params.set('mode', searchMode);
    if (selectedColors.length > 0) params.set('colors', selectedColors.join(','));
    if (cardType) params.set('card_type', cardType);
    if (cmcMin !== undefined) params.set('cmc_min', String(cmcMin));
    if (cmcMax !== undefined) params.set('cmc_max', String(cmcMax));

    const search = params.toString();
    router.replace(`/cards${search ? `?${search}` : ''}`, { scroll: false });
  }, [query, page, searchMode, selectedColors, cardType, cmcMin, cmcMax, router]);

  // Fetch cards using the new search API
  const fetchCards = useCallback(async (): Promise<SearchResponse> => {
    const params = new URLSearchParams();
    params.set('q', query || '*');
    params.set('mode', searchMode);
    params.set('page', String(page));
    params.set('page_size', '20');

    if (selectedColors.length > 0) {
      params.set('colors', selectedColors.join(','));
    }
    if (cardType) {
      params.set('card_type', cardType);
    }
    if (cmcMin !== undefined) {
      params.set('cmc_min', String(cmcMin));
    }
    if (cmcMax !== undefined) {
      params.set('cmc_max', String(cmcMax));
    }

    const response = await fetch(`/api/search?${params.toString()}`);
    if (!response.ok) {
      throw new Error(`Search failed: ${response.statusText}`);
    }
    return response.json();
  }, [query, searchMode, page, selectedColors, cardType, cmcMin, cmcMax]);

  const { data, isLoading, error } = useQuery({
    queryKey: ['cards', 'search', query, searchMode, page, selectedColors, cardType, cmcMin, cmcMax],
    queryFn: fetchCards,
    enabled: true,
  });

  // Toggle color selection
  const toggleColor = (colorCode: string) => {
    setSelectedColors(prev =>
      prev.includes(colorCode)
        ? prev.filter(c => c !== colorCode)
        : [...prev, colorCode]
    );
    setPage(1);
  };

  // Clear all filters
  const clearFilters = () => {
    setSelectedColors([]);
    setCardType('');
    setCmcMin(undefined);
    setCmcMax(undefined);
    setPage(1);
  };

  const hasActiveFilters = selectedColors.length > 0 || cardType !== '' || cmcMin !== undefined || cmcMax !== undefined;

  return (
    <div className="space-y-6 animate-in">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-[rgb(var(--foreground))]">Search Cards</h1>
        <p className="text-[rgb(var(--muted-foreground))] mt-1">
          Find MTG cards using semantic or text search
        </p>
      </div>

      {/* Search Controls */}
      <Card>
        <CardContent className="p-4 space-y-4">
          {/* Search Mode Toggle + Search Input */}
          <div className="flex flex-col sm:flex-row gap-4">
            {/* Search Mode Toggle */}
            <div className="flex rounded-lg border border-[rgb(var(--border))] overflow-hidden shrink-0">
              <button
                onClick={() => { setSearchMode('semantic'); setPage(1); }}
                className={`flex items-center gap-2 px-4 py-2 text-sm font-medium transition-colors ${
                  searchMode === 'semantic'
                    ? 'bg-[rgb(var(--accent))] text-white'
                    : 'bg-[rgb(var(--background))] text-[rgb(var(--muted-foreground))] hover:bg-[rgb(var(--secondary))]'
                }`}
                aria-pressed={searchMode === 'semantic'}
              >
                <Sparkles className="w-4 h-4" />
                Semantic
              </button>
              <button
                onClick={() => { setSearchMode('text'); setPage(1); }}
                className={`flex items-center gap-2 px-4 py-2 text-sm font-medium transition-colors ${
                  searchMode === 'text'
                    ? 'bg-[rgb(var(--accent))] text-white'
                    : 'bg-[rgb(var(--background))] text-[rgb(var(--muted-foreground))] hover:bg-[rgb(var(--secondary))]'
                }`}
                aria-pressed={searchMode === 'text'}
              >
                <Type className="w-4 h-4" />
                Text
              </button>
            </div>

            {/* Search Input */}
            <div className="flex-1">
              <SearchAutocomplete
                placeholder={searchMode === 'semantic'
                  ? "Describe what you're looking for... (e.g., 'cards that draw cards and gain life')"
                  : "Search by card name..."
                }
                onSelect={(card) => {
                  router.push(`/cards/${card.id}`);
                }}
                className="w-full"
              />
            </div>
          </div>

          {/* Manual Search Input for query-based search */}
          <div className="flex gap-2">
            <div className="relative flex-1">
              <SearchIcon className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-[rgb(var(--muted-foreground))]" />
              <input
                type="text"
                value={query}
                onChange={(e) => { setQuery(e.target.value); setPage(1); }}
                placeholder={searchMode === 'semantic'
                  ? "Search by concept or description..."
                  : "Search by card name..."
                }
                className="w-full pl-10 pr-4 py-2 bg-[rgb(var(--background))] border border-[rgb(var(--border))] rounded-lg text-[rgb(var(--foreground))] placeholder:text-[rgb(var(--muted-foreground))] focus:outline-none focus:ring-2 focus:ring-[rgb(var(--accent))] focus:ring-opacity-20 focus:border-[rgb(var(--accent))]"
              />
              {query && (
                <button
                  onClick={() => { setQuery(''); setPage(1); }}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-[rgb(var(--muted-foreground))] hover:text-[rgb(var(--foreground))]"
                  aria-label="Clear search"
                >
                  <X className="w-4 h-4" />
                </button>
              )}
            </div>
            <Button
              variant="secondary"
              onClick={() => setShowFilters(!showFilters)}
              className="shrink-0"
            >
              {showFilters ? <ChevronUp className="w-4 h-4 mr-2" /> : <ChevronDown className="w-4 h-4 mr-2" />}
              Filters
              {hasActiveFilters && (
                <span className="ml-2 px-1.5 py-0.5 text-xs bg-[rgb(var(--accent))] text-white rounded-full">
                  {selectedColors.length + (cardType ? 1 : 0) + (cmcMin !== undefined ? 1 : 0) + (cmcMax !== undefined ? 1 : 0)}
                </span>
              )}
            </Button>
          </div>

          {/* Expandable Filters */}
          {showFilters && (
            <div className="pt-4 border-t border-[rgb(var(--border))] space-y-4">
              {/* Color Filter */}
              <div>
                <label className="block text-sm font-medium text-[rgb(var(--foreground))] mb-2">
                  Colors
                </label>
                <div className="flex flex-wrap gap-2">
                  {MTG_COLORS.map((color) => (
                    <button
                      key={color.code}
                      onClick={() => toggleColor(color.code)}
                      className={`px-3 py-1.5 rounded-full text-sm font-medium border transition-all ${
                        selectedColors.includes(color.code)
                          ? `${color.bgClass} ${color.textClass} ${color.borderClass} ring-2 ring-offset-1 ring-[rgb(var(--accent))]`
                          : `bg-[rgb(var(--secondary))] text-[rgb(var(--muted-foreground))] border-transparent hover:border-[rgb(var(--border))]`
                      }`}
                      aria-pressed={selectedColors.includes(color.code)}
                    >
                      {color.code} - {color.name}
                    </button>
                  ))}
                </div>
              </div>

              {/* Card Type Filter */}
              <div>
                <label className="block text-sm font-medium text-[rgb(var(--foreground))] mb-2">
                  Card Type
                </label>
                <select
                  value={cardType}
                  onChange={(e) => { setCardType(e.target.value); setPage(1); }}
                  className="w-full sm:w-auto px-3 py-2 bg-[rgb(var(--background))] border border-[rgb(var(--border))] rounded-lg text-[rgb(var(--foreground))] focus:outline-none focus:ring-2 focus:ring-[rgb(var(--accent))] focus:ring-opacity-20 focus:border-[rgb(var(--accent))]"
                >
                  <option value="">All Types</option>
                  {CARD_TYPES.map((type) => (
                    <option key={type} value={type}>{type}</option>
                  ))}
                </select>
              </div>

              {/* CMC Range Filter */}
              <div>
                <label className="block text-sm font-medium text-[rgb(var(--foreground))] mb-2">
                  Mana Value (CMC)
                </label>
                <div className="flex items-center gap-2">
                  <input
                    type="number"
                    min="0"
                    max="20"
                    value={cmcMin ?? ''}
                    onChange={(e) => { setCmcMin(e.target.value ? Number(e.target.value) : undefined); setPage(1); }}
                    placeholder="Min"
                    className="w-20 px-3 py-2 bg-[rgb(var(--background))] border border-[rgb(var(--border))] rounded-lg text-[rgb(var(--foreground))] focus:outline-none focus:ring-2 focus:ring-[rgb(var(--accent))] focus:ring-opacity-20 focus:border-[rgb(var(--accent))]"
                  />
                  <span className="text-[rgb(var(--muted-foreground))]">to</span>
                  <input
                    type="number"
                    min="0"
                    max="20"
                    value={cmcMax ?? ''}
                    onChange={(e) => { setCmcMax(e.target.value ? Number(e.target.value) : undefined); setPage(1); }}
                    placeholder="Max"
                    className="w-20 px-3 py-2 bg-[rgb(var(--background))] border border-[rgb(var(--border))] rounded-lg text-[rgb(var(--foreground))] focus:outline-none focus:ring-2 focus:ring-[rgb(var(--accent))] focus:ring-opacity-20 focus:border-[rgb(var(--accent))]"
                  />
                </div>
              </div>

              {/* Clear Filters */}
              {hasActiveFilters && (
                <Button variant="secondary" size="sm" onClick={clearFilters}>
                  <X className="w-4 h-4 mr-2" />
                  Clear All Filters
                </Button>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Search Mode Indicator */}
      {searchMode === 'semantic' && query && (
        <div className="flex items-center gap-2 text-sm text-[rgb(var(--muted-foreground))]">
          <Sparkles className="w-4 h-4 text-[rgb(var(--accent))]" />
          <span>Using semantic search to find cards matching: &quot;{query}&quot;</span>
        </div>
      )}

      {/* Results */}
      {isLoading ? (
        <LoadingPage />
      ) : error ? (
        <ErrorDisplay
          message={error instanceof Error ? error.message : 'Failed to search cards'}
          status={error instanceof Error && 'status' in error ? (error as { status: number }).status : undefined}
          onRetry={() => queryClient.invalidateQueries({ queryKey: ['cards', 'search', query, searchMode, page, selectedColors, cardType, cmcMin, cmcMax] })}
        />
      ) : data?.cards.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center">
            <SearchIcon className="w-12 h-12 mx-auto text-[rgb(var(--muted-foreground))] mb-4" />
            <p className="text-[rgb(var(--muted-foreground))]">
              {query ? 'No cards found matching your search' : 'Start typing to search for cards'}
            </p>
            {hasActiveFilters && (
              <Button variant="secondary" size="sm" onClick={clearFilters} className="mt-4">
                Clear filters and try again
              </Button>
            )}
          </CardContent>
        </Card>
      ) : (
        <>
          {/* Results count */}
          <div className="flex items-center justify-between">
            <p className="text-sm text-[rgb(var(--muted-foreground))]">
              Found {data?.total || 0} cards
              {searchMode === 'semantic' && ' (sorted by relevance)'}
            </p>
          </div>

          {/* Card Grid with Similarity Scores */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {data?.cards.map((card) => (
              <Link key={card.id} href={`/cards/${card.id}`}>
                <Card className="group hover:border-primary-500/50 transition-all cursor-pointer overflow-hidden p-0">
                  {/* Card Image */}
                  <div className="aspect-[5/7] relative bg-[rgb(var(--secondary))] overflow-hidden">
                    {card.image_url_small || card.image_url ? (
                      <Image
                        src={card.image_url_small || card.image_url || ''}
                        alt={card.name}
                        fill
                        className="object-cover group-hover:scale-105 transition-transform duration-300"
                        sizes="(max-width: 640px) 100vw, (max-width: 1024px) 50vw, 25vw"
                      />
                    ) : (
                      <div className="absolute inset-0 flex items-center justify-center text-[rgb(var(--muted-foreground))]">
                        No Image
                      </div>
                    )}
                    {/* Similarity Score Badge */}
                    {searchMode === 'semantic' && card.similarity_score !== undefined && (
                      <div className="absolute top-2 right-2">
                        <Badge variant="accent" className="bg-[rgb(var(--accent))]/90 text-white border-none">
                          {Math.round(card.similarity_score * 100)}% match
                        </Badge>
                      </div>
                    )}
                  </div>

                  {/* Card Info */}
                  <div className="p-4">
                    <h3 className="font-semibold text-[rgb(var(--foreground))] truncate group-hover:text-primary-500 transition-colors">
                      {card.name}
                    </h3>
                    <div className="flex items-center justify-between mt-2">
                      <span className="text-sm text-[rgb(var(--muted-foreground))]">
                        {card.set_code}
                      </span>
                      {card.rarity && (
                        <Badge className={getRarityColor(card.rarity)}>
                          {card.rarity}
                        </Badge>
                      )}
                    </div>
                    {/* Card Type */}
                    {card.type_line && (
                      <p className="text-xs text-[rgb(var(--muted-foreground))] mt-2 truncate">
                        {card.type_line}
                      </p>
                    )}
                  </div>
                </Card>
              </Link>
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

