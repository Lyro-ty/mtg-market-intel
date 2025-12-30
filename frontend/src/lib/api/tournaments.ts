/**
 * Tournaments API functions
 */
import type {
  TournamentListResponse,
  TournamentDetail,
  DecklistDetail,
  MetaCardsListResponse,
  MetaPeriod,
} from '@/types';
import { fetchApi } from './client';

export async function getTournaments(options: {
  format?: string;
  days?: number;
  minPlayers?: number;
  page?: number;
  pageSize?: number;
} = {}): Promise<TournamentListResponse> {
  const params = new URLSearchParams();

  if (options.format) params.set('format', options.format);
  if (options.days !== undefined) params.set('days', String(options.days));
  if (options.minPlayers !== undefined) params.set('min_players', String(options.minPlayers));
  params.set('page', String(options.page || 1));
  params.set('page_size', String(options.pageSize || 20));

  return fetchApi(`/tournaments?${params}`);
}

export async function getTournament(tournamentId: number): Promise<TournamentDetail> {
  return fetchApi(`/tournaments/${tournamentId}`);
}

export async function getDecklist(tournamentId: number, decklistId: number): Promise<DecklistDetail> {
  return fetchApi(`/tournaments/${tournamentId}/decklists/${decklistId}`);
}

export async function getMetaCards(options: {
  format: string;
  period?: MetaPeriod;
  page?: number;
  pageSize?: number;
} = { format: 'Modern' }): Promise<MetaCardsListResponse> {
  const params = new URLSearchParams();

  params.set('format', options.format);
  if (options.period) params.set('period', options.period);
  params.set('page', String(options.page || 1));
  params.set('page_size', String(options.pageSize || 50));

  return fetchApi(`/meta/cards?${params}`);
}
