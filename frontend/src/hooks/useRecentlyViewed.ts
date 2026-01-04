'use client';

import { useState, useEffect, useCallback } from 'react';

const STORAGE_KEY = 'mtg-recently-viewed-cards';
const MAX_RECENT_CARDS = 12;

export interface RecentCard {
  id: number;
  name: string;
  set_code: string;
  image_url?: string | null;
  viewedAt: number;
}

/**
 * Hook for managing recently viewed cards.
 * Stores up to 12 recent cards in localStorage.
 */
export function useRecentlyViewed() {
  const [recentCards, setRecentCards] = useState<RecentCard[]>([]);
  const [isLoaded, setIsLoaded] = useState(false);

  // Load from localStorage on mount
  useEffect(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored) {
        const parsed = JSON.parse(stored) as RecentCard[];
        setRecentCards(parsed);
      }
    } catch (e) {
      console.error('Failed to load recently viewed cards:', e);
    }
    setIsLoaded(true);
  }, []);

  // Save to localStorage whenever recentCards changes
  useEffect(() => {
    if (isLoaded) {
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(recentCards));
      } catch (e) {
        console.error('Failed to save recently viewed cards:', e);
      }
    }
  }, [recentCards, isLoaded]);

  // Add a card to recently viewed
  const addRecentCard = useCallback((card: Omit<RecentCard, 'viewedAt'>) => {
    setRecentCards((prev) => {
      // Remove if already exists
      const filtered = prev.filter((c) => c.id !== card.id);
      // Add to front with timestamp
      const updated = [{ ...card, viewedAt: Date.now() }, ...filtered];
      // Limit to max
      return updated.slice(0, MAX_RECENT_CARDS);
    });
  }, []);

  // Clear all recent cards
  const clearRecentCards = useCallback(() => {
    setRecentCards([]);
  }, []);

  return {
    recentCards,
    addRecentCard,
    clearRecentCards,
    isLoaded,
  };
}
