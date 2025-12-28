'use client';

import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { Search } from 'lucide-react';

export function Hero() {
  return (
    <section className="relative py-20 md:py-32">
      {/* Background gradient */}
      <div className="absolute inset-0 bg-gradient-to-b from-[rgb(var(--accent))]/5 via-transparent to-transparent" />

      <div className="relative max-w-4xl mx-auto px-6 text-center">
        <h1 className="font-display text-4xl md:text-6xl font-bold tracking-wide mb-6">
          Make Smarter{' '}
          <span className="text-[rgb(var(--accent))]">MTG Market</span>{' '}
          Decisions
        </h1>

        <p className="text-xl text-muted-foreground mb-8 max-w-2xl mx-auto">
          Accurate pricing data. Real-time alerts. Know exactly when to buy, sell, or hold.
        </p>

        {/* Search bar */}
        <div className="max-w-xl mx-auto mb-8">
          <Link href="/cards">
            <div className="flex items-center gap-3 px-4 py-3 rounded-lg border border-border bg-card hover:border-[rgb(var(--accent))]/50 transition-colors cursor-pointer">
              <Search className="w-5 h-5 text-muted-foreground" />
              <span className="text-muted-foreground">Search any card...</span>
            </div>
          </Link>
        </div>

        {/* Stats */}
        <div className="flex flex-wrap justify-center gap-8 text-sm text-muted-foreground mb-8">
          <span>90,000+ cards tracked</span>
          <span>Live prices</span>
          <span>Tournament meta</span>
        </div>

        {/* CTA */}
        <div className="flex flex-wrap justify-center gap-4">
          <Button size="lg" asChild>
            <Link href="/register">Get Started Free</Link>
          </Button>
          <Button size="lg" variant="outline" asChild>
            <Link href="/market">View Market</Link>
          </Button>
        </div>
      </div>
    </section>
  );
}
