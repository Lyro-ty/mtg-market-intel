'use client';

import Link from 'next/link';
import { Home, Search, ArrowLeft } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';

export default function NotFound() {
  return (
    <div className="min-h-screen bg-background flex items-center justify-center p-4">
      <Card className="max-w-md w-full glow-accent">
        <CardContent className="p-8 text-center">
          {/* 404 Display */}
          <div className="mb-6">
            <p className="font-display text-8xl text-[rgb(var(--accent))] opacity-20">404</p>
            <h1 className="font-display text-2xl text-foreground -mt-4">Page Not Found</h1>
          </div>

          {/* Message */}
          <p className="text-muted-foreground mb-8">
            Looks like this card got lost in the Blind Eternities.
            The page you&apos;re looking for doesn&apos;t exist or has been moved.
          </p>

          {/* Actions */}
          <div className="flex flex-col sm:flex-row gap-3 justify-center">
            <Button asChild variant="secondary" className="glow-accent">
              <Link href="/">
                <Home className="w-4 h-4 mr-2" />
                Go Home
              </Link>
            </Button>
            <Button asChild className="gradient-arcane text-white">
              <Link href="/cards">
                <Search className="w-4 h-4 mr-2" />
                Search Cards
              </Link>
            </Button>
          </div>

          {/* Back Link */}
          <div className="mt-6">
            <button
              onClick={() => typeof window !== 'undefined' && window.history.back()}
              className="text-sm text-muted-foreground hover:text-foreground transition-colors inline-flex items-center gap-1"
            >
              <ArrowLeft className="w-4 h-4" />
              Go back
            </button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
