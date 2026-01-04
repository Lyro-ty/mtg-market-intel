'use client';

import { useEffect, useCallback, useState } from 'react';
import { useRouter } from 'next/navigation';

interface ShortcutHandlers {
  onSearch?: () => void;
  onEscape?: () => void;
  onHelp?: () => void;
}

/**
 * Global keyboard shortcuts hook.
 *
 * Shortcuts:
 * - `/` or `Cmd+K` - Focus search (triggers onSearch)
 * - `Escape` - Close modals, blur inputs (triggers onEscape)
 * - `?` - Show keyboard shortcuts help (triggers onHelp)
 * - `g h` - Go to home
 * - `g c` - Go to cards
 * - `g d` - Go to dashboard
 */
export function useKeyboardShortcuts(handlers: ShortcutHandlers = {}) {
  const router = useRouter();
  const [showHelp, setShowHelp] = useState(false);
  const [pendingKey, setPendingKey] = useState<string | null>(null);

  const handleKeyDown = useCallback((event: KeyboardEvent) => {
    const target = event.target as HTMLElement;
    const isInput = target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable;

    // Handle Escape - always works
    if (event.key === 'Escape') {
      event.preventDefault();
      setShowHelp(false);
      setPendingKey(null);
      // Blur any focused input
      if (document.activeElement instanceof HTMLElement) {
        document.activeElement.blur();
      }
      handlers.onEscape?.();
      return;
    }

    // Don't trigger shortcuts when typing in inputs (except Escape)
    if (isInput) return;

    // Handle two-key combos (g + letter)
    if (pendingKey === 'g') {
      setPendingKey(null);
      switch (event.key.toLowerCase()) {
        case 'h':
          event.preventDefault();
          router.push('/');
          return;
        case 'c':
          event.preventDefault();
          router.push('/cards');
          return;
        case 'd':
          event.preventDefault();
          router.push('/dashboard');
          return;
        case 'm':
          event.preventDefault();
          router.push('/market');
          return;
      }
    }

    // Start g combo
    if (event.key === 'g') {
      setPendingKey('g');
      // Clear after 1 second if no second key
      setTimeout(() => setPendingKey(null), 1000);
      return;
    }

    // Handle `/` - Focus search
    if (event.key === '/') {
      event.preventDefault();
      handlers.onSearch?.();
      return;
    }

    // Handle Cmd/Ctrl + K - Focus search
    if ((event.metaKey || event.ctrlKey) && event.key === 'k') {
      event.preventDefault();
      handlers.onSearch?.();
      return;
    }

    // Handle `?` - Show help
    if (event.key === '?' || (event.shiftKey && event.key === '/')) {
      event.preventDefault();
      setShowHelp((prev) => !prev);
      handlers.onHelp?.();
      return;
    }
  }, [handlers, pendingKey, router]);

  useEffect(() => {
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);

  return {
    showHelp,
    setShowHelp,
    pendingKey,
  };
}

/**
 * All keyboard shortcuts for the help modal
 */
export const KEYBOARD_SHORTCUTS = [
  { keys: ['/', 'Cmd+K'], description: 'Focus search' },
  { keys: ['Esc'], description: 'Close modal / Blur input' },
  { keys: ['?'], description: 'Show this help' },
  { keys: ['g', 'h'], description: 'Go to Home', combo: true },
  { keys: ['g', 'c'], description: 'Go to Cards', combo: true },
  { keys: ['g', 'd'], description: 'Go to Dashboard', combo: true },
  { keys: ['g', 'm'], description: 'Go to Market', combo: true },
];
