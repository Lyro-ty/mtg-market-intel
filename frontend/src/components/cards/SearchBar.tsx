'use client';

import { useState, useRef, useEffect } from 'react';
import { Search } from 'lucide-react';
import { Input } from '@/components/ui/Input';

interface SearchBarProps {
  onSearch: (query: string) => void;
  placeholder?: string;
  value?: string;
}

export function SearchBar({
  onSearch,
  placeholder = 'Search cards...',
  value: controlledValue,
}: SearchBarProps) {
  const [value, setValue] = useState(controlledValue ?? '');
  const timeoutRef = useRef<NodeJS.Timeout | null>(null);
  const pendingSearchRef = useRef<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const wasFocusedRef = useRef(false);
  
  // Sync from parent only if we're not waiting for a debounced search
  // This prevents the parent from overwriting user input while they're typing
  useEffect(() => {
    if (controlledValue !== undefined) {
      // If we have a pending search, only accept parent updates that match what we're waiting for
      // This means the parent update is from our own onSearch callback
      // If pending is null or the values don't match, it's a programmatic change (e.g., clearing filters)
      if (pendingSearchRef.current === null) {
        // No pending search, safe to sync from parent
        setValue(controlledValue);
      } else if (controlledValue === pendingSearchRef.current) {
        // Parent value matches what we're waiting for, this is from our own callback
        // Don't update state (it's already correct), but clear pending
        pendingSearchRef.current = null;
      }
      // If pending exists and doesn't match, ignore the parent update (user is still typing)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [controlledValue]);
  
  // Maintain focus after re-renders caused by parent updates
  useEffect(() => {
    // If the input was focused before and it's not focused now, restore focus
    // This handles cases where parent re-renders cause the input to lose focus
    if (wasFocusedRef.current && inputRef.current && document.activeElement !== inputRef.current) {
      // Use requestAnimationFrame to ensure DOM is ready
      requestAnimationFrame(() => {
        if (inputRef.current && wasFocusedRef.current && document.activeElement !== inputRef.current) {
          inputRef.current.focus();
        }
      });
    }
  });

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newValue = e.target.value;
    setValue(newValue);
    pendingSearchRef.current = newValue; // Mark that we're waiting for this value to be searched
    wasFocusedRef.current = document.activeElement === e.target;
    
    // Debounce the search
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
    }
    timeoutRef.current = setTimeout(() => {
      onSearch(newValue);
      // Clear pending after search is executed
      // The parent will update and pass the value back, which we'll accept since pending is cleared
      pendingSearchRef.current = null;
    }, 300);
  };

  // Cleanup timeout on unmount
  useEffect(() => {
    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
    };
  }, []);

  return (
    <div className="relative">
      <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-[rgb(var(--muted-foreground))]" />
      <Input
        ref={inputRef}
        type="text"
        value={value}
        onChange={handleChange}
        onFocus={() => {
          wasFocusedRef.current = true;
        }}
        onBlur={() => {
          wasFocusedRef.current = false;
        }}
        placeholder={placeholder}
        className="pl-10"
      />
    </div>
  );
}

