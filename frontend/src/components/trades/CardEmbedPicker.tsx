'use client';

import { useState, useCallback, useEffect } from 'react';
import Image from 'next/image';
import { Search, X, Loader2 } from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { formatCurrency, cn } from '@/lib/utils';

interface CardResult {
  id: number;
  name: string;
  set_code?: string;
  image_url?: string;
  price?: number;
}

interface CardEmbedPickerProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSelect: (card: CardResult) => void;
}

/**
 * Card search modal for embedding cards in trade messages.
 * Uses autocomplete API to search for cards.
 */
export function CardEmbedPicker({
  open,
  onOpenChange,
  onSelect,
}: CardEmbedPickerProps) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<CardResult[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [selectedIndex, setSelectedIndex] = useState(-1);

  // Reset state when dialog closes
  useEffect(() => {
    if (!open) {
      setQuery('');
      setResults([]);
      setSelectedIndex(-1);
    }
  }, [open]);

  // Debounced search
  const searchCards = useCallback(async (searchQuery: string) => {
    if (searchQuery.length < 2) {
      setResults([]);
      return;
    }

    setIsLoading(true);
    try {
      const response = await fetch(
        `/api/search/autocomplete?q=${encodeURIComponent(searchQuery)}&limit=12`
      );
      if (response.ok) {
        const data = await response.json();
        // Transform suggestions to card results
        const cards: CardResult[] = data.suggestions.map((s: {
          id: number;
          name: string;
          set_code?: string;
          image_url?: string;
          price?: number;
        }) => ({
          id: s.id,
          name: s.name,
          set_code: s.set_code,
          image_url: s.image_url,
          price: s.price,
        }));
        setResults(cards);
        setSelectedIndex(-1);
      }
    } catch (error) {
      console.error('Card search error:', error);
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Debounce effect
  useEffect(() => {
    const timer = setTimeout(() => {
      searchCards(query);
    }, 200);

    return () => clearTimeout(timer);
  }, [query, searchCards]);

  const handleSelect = (card: CardResult) => {
    onSelect(card);
    onOpenChange(false);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault();
        setSelectedIndex((prev) =>
          prev < results.length - 1 ? prev + 1 : prev
        );
        break;
      case 'ArrowUp':
        e.preventDefault();
        setSelectedIndex((prev) => (prev > 0 ? prev - 1 : -1));
        break;
      case 'Enter':
        e.preventDefault();
        if (selectedIndex >= 0 && selectedIndex < results.length) {
          handleSelect(results[selectedIndex]);
        }
        break;
      case 'Escape':
        e.preventDefault();
        onOpenChange(false);
        break;
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Embed Card</DialogTitle>
        </DialogHeader>

        {/* Search input */}
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-[rgb(var(--muted-foreground))]" />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Search for a card..."
            autoFocus
            className={cn(
              'w-full pl-10 pr-10 py-2 rounded-lg border border-[rgb(var(--border))] bg-[rgb(var(--background))] text-sm',
              'placeholder:text-[rgb(var(--muted-foreground))]',
              'focus:outline-none focus:ring-2 focus:ring-amber-500/20 focus:border-amber-500/50'
            )}
          />
          {query && (
            <button
              onClick={() => setQuery('')}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-[rgb(var(--muted-foreground))] hover:text-[rgb(var(--foreground))]"
            >
              <X className="h-4 w-4" />
            </button>
          )}
          {isLoading && (
            <div className="absolute right-10 top-1/2 -translate-y-1/2">
              <Loader2 className="h-4 w-4 animate-spin text-[rgb(var(--muted-foreground))]" />
            </div>
          )}
        </div>

        {/* Results */}
        <ScrollArea className="h-[300px] mt-2">
          {results.length === 0 && query.length >= 2 && !isLoading ? (
            <div className="flex items-center justify-center h-full text-sm text-[rgb(var(--muted-foreground))]">
              No cards found
            </div>
          ) : results.length === 0 && query.length < 2 ? (
            <div className="flex items-center justify-center h-full text-sm text-[rgb(var(--muted-foreground))]">
              Type at least 2 characters to search
            </div>
          ) : (
            <div className="grid grid-cols-3 gap-2 p-1">
              {results.map((card, index) => (
                <button
                  key={card.id}
                  onClick={() => handleSelect(card)}
                  onMouseEnter={() => setSelectedIndex(index)}
                  className={cn(
                    'flex flex-col items-center p-2 rounded-lg border transition-colors',
                    index === selectedIndex
                      ? 'border-amber-500 bg-amber-500/10'
                      : 'border-transparent hover:border-[rgb(var(--border))] hover:bg-[rgb(var(--secondary))]'
                  )}
                >
                  {/* Card image */}
                  {card.image_url ? (
                    <Image
                      src={card.image_url}
                      alt={card.name}
                      width={80}
                      height={112}
                      className="rounded object-cover"
                      unoptimized
                    />
                  ) : (
                    <div className="w-20 h-28 rounded bg-gradient-to-br from-amber-900/40 to-amber-700/20 flex items-center justify-center">
                      <span className="text-xs text-amber-500/60 font-medium">MTG</span>
                    </div>
                  )}

                  {/* Card info */}
                  <div className="mt-2 text-center w-full">
                    <div className="text-xs font-medium text-[rgb(var(--foreground))] line-clamp-1">
                      {card.name}
                    </div>
                    {card.set_code && (
                      <div className="text-[10px] text-[rgb(var(--muted-foreground))] uppercase">
                        {card.set_code}
                      </div>
                    )}
                    {card.price !== undefined && card.price !== null && (
                      <div className="text-xs font-semibold text-amber-500 mt-0.5">
                        {formatCurrency(card.price)}
                      </div>
                    )}
                  </div>
                </button>
              ))}
            </div>
          )}
        </ScrollArea>

        {/* Footer */}
        <div className="flex justify-end pt-2 border-t border-[rgb(var(--border))]">
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
