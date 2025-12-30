'use client';

import { useEffect } from 'react';
import * as Sentry from '@sentry/nextjs';
import { AlertTriangle, RefreshCw, Home } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // Log error to console in development
    console.error('Application error:', error);

    // Report to Sentry in production
    Sentry.captureException(error);
  }, [error]);

  return (
    <div className="min-h-screen bg-background flex items-center justify-center p-4">
      <Card className="max-w-md w-full glow-accent border-[rgb(var(--destructive))]/30">
        <CardContent className="p-8 text-center">
          {/* Error Icon */}
          <div className="w-16 h-16 rounded-full bg-[rgb(var(--destructive))]/10 flex items-center justify-center mx-auto mb-6">
            <AlertTriangle className="w-8 h-8 text-[rgb(var(--destructive))]" />
          </div>

          {/* Message */}
          <h1 className="font-display text-2xl text-foreground mb-2">Something Went Wrong</h1>
          <p className="text-muted-foreground mb-6">
            An unexpected error occurred. Don&apos;t worry, your collection is safe.
          </p>

          {/* Error Details (dev only) */}
          {process.env.NODE_ENV === 'development' && (
            <div className="mb-6 p-3 rounded-lg bg-secondary text-left">
              <p className="text-xs text-muted-foreground font-mono break-all">
                {error.message}
              </p>
              {error.digest && (
                <p className="text-xs text-muted-foreground mt-1">
                  Digest: {error.digest}
                </p>
              )}
            </div>
          )}

          {/* Actions */}
          <div className="flex flex-col sm:flex-row gap-3 justify-center">
            <Button
              onClick={reset}
              variant="secondary"
              className="glow-accent"
            >
              <RefreshCw className="w-4 h-4 mr-2" />
              Try Again
            </Button>
            <Button
              asChild
              className="gradient-arcane text-white"
            >
              <a href="/">
                <Home className="w-4 h-4 mr-2" />
                Go Home
              </a>
            </Button>
          </div>

          {/* Support Link */}
          <p className="mt-6 text-sm text-muted-foreground">
            If this keeps happening,{' '}
            <a href="/contact" className="text-[rgb(var(--accent))] hover:underline">
              contact support
            </a>
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
