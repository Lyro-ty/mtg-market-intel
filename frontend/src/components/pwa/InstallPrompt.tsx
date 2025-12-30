'use client';

import { useState, useEffect } from 'react';
import { Download, X } from 'lucide-react';
import { Button } from '@/components/ui/button';

interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }>;
}

const INSTALL_DISMISSED_KEY = 'pwa-install-dismissed';

export function InstallPrompt() {
  const [deferredPrompt, setDeferredPrompt] = useState<BeforeInstallPromptEvent | null>(null);
  const [showPrompt, setShowPrompt] = useState(false);

  useEffect(() => {
    // Check if user has dismissed the prompt before
    const dismissed = localStorage.getItem(INSTALL_DISMISSED_KEY);
    if (dismissed) return;

    const handleBeforeInstallPrompt = (e: Event) => {
      // Prevent the default browser prompt
      e.preventDefault();
      // Store the event for later use
      setDeferredPrompt(e as BeforeInstallPromptEvent);
      // Show our custom prompt after a short delay
      setTimeout(() => setShowPrompt(true), 3000);
    };

    window.addEventListener('beforeinstallprompt', handleBeforeInstallPrompt);

    return () => {
      window.removeEventListener('beforeinstallprompt', handleBeforeInstallPrompt);
    };
  }, []);

  const handleInstall = async () => {
    if (!deferredPrompt) return;

    // Show the browser install prompt
    await deferredPrompt.prompt();

    // Wait for user choice
    const { outcome } = await deferredPrompt.userChoice;

    if (outcome === 'accepted') {
      console.log('PWA installed');
    }

    // Clear the prompt
    setDeferredPrompt(null);
    setShowPrompt(false);
  };

  const handleDismiss = () => {
    // Remember that user dismissed for this session
    localStorage.setItem(INSTALL_DISMISSED_KEY, 'true');
    setShowPrompt(false);
  };

  if (!showPrompt) return null;

  return (
    <div className="fixed bottom-4 left-4 right-4 md:left-auto md:right-4 md:max-w-sm z-50 animate-in slide-in-from-bottom-4">
      <div className="bg-[rgb(var(--card))] border border-[rgb(var(--border))] rounded-xl p-4 shadow-xl">
        <div className="flex items-start gap-3">
          <div className="p-2 rounded-lg bg-gradient-to-br from-[rgb(var(--magic-gold))] to-[rgb(var(--mythic-orange))]">
            <Download className="w-5 h-5 text-white" />
          </div>
          <div className="flex-1">
            <h3 className="font-heading font-semibold text-[rgb(var(--foreground))]">
              Install Dualcaster Deals
            </h3>
            <p className="text-sm text-[rgb(var(--muted-foreground))] mt-1">
              Add to your home screen for quick access and offline support.
            </p>
          </div>
          <button
            onClick={handleDismiss}
            className="p-1 rounded hover:bg-[rgb(var(--secondary))] transition-colors"
            aria-label="Dismiss"
          >
            <X className="w-4 h-4 text-[rgb(var(--muted-foreground))]" />
          </button>
        </div>
        <div className="flex gap-2 mt-3">
          <Button
            variant="primary"
            size="sm"
            onClick={handleInstall}
            className="flex-1 bg-gradient-to-r from-[rgb(var(--magic-gold))] to-[rgb(var(--mythic-orange))]"
          >
            Install App
          </Button>
          <Button
            variant="secondary"
            size="sm"
            onClick={handleDismiss}
          >
            Not Now
          </Button>
        </div>
      </div>
    </div>
  );
}
