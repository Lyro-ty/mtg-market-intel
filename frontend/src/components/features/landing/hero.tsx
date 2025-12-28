'use client';

import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { Search, Sparkles, TrendingUp, Shield } from 'lucide-react';

export function Hero() {
  return (
    <section className="relative py-20 md:py-32 overflow-hidden">
      {/* Animated background elements */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        {/* Gradient orbs */}
        <div className="absolute top-1/4 -left-20 w-72 h-72 bg-[rgb(var(--magic-purple))] rounded-full blur-[120px] opacity-20 animate-pulse" />
        <div className="absolute top-1/3 -right-20 w-96 h-96 bg-[rgb(var(--magic-green))] rounded-full blur-[150px] opacity-15 animate-pulse" style={{ animationDelay: '1s' }} />
        <div className="absolute bottom-1/4 left-1/3 w-64 h-64 bg-[rgb(var(--magic-gold))] rounded-full blur-[100px] opacity-10 animate-pulse" style={{ animationDelay: '2s' }} />

        {/* Grid pattern */}
        <div
          className="absolute inset-0 opacity-[0.02]"
          style={{
            backgroundImage: `linear-gradient(rgb(var(--foreground)) 1px, transparent 1px),
                              linear-gradient(90deg, rgb(var(--foreground)) 1px, transparent 1px)`,
            backgroundSize: '50px 50px'
          }}
        />
      </div>

      {/* Top gradient fade */}
      <div className="absolute inset-x-0 top-0 h-32 bg-gradient-to-b from-background to-transparent" />

      {/* Bottom gradient fade */}
      <div className="absolute inset-x-0 bottom-0 h-32 bg-gradient-to-t from-background to-transparent" />

      <div className="relative max-w-5xl mx-auto px-6 text-center">
        {/* Badge */}
        <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-[rgb(var(--accent))]/10 border border-[rgb(var(--accent))]/20 text-sm text-[rgb(var(--accent))] mb-8 animate-fade-in">
          <Sparkles className="w-4 h-4" />
          <span>AI-Powered Market Intelligence</span>
        </div>

        {/* Main heading with staggered animation */}
        <h1 className="font-display text-4xl sm:text-5xl md:text-6xl lg:text-7xl font-bold tracking-wide mb-6">
          <span className="block animate-slide-in-bottom" style={{ animationDelay: '0.1s' }}>
            Make Smarter
          </span>
          <span className="block animate-slide-in-bottom" style={{ animationDelay: '0.2s' }}>
            <span className="foil-shimmer">MTG Market</span>
          </span>
          <span className="block animate-slide-in-bottom" style={{ animationDelay: '0.3s' }}>
            Decisions
          </span>
        </h1>

        <p className="text-lg md:text-xl text-muted-foreground mb-10 max-w-2xl mx-auto animate-fade-in" style={{ animationDelay: '0.4s' }}>
          Track prices across marketplaces. Get AI-powered buy and sell signals.
          Know exactly when to make your move.
        </p>

        {/* Search bar with glow */}
        <div className="max-w-xl mx-auto mb-10 animate-fade-in" style={{ animationDelay: '0.5s' }}>
          <Link href="/cards">
            <div className="group flex items-center gap-3 px-5 py-4 rounded-xl border border-border bg-card/50 hover:border-[rgb(var(--accent))]/50 hover:bg-card transition-all cursor-pointer glow-accent">
              <Search className="w-5 h-5 text-muted-foreground group-hover:text-[rgb(var(--accent))] transition-colors" />
              <span className="text-muted-foreground">Search 90,000+ cards...</span>
              <kbd className="hidden sm:inline-flex ml-auto px-2 py-1 rounded bg-secondary text-xs text-muted-foreground">
                ⌘K
              </kbd>
            </div>
          </Link>
        </div>

        {/* Feature pills */}
        <div className="flex flex-wrap justify-center gap-3 mb-10 animate-fade-in" style={{ animationDelay: '0.6s' }}>
          <div className="flex items-center gap-2 px-4 py-2 rounded-full bg-secondary/50 text-sm text-muted-foreground">
            <TrendingUp className="w-4 h-4 text-[rgb(var(--success))]" />
            <span>Live Prices</span>
          </div>
          <div className="flex items-center gap-2 px-4 py-2 rounded-full bg-secondary/50 text-sm text-muted-foreground">
            <Sparkles className="w-4 h-4 text-[rgb(var(--magic-gold))]" />
            <span>AI Recommendations</span>
          </div>
          <div className="flex items-center gap-2 px-4 py-2 rounded-full bg-secondary/50 text-sm text-muted-foreground">
            <Shield className="w-4 h-4 text-[rgb(var(--accent))]" />
            <span>Portfolio Tracking</span>
          </div>
        </div>

        {/* CTA buttons */}
        <div className="flex flex-wrap justify-center gap-4 animate-fade-in" style={{ animationDelay: '0.7s' }}>
          <Button size="lg" asChild className="gradient-arcane text-white glow-accent hover-lift press-effect text-base px-8">
            <Link href="/register">
              Get Started Free
            </Link>
          </Button>
          <Button size="lg" variant="outline" asChild className="hover-lift press-effect text-base px-8">
            <Link href="/market">
              View Market Data
            </Link>
          </Button>
        </div>

        {/* Trust indicators */}
        <div className="mt-12 pt-8 border-t border-border/50 animate-fade-in" style={{ animationDelay: '0.8s' }}>
          <p className="text-sm text-muted-foreground mb-4">Trusted by collectors worldwide</p>
          <div className="flex flex-wrap justify-center gap-8 text-muted-foreground/60">
            <div className="text-center">
              <p className="text-2xl font-bold text-foreground">90K+</p>
              <p className="text-xs">Cards Tracked</p>
            </div>
            <div className="text-center">
              <p className="text-2xl font-bold text-foreground">30min</p>
              <p className="text-xs">Price Updates</p>
            </div>
            <div className="text-center">
              <p className="text-2xl font-bold text-foreground">5+</p>
              <p className="text-xs">Marketplaces</p>
            </div>
            <div className="text-center">
              <p className="text-2xl font-bold text-foreground">Free</p>
              <p className="text-xs">Forever</p>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
