'use client';

import { X, Keyboard } from 'lucide-react';
import { KEYBOARD_SHORTCUTS } from '@/hooks';
import { Card, CardContent, CardHeader, CardTitle } from './card';

interface KeyboardShortcutsModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export function KeyboardShortcutsModal({ isOpen, onClose }: KeyboardShortcutsModalProps) {
  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
      onClick={onClose}
    >
      <Card
        className="w-full max-w-md bg-[rgb(var(--card))] border-[rgb(var(--border))] shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <CardHeader className="border-b border-[rgb(var(--border))]">
          <div className="flex items-center justify-between">
            <CardTitle className="flex items-center gap-2">
              <Keyboard className="w-5 h-5 text-[rgb(var(--accent))]" />
              Keyboard Shortcuts
            </CardTitle>
            <button
              onClick={onClose}
              className="p-2 rounded-lg hover:bg-[rgb(var(--secondary))] transition-colors"
              aria-label="Close"
            >
              <X className="w-5 h-5 text-[rgb(var(--muted-foreground))]" />
            </button>
          </div>
        </CardHeader>
        <CardContent className="p-4">
          <div className="space-y-3">
            {KEYBOARD_SHORTCUTS.map((shortcut, idx) => (
              <div
                key={idx}
                className="flex items-center justify-between py-2 border-b border-[rgb(var(--border))] last:border-0"
              >
                <span className="text-[rgb(var(--foreground))]">
                  {shortcut.description}
                </span>
                <div className="flex items-center gap-1">
                  {shortcut.combo ? (
                    <>
                      <kbd className="px-2 py-1 text-xs font-mono bg-[rgb(var(--secondary))] border border-[rgb(var(--border))] rounded">
                        {shortcut.keys[0]}
                      </kbd>
                      <span className="text-[rgb(var(--muted-foreground))] text-xs">then</span>
                      <kbd className="px-2 py-1 text-xs font-mono bg-[rgb(var(--secondary))] border border-[rgb(var(--border))] rounded">
                        {shortcut.keys[1]}
                      </kbd>
                    </>
                  ) : (
                    shortcut.keys.map((key, keyIdx) => (
                      <span key={keyIdx} className="flex items-center">
                        {keyIdx > 0 && <span className="text-[rgb(var(--muted-foreground))] mx-1 text-xs">or</span>}
                        <kbd className="px-2 py-1 text-xs font-mono bg-[rgb(var(--secondary))] border border-[rgb(var(--border))] rounded">
                          {key}
                        </kbd>
                      </span>
                    ))
                  )}
                </div>
              </div>
            ))}
          </div>
          <p className="mt-4 text-xs text-[rgb(var(--muted-foreground))] text-center">
            Press <kbd className="px-1 py-0.5 text-xs font-mono bg-[rgb(var(--secondary))] border border-[rgb(var(--border))] rounded">Esc</kbd> to close
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
