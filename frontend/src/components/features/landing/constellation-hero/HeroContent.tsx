'use client';

import Link from 'next/link';
import Image from 'next/image';
import { motion } from 'framer-motion';
import { Button } from '@/components/ui/button';
import { Search, Sparkles, TrendingUp, Shield } from 'lucide-react';

export function HeroContent() {
  return (
    <div className="relative z-20 max-w-4xl mx-auto px-6 text-center">
      {/* Logo */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, delay: 0.2 }}
        className="mb-6"
      >
        <Image
          src="/logo.png"
          alt="Dualcaster Deals"
          width={120}
          height={120}
          className="mx-auto rounded-2xl shadow-2xl shadow-[rgb(var(--accent))]/20"
          priority
        />
      </motion.div>

      {/* Badge */}
      <motion.div
        initial={{ opacity: 0, scale: 0.9 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.5, delay: 0.4 }}
        className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-[rgb(var(--accent))]/10 border border-[rgb(var(--accent))]/20 text-sm text-[rgb(var(--accent))] mb-6"
      >
        <Sparkles className="w-4 h-4" />
        <span>AI-Powered Market Intelligence</span>
      </motion.div>

      {/* Main heading */}
      <motion.h1
        className="font-display text-4xl sm:text-5xl md:text-6xl lg:text-7xl font-bold tracking-wide mb-6"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.8, delay: 0.5 }}
      >
        <motion.span
          className="block"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.6 }}
        >
          The Market is
        </motion.span>
        <motion.span
          className="block"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.75 }}
        >
          <span className="foil-shimmer">Always Moving</span>
        </motion.span>
        <motion.span
          className="block text-[rgb(var(--muted-foreground))]"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.9 }}
        >
          Are You Watching?
        </motion.span>
      </motion.h1>

      {/* Subheading */}
      <motion.p
        className="text-lg md:text-xl text-muted-foreground mb-8 max-w-2xl mx-auto"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, delay: 1.0 }}
      >
        Track prices across 5+ marketplaces. Get AI-powered buy and sell signals.
        Know exactly when to make your move.
      </motion.p>

      {/* Search bar */}
      <motion.div
        className="max-w-xl mx-auto mb-8"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, delay: 1.1 }}
      >
        <Link href="/cards">
          <div className="group flex items-center gap-3 px-5 py-4 rounded-xl border border-border bg-card/50 hover:border-[rgb(var(--accent))]/50 hover:bg-card transition-all cursor-pointer glow-accent backdrop-blur-sm">
            <Search className="w-5 h-5 text-muted-foreground group-hover:text-[rgb(var(--accent))] transition-colors" />
            <span className="text-muted-foreground">Search 90,000+ cards...</span>
            <kbd className="hidden sm:inline-flex ml-auto px-2 py-1 rounded bg-secondary text-xs text-muted-foreground">
              /
            </kbd>
          </div>
        </Link>
      </motion.div>

      {/* Feature pills */}
      <motion.div
        className="flex flex-wrap justify-center gap-3 mb-8"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, delay: 1.2 }}
      >
        <div className="flex items-center gap-2 px-4 py-2 rounded-full bg-secondary/50 backdrop-blur-sm text-sm text-muted-foreground border border-border/50">
          <TrendingUp className="w-4 h-4 text-[rgb(var(--success))]" />
          <span>Live Prices</span>
        </div>
        <div className="flex items-center gap-2 px-4 py-2 rounded-full bg-secondary/50 backdrop-blur-sm text-sm text-muted-foreground border border-border/50">
          <Sparkles className="w-4 h-4 text-[rgb(var(--magic-gold))]" />
          <span>AI Recommendations</span>
        </div>
        <div className="flex items-center gap-2 px-4 py-2 rounded-full bg-secondary/50 backdrop-blur-sm text-sm text-muted-foreground border border-border/50">
          <Shield className="w-4 h-4 text-[rgb(var(--accent))]" />
          <span>Portfolio Tracking</span>
        </div>
      </motion.div>

      {/* CTA buttons */}
      <motion.div
        className="flex flex-wrap justify-center gap-4"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, delay: 1.3 }}
      >
        <Button
          size="lg"
          asChild
          className="gradient-arcane text-white glow-accent hover-lift press-effect text-base px-8"
        >
          <Link href="/register">
            Get Started Free
          </Link>
        </Button>
        <Button
          size="lg"
          variant="outline"
          asChild
          className="hover-lift press-effect text-base px-8 backdrop-blur-sm"
        >
          <Link href="/market">
            View Market Data
          </Link>
        </Button>
      </motion.div>

      {/* Trust indicators */}
      <motion.div
        className="mt-12 pt-8 border-t border-border/30"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.6, delay: 1.5 }}
      >
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
      </motion.div>
    </div>
  );
}
