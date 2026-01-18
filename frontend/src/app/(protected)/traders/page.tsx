'use client';

import { useState, useMemo, useCallback } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Users } from 'lucide-react';

import { PageHeader } from '@/components/ornate/page-header';
import { DirectoryFilters, type DirectoryFiltersState } from './components/DirectoryFilters';
import { DirectoryGrid } from './components/DirectoryGrid';
import {
  getDirectory,
  getFavorites,
  addFavorite,
  removeFavorite,
  type DirectorySearchParams,
} from '@/lib/api/directory';

const PAGE_SIZE = 20;

export default function TradersPage() {
  // Filter state
  const [filters, setFilters] = useState<DirectoryFiltersState>({
    q: '',
    sort: 'discovery_score',
    reputationTier: [],
    frameTier: [],
    cardType: [],
    format: [],
    shipping: [],
    onlineOnly: false,
    verifiedOnly: false,
  });

  // View mode state
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');

  // Pagination state (0-indexed)
  const [page, setPage] = useState(0);

  const queryClient = useQueryClient();

  // Build API params from filter state
  const apiParams = useMemo<DirectorySearchParams>(
    () => ({
      q: filters.q || undefined,
      sort: filters.sort,
      reputation_tier: filters.reputationTier.length > 0 ? filters.reputationTier : undefined,
      frame_tier: filters.frameTier.length > 0 ? filters.frameTier : undefined,
      card_type: filters.cardType.length > 0 ? filters.cardType : undefined,
      format: filters.format.length > 0 ? filters.format : undefined,
      shipping: filters.shipping.length > 0 ? filters.shipping : undefined,
      online_only: filters.onlineOnly || undefined,
      verified_only: filters.verifiedOnly || undefined,
      page: page + 1, // API is 1-indexed
      limit: PAGE_SIZE,
    }),
    [filters, page]
  );

  // Fetch directory data
  const {
    data: directoryData,
    isLoading: isLoadingDirectory,
    error: directoryError,
  } = useQuery({
    queryKey: ['directory', apiParams],
    queryFn: () => getDirectory(apiParams),
    staleTime: 30000, // 30 seconds
    placeholderData: (previousData) => previousData,
  });

  // Fetch user's favorites
  const { data: favoritesData } = useQuery({
    queryKey: ['favorites'],
    queryFn: getFavorites,
    staleTime: 60000, // 1 minute
  });

  // Build set of favorite user IDs for quick lookup
  const favoriteIds = useMemo(() => {
    if (!favoritesData?.favorites) return new Set<number>();
    return new Set(favoritesData.favorites.map((f) => f.favorited_user_id));
  }, [favoritesData]);

  // Add favorite mutation
  const addFavoriteMutation = useMutation({
    mutationFn: (userId: number) => addFavorite(userId, false),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['favorites'] });
    },
  });

  // Remove favorite mutation
  const removeFavoriteMutation = useMutation({
    mutationFn: (userId: number) => removeFavorite(userId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['favorites'] });
    },
  });

  // Handle favorite toggle
  const handleToggleFavorite = useCallback(
    (userId: number) => {
      if (favoriteIds.has(userId)) {
        removeFavoriteMutation.mutate(userId);
      } else {
        addFavoriteMutation.mutate(userId);
      }
    },
    [favoriteIds, addFavoriteMutation, removeFavoriteMutation]
  );

  // Handle filter changes - reset to page 0
  const handleFiltersChange = useCallback((newFilters: DirectoryFiltersState) => {
    setFilters(newFilters);
    setPage(0); // Reset pagination when filters change
  }, []);

  // Handle page change
  const handlePageChange = useCallback((newPage: number) => {
    setPage(newPage);
    // Scroll to top of grid
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }, []);

  return (
    <div className="container mx-auto px-4 py-8 space-y-8">
      {/* Page Header */}
      <PageHeader
        title="Trader Directory"
        subtitle="Find and connect with MTG traders in the community"
      >
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Users className="h-4 w-4" />
          <span>{directoryData?.total ?? 0} traders</span>
        </div>
      </PageHeader>

      {/* Filters */}
      <DirectoryFilters
        filters={filters}
        onChange={handleFiltersChange}
        viewMode={viewMode}
        onViewModeChange={setViewMode}
      />

      {/* Error State */}
      {directoryError && (
        <div className="p-4 bg-destructive/10 border border-destructive/20 rounded-lg text-destructive">
          <p className="font-semibold">Error loading directory</p>
          <p className="text-sm">
            {directoryError instanceof Error
              ? directoryError.message
              : 'An unexpected error occurred'}
          </p>
        </div>
      )}

      {/* Directory Grid */}
      <DirectoryGrid
        users={directoryData?.users ?? []}
        total={directoryData?.total ?? 0}
        isLoading={isLoadingDirectory}
        viewMode={viewMode}
        page={page}
        pageSize={PAGE_SIZE}
        onPageChange={handlePageChange}
        favoriteIds={favoriteIds}
        onToggleFavorite={handleToggleFavorite}
      />
    </div>
  );
}
