'use client';

import { ExternalLink, Newspaper } from 'lucide-react';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { formatRelativeTime } from '@/lib/utils';
import type { NewsArticle } from '@/types';

interface NewsArticleCardProps {
  article: NewsArticle;
  compact?: boolean;
}

export function NewsArticleCard({ article, compact = false }: NewsArticleCardProps) {
  const handleClick = () => {
    window.open(article.external_url, '_blank', 'noopener,noreferrer');
  };

  if (compact) {
    return (
      <button
        onClick={handleClick}
        className="w-full text-left p-3 rounded-lg bg-[rgb(var(--secondary))] hover:bg-[rgb(var(--secondary))]/80 transition-colors"
      >
        <div className="flex items-start justify-between gap-2">
          <div className="flex-1 min-w-0">
            <h4 className="text-sm font-medium text-[rgb(var(--foreground))] line-clamp-2">
              {article.title}
            </h4>
            <div className="flex items-center gap-2 mt-1 text-xs text-[rgb(var(--muted-foreground))]">
              <span>{article.source_display}</span>
              {article.published_at && (
                <>
                  <span>•</span>
                  <span>{formatRelativeTime(article.published_at)}</span>
                </>
              )}
            </div>
          </div>
          <ExternalLink className="h-4 w-4 flex-shrink-0 text-[rgb(var(--muted-foreground))]" />
        </div>
      </button>
    );
  }

  return (
    <Card
      className="group hover:border-primary-500/50 transition-all cursor-pointer"
      onClick={handleClick}
    >
      <CardHeader className="pb-2">
        <div className="flex items-start justify-between gap-4">
          <div className="flex items-center gap-2">
            <Newspaper className="h-5 w-5 text-primary-500" />
            <Badge variant="secondary">{article.source_display}</Badge>
          </div>
          <ExternalLink className="h-4 w-4 text-[rgb(var(--muted-foreground))] group-hover:text-primary-500 transition-colors" />
        </div>
      </CardHeader>
      <CardContent>
        <h3 className="font-semibold text-[rgb(var(--foreground))] group-hover:text-primary-500 transition-colors line-clamp-2">
          {article.title}
        </h3>

        {article.summary && (
          <p className="mt-2 text-sm text-[rgb(var(--muted-foreground))] line-clamp-3">
            {article.summary}
          </p>
        )}

        <div className="flex items-center justify-between mt-4">
          <span className="text-xs text-[rgb(var(--muted-foreground))]">
            {article.published_at ? formatRelativeTime(article.published_at) : 'Unknown date'}
          </span>
          {article.card_mention_count > 0 && (
            <Badge variant="outline" className="text-xs">
              {article.card_mention_count} card{article.card_mention_count !== 1 ? 's' : ''} mentioned
            </Badge>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
