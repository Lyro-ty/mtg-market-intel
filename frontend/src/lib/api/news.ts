/**
 * News API functions
 */
import type {
  NewsListResponse,
  NewsArticleDetail,
  NewsSource,
  CardNewsResponse,
} from '@/types';
import { fetchApi } from './client';

export async function getNews(options: {
  source?: string;
  limit?: number;
  offset?: number;
} = {}): Promise<NewsListResponse> {
  const params = new URLSearchParams();

  if (options.source) {
    params.set('source', options.source);
  }
  if (options.limit) {
    params.set('limit', String(options.limit));
  }
  if (options.offset) {
    params.set('offset', String(options.offset));
  }

  const queryString = params.toString();
  return fetchApi(`/news${queryString ? `?${queryString}` : ''}`);
}

export async function getNewsArticle(articleId: number): Promise<NewsArticleDetail> {
  return fetchApi(`/news/${articleId}`);
}

export async function getNewsSources(): Promise<NewsSource[]> {
  return fetchApi('/news/sources');
}

export async function getCardNews(
  cardId: number,
  limit: number = 5
): Promise<CardNewsResponse> {
  return fetchApi(`/cards/${cardId}/news?limit=${limit}`);
}
