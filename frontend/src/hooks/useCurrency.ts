'use client';

import { useState, useCallback, useEffect } from 'react';

// Supported currencies
export type Currency = 'USD' | 'EUR';

// Currency display information
const CURRENCY_INFO: Record<Currency, { symbol: string; name: string; locale: string }> = {
  USD: { symbol: '$', name: 'US Dollar', locale: 'en-US' },
  EUR: { symbol: '\u20AC', name: 'Euro', locale: 'de-DE' },
};

const CURRENCY_STORAGE_KEY = 'preferred_currency';

/**
 * Hook for managing user's preferred currency.
 *
 * Persists preference to localStorage and provides formatting utilities.
 */
export function useCurrency() {
  const [currency, setCurrencyState] = useState<Currency>('USD');

  // Load preference from localStorage on mount
  useEffect(() => {
    if (typeof window !== 'undefined') {
      const stored = localStorage.getItem(CURRENCY_STORAGE_KEY) as Currency | null;
      if (stored && (stored === 'USD' || stored === 'EUR')) {
        setCurrencyState(stored);
      }
    }
  }, []);

  // Set currency and persist to localStorage
  const setCurrency = useCallback((newCurrency: Currency) => {
    setCurrencyState(newCurrency);
    if (typeof window !== 'undefined') {
      localStorage.setItem(CURRENCY_STORAGE_KEY, newCurrency);
    }
  }, []);

  // Get currency symbol
  const getSymbol = useCallback(() => {
    return CURRENCY_INFO[currency].symbol;
  }, [currency]);

  // Format a price in the current currency
  const formatPrice = useCallback((
    amount: number,
    options?: { compact?: boolean; showSymbol?: boolean }
  ) => {
    const info = CURRENCY_INFO[currency];
    const formatter = new Intl.NumberFormat(info.locale, {
      style: options?.showSymbol !== false ? 'currency' : 'decimal',
      currency: currency,
      notation: options?.compact ? 'compact' : 'standard',
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });

    return formatter.format(amount);
  }, [currency]);

  // Format a price change percentage
  const formatChange = useCallback((change: number) => {
    const sign = change >= 0 ? '+' : '';
    return `${sign}${change.toFixed(2)}%`;
  }, []);

  return {
    currency,
    setCurrency,
    getSymbol,
    formatPrice,
    formatChange,
    currencyInfo: CURRENCY_INFO[currency],
    availableCurrencies: Object.keys(CURRENCY_INFO) as Currency[],
  };
}
