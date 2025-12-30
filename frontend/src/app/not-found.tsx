import Link from 'next/link';
import { Search, Home } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';

export default function NotFound() {
  return (
    <div className="min-h-screen bg-background flex items-center justify-center p-4">
      <Card className="max-w-md w-full glow-accent">
        <CardContent className="p-8 text-center">
          {/* 404 Display */}
          <div className="mb-6">
            <span className="text-8xl font-bold bg-gradient-to-r from-[rgb(var(--magic-gold))] to-[rgb(var(--mythic-orange))] bg-clip-text text-transparent">
              404
            </span>
          </div>

          {/* Message */}
          <h1 className="font-display text-2xl text-foreground mb-2">Page Not Found</h1>
          <p className="text-muted-foreground mb-6">
            This card seems to have phased out of existence. Let&apos;s get you back on track.
          </p>

          {/* Actions */}
          <div className="flex flex-col sm:flex-row gap-3 justify-center">
            <Button asChild variant="secondary" className="glow-accent">
              <Link href="/cards">
                <Search className="w-4 h-4 mr-2" />
                Search Cards
              </Link>
            </Button>
            <Button asChild className="gradient-arcane text-white">
              <Link href="/">
                <Home className="w-4 h-4 mr-2" />
                Go Home
              </Link>
            </Button>
          </div>

          {/* Help Link */}
          <p className="mt-6 text-sm text-muted-foreground">
            Need help?{' '}
            <Link href="/help" className="text-[rgb(var(--accent))] hover:underline">
              Check our FAQ
            </Link>
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
