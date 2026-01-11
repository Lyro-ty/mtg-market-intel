/**
 * Utility functions for the frontend
 */

import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

/**
 * Merge Tailwind CSS classes (shadcn/ui compatible)
 */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/**
 * Format a number as currency
 */
export function formatCurrency(
  value: number | undefined | null,
  currency: string = 'USD'
): string {
  if (value === undefined || value === null || isNaN(value)) return '-';

  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency,
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);
}

/**
 * Safely format a number with toFixed, returning fallback for null/undefined/NaN.
 */
export function safeToFixed(
  value: number | null | undefined,
  decimals: number = 2,
  fallback: string = '-'
): string {
  if (value === null || value === undefined || isNaN(value)) {
    return fallback;
  }
  return value.toFixed(decimals);
}

/**
 * Format a percentage value safely.
 * @param includeSign - If true, always include +/- sign. If false, no sign prefix.
 */
export function formatPercent(
  value: number | undefined | null,
  decimals: number = 1,
  includeSign: boolean = true
): string {
  if (value === undefined || value === null || isNaN(value)) return '-';

  const sign = includeSign && value > 0 ? '+' : '';
  return `${sign}${value.toFixed(decimals)}%`;
}

/**
 * Format a number with optional decimal places
 */
export function formatNumber(
  value: number | undefined | null,
  decimals: number = 0
): string {
  if (value === undefined || value === null || isNaN(value)) return '-';

  return new Intl.NumberFormat('en-US', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(value);
}

/**
 * Format a date string
 */
export function formatDate(
  date: string | Date | undefined | null,
  options: Intl.DateTimeFormatOptions = {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  }
): string {
  if (!date) return '-';

  const d = typeof date === 'string' ? new Date(date) : date;
  return new Intl.DateTimeFormat('en-US', options).format(d);
}

/**
 * Format a relative time string (e.g., "2 hours ago")
 */
export function formatRelativeTime(date: string | Date | undefined | null): string {
  if (!date) return '-';

  const d = typeof date === 'string' ? new Date(date) : date;
  const now = new Date();
  const diffMs = now.getTime() - d.getTime();
  const diffSecs = Math.floor(diffMs / 1000);
  const diffMins = Math.floor(diffSecs / 60);
  const diffHours = Math.floor(diffMins / 60);
  const diffDays = Math.floor(diffHours / 24);

  if (diffDays > 0) return `${diffDays}d ago`;
  if (diffHours > 0) return `${diffHours}h ago`;
  if (diffMins > 0) return `${diffMins}m ago`;
  return 'just now';
}

/**
 * Get color class for price change
 */
export function getPriceChangeColor(change: number | undefined | null): string {
  if (change === undefined || change === null) return 'text-gray-500';
  if (change > 0) return 'text-green-500';
  if (change < 0) return 'text-red-500';
  return 'text-gray-500';
}

/**
 * Get background color class for action type
 */
export function getActionColor(action: string): string {
  switch (action) {
    case 'BUY':
      return 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200';
    case 'SELL':
      return 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200';
    case 'HOLD':
      return 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200';
    default:
      return 'bg-gray-100 text-gray-800';
  }
}

/**
 * Get rarity color class
 */
export function getRarityColor(rarity: string | undefined): string {
  switch (rarity?.toLowerCase()) {
    case 'mythic':
      return 'text-orange-500';
    case 'rare':
      return 'text-yellow-500';
    case 'uncommon':
      return 'text-gray-400';
    case 'common':
      return 'text-gray-600';
    default:
      return 'text-gray-500';
  }
}

/**
 * Truncate text to a maximum length
 */
export function truncate(text: string, maxLength: number): string {
  if (text.length <= maxLength) return text;
  return text.slice(0, maxLength - 3) + '...';
}

/**
 * Generate a TCGPlayer affiliate link for a card
 * Uses Impact.com partner vanity link for affiliate tracking
 *
 * Format: https://partner.tcgplayer.com/VANITY_SLUG?u=ENCODED_TCGPLAYER_URL
 */
export function getTcgPlayerUrl(cardName: string, setCode?: string): string {
  const searchQuery = setCode ? `${cardName} ${setCode}` : cardName;
  const tcgPlayerUrl = `https://www.tcgplayer.com/search/magic/product?q=${encodeURIComponent(searchQuery)}`;

  // Dualcaster Deals vanity affiliate link
  const encodedUrl = encodeURIComponent(tcgPlayerUrl);
  return `https://partner.tcgplayer.com/dualcaster?u=${encodedUrl}`;
}
