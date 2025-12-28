'use client';

import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { useAuth } from '@/contexts/AuthContext';

export function PublicHeader() {
  const { user } = useAuth();

  return (
    <header className="border-b border-border">
      <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
        <Link href="/" className="flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-[rgb(var(--accent))]">
            <span className="font-display text-sm font-bold text-white">DD</span>
          </div>
          <span className="font-heading text-xl font-semibold">Dualcaster Deals</span>
        </Link>

        <nav className="hidden md:flex items-center gap-6">
          <Link href="/market" className="text-muted-foreground hover:text-foreground transition-colors">
            Market
          </Link>
          <Link href="/cards" className="text-muted-foreground hover:text-foreground transition-colors">
            Cards
          </Link>
          <Link href="/tournaments" className="text-muted-foreground hover:text-foreground transition-colors">
            Tournaments
          </Link>
        </nav>

        <div className="flex items-center gap-2">
          {user ? (
            <Button asChild>
              <Link href="/dashboard">Dashboard</Link>
            </Button>
          ) : (
            <>
              <Button variant="ghost" asChild>
                <Link href="/login">Login</Link>
              </Button>
              <Button asChild>
                <Link href="/register">Get Started</Link>
              </Button>
            </>
          )}
        </div>
      </div>
    </header>
  );
}
