'use client';

import Link from 'next/link';
import { motion } from 'framer-motion';
import { Sparkles, ArrowRight, Zap } from 'lucide-react';
import { Button } from '@/components/ui/button';

export function FinalCTA() {
  return (
    <section className="relative py-24 overflow-hidden">
      {/* Background effects */}
      <div className="absolute inset-0 pointer-events-none">
        <div className="absolute inset-0 bg-gradient-to-t from-[rgb(var(--accent))]/10 via-transparent to-transparent" />
        <div className="absolute bottom-0 left-1/2 -translate-x-1/2 w-[800px] h-[400px] bg-[rgb(var(--accent))]/20 rounded-full blur-3xl" />
        <div className="absolute bottom-1/4 left-1/4 w-[300px] h-[300px] bg-[rgb(var(--magic-gold))]/10 rounded-full blur-3xl" />
        <div className="absolute bottom-1/4 right-1/4 w-[300px] h-[300px] bg-[rgb(var(--success))]/10 rounded-full blur-3xl" />
      </div>

      <div className="relative z-10 max-w-4xl mx-auto px-6 text-center">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: '-100px' }}
          transition={{ duration: 0.6 }}
        >
          {/* Badge */}
          <span className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-[rgb(var(--accent))]/10 border border-[rgb(var(--accent))]/20 text-sm text-[rgb(var(--accent))] mb-6">
            <Zap className="w-4 h-4" />
            Free Forever for Collectors
          </span>

          {/* Headline */}
          <h2 className="font-display text-3xl sm:text-4xl md:text-5xl lg:text-6xl font-bold text-foreground mb-6">
            Ready to Get Your
            <span className="block mt-2">
              <span className="foil-shimmer">Edge in the Market?</span>
            </span>
          </h2>

          {/* Subhead */}
          <p className="text-lg md:text-xl text-muted-foreground mb-10 max-w-2xl mx-auto">
            Join collectors and stores already using Dualcaster Deals to track prices,
            find trades, and make smarter decisions.
          </p>

          {/* CTA Buttons */}
          <div className="flex flex-col sm:flex-row items-center justify-center gap-4 mb-12">
            <Link href="/register">
              <Button
                size="lg"
                className="gradient-arcane text-white glow-accent hover-lift press-effect text-lg px-10 py-6 h-auto"
              >
                <Sparkles className="w-5 h-5 mr-2" />
                Create Free Account
                <ArrowRight className="w-5 h-5 ml-2" />
              </Button>
            </Link>
            <Link href="/cards">
              <Button
                size="lg"
                variant="outline"
                className="hover-lift press-effect text-lg px-8 py-6 h-auto backdrop-blur-sm"
              >
                Explore Cards First
              </Button>
            </Link>
          </div>

          {/* Trust points */}
          <div className="flex flex-wrap items-center justify-center gap-x-8 gap-y-3 text-sm text-muted-foreground">
            <span className="flex items-center gap-2">
              <span className="w-1.5 h-1.5 rounded-full bg-[rgb(var(--success))]" />
              No credit card required
            </span>
            <span className="flex items-center gap-2">
              <span className="w-1.5 h-1.5 rounded-full bg-[rgb(var(--success))]" />
              90K+ cards tracked
            </span>
            <span className="flex items-center gap-2">
              <span className="w-1.5 h-1.5 rounded-full bg-[rgb(var(--success))]" />
              Real-time price data
            </span>
          </div>
        </motion.div>
      </div>
    </section>
  );
}
