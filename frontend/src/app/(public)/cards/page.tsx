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
import { Input } from '@/components/ui/input';
import { PageHeader } from '@/components/ornate/page-header';
import { RarityBadge } from '@/components/ornate/rarity-badge';
import { formatCurrency } from '@/lib/utils';
import type { Card as CardType } from '@/types';
import type { CardRarity } from '@/components/ornate/ornate-card';

// MTG color definitions with mana symbols - dark mode only styling
const MTG_COLORS = [
  { code: 'W', name: 'White', bgClass: 'bg-amber-900/30', textClass: 'text-amber-200', borderClass: 'border-amber-700' },
  { code: 'U', name: 'Blue', bgClass: 'bg-blue-900/30', textClass: 'text-blue-200', borderClass: 'border-blue-700' },
  { code: 'B', name: 'Black', bgClass: 'bg-gray-700', textClass: 'text-gray-200', borderClass: 'border-gray-600' },
  { code: 'R', name: 'Red', bgClass: 'bg-red-900/30', textClass: 'text-red-200', borderClass: 'border-red-700' },
  { code: 'G', name: 'Green', bgClass: 'bg-green-900/30', textClass: 'text-green-200', borderClass: 'border-green-700' },
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
  results: SearchResultCard[];
  total: number;
  page: number;
  page_size: number;
  has_more: boolean;
  search_mode?: string;
}

