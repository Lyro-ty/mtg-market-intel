'use client';

import React, { useState } from 'react';
import { useQuery, useInfiniteQuery } from '@tanstack/react-query';
import { Newspaper, Filter, Clock, RefreshCw } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { PageHeader } from '@/components/ornate/page-header';
import { NewsArticleCard } from '@/components/news';
import { getNews, getNewsSources } from '@/lib/api';

const PAGE_SIZE = 20;

export default function NewsPage() {
  const [sourceFilter, setSourceFilter] = useState<string>('all');

  // Fetch available sources
  const { data: sources, isLoading: sourcesLoading } = useQuery({
    queryKey: ['news-sources'],
    queryFn: getNewsSources,
    staleTime: 5 * 60 * 1000,
  });

  // Fetch news with infinite scroll
  const {
    data,
    isLoading,
    isFetchingNextPage,
    hasNextPage,
    fetchNextPage,
    refetch,
  } = useInfiniteQuery({
    queryKey: ['news', sourceFilter],
    queryFn: async ({ pageParam = 0 }) => {
      return getNews({
        source: sourceFilter === 'all' ? undefined : sourceFilter,
        limit: PAGE_SIZE,
        offset: pageParam,
      });
    },
    getNextPageParam: (lastPage, allPages) => {
      const totalFetched = allPages.reduce((sum, page) => sum + page.items.length, 0);
      return lastPage.has_more ? totalFetched : undefined;
    },
    initialPageParam: 0,
    staleTime: 60 * 1000, // 1 minute
  });

  // Flatten pages into single list
  const articles = data?.pages.flatMap((page) => page.items) ?? [];
  const totalCount = data?.pages[0]?.total ?? 0;

  return (
    <div className="container mx-auto px-4 py-8 space-y-8">
      <PageHeader
        title="MTG News"
        subtitle="Latest news and articles from the Magic: The Gathering community"
      />

      {/* Filters */}
      <Card className="glow-accent">
        <CardContent className="p-4">
          <div className="flex flex-col sm:flex-row items-start sm:items-center gap-4 justify-between">
            <div className="flex items-center gap-3">
              <Filter className="w-5 h-5 text-[rgb(var(--muted-foreground))]" />
              <Select
                value={sourceFilter}
                onValueChange={setSourceFilter}
                disabled={sourcesLoading}
              >
                <SelectTrigger className="w-[200px]">
                  <SelectValue placeholder="All sources" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All sources</SelectItem>
                  {sources?.map((source) => (
                    <SelectItem key={source.source} value={source.source}>
                      {source.display} ({source.count})
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="flex items-center gap-4">
              <Badge variant="secondary" className="text-sm">
                {totalCount} article{totalCount !== 1 ? 's' : ''}
              </Badge>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => refetch()}
                className="flex items-center gap-2"
              >
                <RefreshCw className="w-4 h-4" />
                Refresh
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* News List */}
      {isLoading ? (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <Card key={i}>
              <CardHeader className="pb-2">
                <Skeleton className="h-6 w-24" />
              </CardHeader>
              <CardContent>
                <Skeleton className="h-5 w-full mb-2" />
                <Skeleton className="h-5 w-3/4 mb-4" />
                <Skeleton className="h-16 w-full mb-4" />
                <div className="flex justify-between">
                  <Skeleton className="h-4 w-16" />
                  <Skeleton className="h-4 w-24" />
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      ) : articles.length === 0 ? (
        <Card className="glow-accent">
          <CardContent className="p-12 text-center">
            <Newspaper className="w-12 h-12 mx-auto text-[rgb(var(--muted-foreground))] mb-4" />
            <h3 className="text-lg font-semibold text-[rgb(var(--foreground))] mb-2">
              No news articles found
            </h3>
            <p className="text-[rgb(var(--muted-foreground))]">
              {sourceFilter !== 'all'
                ? 'Try selecting a different source or check back later.'
                : 'Check back later for the latest MTG news.'}
            </p>
          </CardContent>
        </Card>
      ) : (
        <>
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {articles.map((article) => (
              <NewsArticleCard key={article.id} article={article} />
            ))}
          </div>

          {/* Load More */}
          {hasNextPage && (
            <div className="flex justify-center pt-4">
              <Button
                variant="outline"
                onClick={() => fetchNextPage()}
                disabled={isFetchingNextPage}
                className="min-w-[200px]"
              >
                {isFetchingNextPage ? (
                  <>
                    <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
                    Loading...
                  </>
                ) : (
                  'Load more articles'
                )}
              </Button>
            </div>
          )}
        </>
      )}

      {/* Last Updated */}
      <div className="flex items-center justify-center gap-2 text-sm text-[rgb(var(--muted-foreground))]">
        <Clock className="w-4 h-4" />
        <span>News updates every hour</span>
      </div>
    </div>
  );
}
