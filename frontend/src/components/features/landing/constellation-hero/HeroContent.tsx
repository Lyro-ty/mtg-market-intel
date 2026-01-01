'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import Image from 'next/image';
import { motion } from 'framer-motion';
import { Button } from '@/components/ui/button';
import { Eye, Sparkles, MapPin, Shield, Swords } from 'lucide-react';
import { getSiteStats, SiteStats } from '@/lib/api';

export function HeroContent() {
  const [stats, setStats] = useState<SiteStats | null>(null);

  useEffect(() => {
    getSiteStats()
      .then(setStats)
      .catch(() => {
        // Fallback to null - we'll show static text
      });
  }, []);

  // Format large numbers (e.g., 98000 -> "98K+")
  const formatCount = (n: number) => {
    if (n >= 1000) {
      return `${Math.floor(n / 1000)}K+`;
    }
    return n.toString();
  };

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
        <Swords className="w-4 h-4" />
        <span>Real-Time Market Intelligence</span>
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
          Your Edge in
        </motion.span>
        <motion.span
          className="block"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.75 }}
        >
          <span className="foil-shimmer">the Market</span>
        </motion.span>
        <motion.span
          className="block text-xl sm:text-2xl md:text-3xl font-normal text-[rgb(var(--muted-foreground))] mt-4"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.9 }}
        >
          Scry Further. Connect Deeper. Deal Smarter.
        </motion.span>
      </motion.h1>

      {/* Subheading */}
      <motion.p
        className="text-lg md:text-xl text-muted-foreground mb-8 max-w-2xl mx-auto"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, delay: 1.0 }}
      >
        Market intelligence meets community. Find collectors and trading posts
        who have what you seek — and seek what you hold.
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
            <Eye className="w-5 h-5 text-muted-foreground group-hover:text-[rgb(var(--accent))] transition-colors" />
            <span className="text-muted-foreground">Scry the vault...</span>
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
          <Eye className="w-4 h-4 text-[rgb(var(--success))]" />
          <span>Market Scrying</span>
        </div>
        <div className="flex items-center gap-2 px-4 py-2 rounded-full bg-secondary/50 backdrop-blur-sm text-sm text-muted-foreground border border-border/50">
          <Sparkles className="w-4 h-4 text-[rgb(var(--magic-gold))]" />
          <span>Trade Conjuring</span>
        </div>
        <div className="flex items-center gap-2 px-4 py-2 rounded-full bg-secondary/50 backdrop-blur-sm text-sm text-muted-foreground border border-border/50">
          <MapPin className="w-4 h-4 text-[rgb(var(--accent))]" />
          <span>Trading Posts</span>
        </div>
        <div className="flex items-center gap-2 px-4 py-2 rounded-full bg-secondary/50 backdrop-blur-sm text-sm text-muted-foreground border border-border/50">
          <Shield className="w-4 h-4 text-[rgb(var(--accent))]" />
          <span>Trusted Network</span>
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
            Enter the Bazaar
          </Link>
        </Button>
        <Button
          size="lg"
          variant="outline"
          asChild
          className="hover-lift press-effect text-base px-8 backdrop-blur-sm"
        >
          <Link href="/cards">
            Begin Your Quest
          </Link>
        </Button>
      </motion.div>

      {/* Trust indicators - Live stats */}
      <motion.div
        className="mt-12 pt-8 border-t border-border/30"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.6, delay: 1.5 }}
      >
        <p className="text-sm text-muted-foreground mb-4">Join the growing community</p>
        <div className="flex flex-wrap justify-center gap-8 text-muted-foreground/60">
          <div className="text-center">
            <p className="text-2xl font-bold text-foreground">
              {stats ? stats.seekers : '—'}
            </p>
            <p className="text-xs">Seekers</p>
          </div>
          <div className="text-center">
            <p className="text-2xl font-bold text-foreground">
              {stats ? stats.trading_posts : '—'}
            </p>
            <p className="text-xs">Trading Posts</p>
          </div>
          <div className="text-center">
            <p className="text-2xl font-bold text-foreground">
              {stats ? formatCount(stats.cards_in_vault) : '—'}
            </p>
            <p className="text-xs">Cards in the Vault</p>
          </div>
          <div className="text-center">
            <p className="text-2xl font-bold text-foreground">Free</p>
            <p className="text-xs">to Join</p>
          </div>
        </div>
      </motion.div>
    </div>
  );
}
