'use client';

import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/Button';
import { ThemePicker } from '@/components/ui/ThemePicker';

const WELCOME_SEEN_KEY = 'mtg-welcome-seen';

export function WelcomeModal() {
  const [isOpen, setIsOpen] = useState(false);

  useEffect(() => {
    const hasSeen = localStorage.getItem(WELCOME_SEEN_KEY);
    if (!hasSeen) {
      setIsOpen(true);
    }
  }, []);

  const handleDismiss = () => {
    localStorage.setItem(WELCOME_SEEN_KEY, 'true');
    setIsOpen(false);
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/60 animate-fade-in"
        onClick={handleDismiss}
      />

      {/* Modal */}
      <div className="relative bg-[rgb(var(--card))] rounded-xl p-8 max-w-md mx-4 animate-scale-in shadow-2xl border border-[rgb(var(--border))]">
        <h2 className="text-2xl font-bold mb-2 text-[rgb(var(--foreground))]">Welcome, Planeswalker!</h2>
        <p className="text-[rgb(var(--muted-foreground))] mb-6">
          Choose your mana affinity to personalize your experience
        </p>

        <div className="mb-8 flex justify-center">
          <ThemePicker />
        </div>

        <div className="flex gap-3">
          <Button onClick={handleDismiss} className="flex-1">
            Get Started
          </Button>
          <Button variant="ghost" onClick={handleDismiss}>
            Skip for now
          </Button>
        </div>
      </div>
    </div>
  );
}
