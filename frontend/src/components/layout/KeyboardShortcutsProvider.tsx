'use client';

import { ReactNode, useCallback, useRef } from 'react';
import { useKeyboardShortcuts } from '@/hooks';
import { KeyboardShortcutsModal } from '@/components/ui/KeyboardShortcutsModal';

interface KeyboardShortcutsProviderProps {
  children: ReactNode;
}

/**
 * Global keyboard shortcuts provider.
 * Handles global shortcuts like `/` for search, `?` for help.
 */
export function KeyboardShortcutsProvider({ children }: KeyboardShortcutsProviderProps) {
  // Try to find a search input on the page
  const focusSearch = useCallback(() => {
    // Try multiple selectors to find a search input
    const searchInput = document.querySelector<HTMLInputElement>(
      'input[type="search"], input[placeholder*="Search"], input[placeholder*="search"], [data-search-input]'
    );
    if (searchInput) {
      searchInput.focus();
      searchInput.select();
    } else {
      // If no search input found, navigate to cards page
      window.location.href = '/cards';
    }
  }, []);

  const { showHelp, setShowHelp } = useKeyboardShortcuts({
    onSearch: focusSearch,
  });

  return (
    <>
      {children}
      <KeyboardShortcutsModal
        isOpen={showHelp}
        onClose={() => setShowHelp(false)}
      />
    </>
  );
}