// Helper to convert rarity string to CardRarity type
function normalizeRarity(rarity: string | undefined): CardRarity | undefined {
  if (!rarity) return undefined;
  const lower = rarity.toLowerCase();
  if (lower === 'common' || lower === 'uncommon' || lower === 'rare' || lower === 'mythic') {
    return lower as CardRarity;
  }
  return undefined;
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
      <PageHeader
        title="Search Cards"
        subtitle="Find MTG cards using semantic or text search"
      />

      {/* Search Controls */}
      <Card className="glow-accent">
        <CardContent className="p-4 space-y-4">
          {/* Search Mode Toggle + Search Input */}
          <div className="flex flex-col sm:flex-row gap-4">
            {/* Search Mode Toggle */}
            <div className="flex rounded-lg border border-border overflow-hidden shrink-0">
              <button
                onClick={() => { setSearchMode('semantic'); setPage(1); }}
                className={`flex items-center gap-2 px-4 py-2 text-sm font-medium transition-all ${
                  searchMode === 'semantic'
                    ? 'gradient-arcane text-white'
                    : 'bg-background text-muted-foreground hover:bg-secondary hover:text-foreground'
                }`}
                aria-pressed={searchMode === 'semantic'}
              >
                <Sparkles className="w-4 h-4" />
                Semantic
              </button>
              <button
                onClick={() => { setSearchMode('text'); setPage(1); }}
                className={`flex items-center gap-2 px-4 py-2 text-sm font-medium transition-all ${
                  searchMode === 'text'
                    ? 'gradient-arcane text-white'
                    : 'bg-background text-muted-foreground hover:bg-secondary hover:text-foreground'
                }`}
                aria-pressed={searchMode === 'text'}
              >
                <Type className="w-4 h-4" />
                Text
              </button>
            </div>

            {/* Search Input */}
            <div className="relative flex-1">
              <SearchIcon className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground z-10" />
              <Input
                type="text"
                value={query}
                onChange={(e) => { setQuery(e.target.value); setPage(1); }}
                placeholder={searchMode === 'semantic'
                  ? "Describe what you're looking for... (e.g., 'cards that draw cards')"
                  : "Search by card name..."
                }
                className="pl-10 pr-10"
              />
              {query && (
                <button
                  onClick={() => { setQuery(''); setPage(1); }}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors z-10"
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
                <span className="ml-2 px-1.5 py-0.5 text-xs gradient-arcane text-white rounded-full">
                  {selectedColors.length + (cardType ? 1 : 0) + (cmcMin !== undefined ? 1 : 0) + (cmcMax !== undefined ? 1 : 0)}
                </span>
              )}
            </Button>
          </div>

          {/* Expandable Filters */}
          {showFilters && (
            <div className="pt-4 border-t border-border space-y-4">
              {/* Color Filter */}
              <div>
                <label className="block text-sm font-medium text-foreground mb-2">
                  Colors
                </label>
                <div className="flex flex-wrap gap-2">
                  {MTG_COLORS.map((color) => (
                    <button
                      key={color.code}
                      onClick={() => toggleColor(color.code)}
                      className={`px-3 py-1.5 rounded-full text-sm font-medium border transition-all ${
                        selectedColors.includes(color.code)
                          ? `${color.bgClass} ${color.textClass} ${color.borderClass} ring-2 ring-offset-1 ring-offset-background ring-[rgb(var(--accent))]`
                          : `bg-secondary text-muted-foreground border-transparent hover:border-border`
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
                <label className="block text-sm font-medium text-foreground mb-2">
                  Card Type
                </label>
                <select
                  value={cardType}
                  onChange={(e) => { setCardType(e.target.value); setPage(1); }}
                  className="w-full sm:w-auto px-3 py-2 bg-background border border-border rounded-lg text-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 focus:ring-offset-background"
                >
                  <option value="">All Types</option>
                  {CARD_TYPES.map((type) => (
                    <option key={type} value={type}>{type}</option>
                  ))}
                </select>
              </div>

              {/* CMC Range Filter */}
              <div>
                <label className="block text-sm font-medium text-foreground mb-2">
                  Mana Value (CMC)
                </label>
                <div className="flex items-center gap-2">
                  <Input
                    type="number"
                    min={0}
                    max={20}
                    value={cmcMin ?? ''}
                    onChange={(e) => { setCmcMin(e.target.value ? Number(e.target.value) : undefined); setPage(1); }}
                    placeholder="Min"
                    className="w-20"
                  />
                  <span className="text-muted-foreground">to</span>
                  <Input
                    type="number"
                    min={0}
                    max={20}
                    value={cmcMax ?? ''}
                    onChange={(e) => { setCmcMax(e.target.value ? Number(e.target.value) : undefined); setPage(1); }}
                    placeholder="Max"
                    className="w-20"
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
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Sparkles className="w-4 h-4 text-[rgb(var(--magic-purple))]" />
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
      ) : (data?.results?.length ?? 0) === 0 ? (
        <Card>
          <CardContent className="py-12 text-center">
            <SearchIcon className="w-12 h-12 mx-auto text-muted-foreground mb-4" />
            <p className="text-muted-foreground">
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
            <p className="text-sm text-muted-foreground">
              Found {data?.total || 0} cards
              {searchMode === 'semantic' && ' (sorted by relevance)'}
            </p>
          </div>

          {/* Card Grid with Similarity Scores */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {data?.results?.map((card) => {
              const cardRarity = normalizeRarity(card.rarity);
              return (
                <Link key={card.id} href={`/cards/${card.id}`}>
                  <Card className="group hover:border-[rgb(var(--accent))]/50 hover:shadow-[0_0_15px_rgb(var(--accent)/0.1)] transition-all cursor-pointer overflow-hidden p-0">
                    {/* Card Image */}
                    <div className="aspect-[5/7] relative bg-secondary overflow-hidden">
                      {card.image_url_small || card.image_url ? (
                        <Image
                          src={card.image_url_small || card.image_url || ''}
                          alt={card.name}
                          fill
                          className="object-cover group-hover:scale-105 transition-transform duration-300"
                          sizes="(max-width: 640px) 100vw, (max-width: 1024px) 50vw, 25vw"
                        />
                      ) : (
                        <div className="absolute inset-0 flex items-center justify-center text-muted-foreground">
                          No Image
                        </div>
                      )}
                      {/* Similarity Score Badge */}
                      {searchMode === 'semantic' && card.similarity_score !== undefined && (
                        <div className="absolute top-2 right-2">
                          <Badge className="gradient-arcane text-white border-none">
                            {Math.round(card.similarity_score * 100)}% match
                          </Badge>
                        </div>
                      )}
                    </div>

                    {/* Card Info */}
                    <div className="p-4">
                      <h3 className="font-semibold text-foreground truncate group-hover:text-[rgb(var(--accent))] transition-colors">
                        {card.name}
                      </h3>
                      <div className="flex items-center justify-between mt-2">
                        <span className="text-sm text-muted-foreground">
                          {card.set_code}
                        </span>
                        {cardRarity && (
                          <RarityBadge rarity={cardRarity} />
                        )}
                      </div>
                      {/* Card Type */}
                      {card.type_line && (
                        <p className="text-xs text-muted-foreground mt-2 truncate">
                          {card.type_line}
                        </p>
                      )}
                    </div>
                  </Card>
                </Link>
              );
            })}
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
              <span className="text-sm text-muted-foreground">
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
