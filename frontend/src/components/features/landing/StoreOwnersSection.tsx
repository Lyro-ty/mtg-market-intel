'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { motion } from 'framer-motion';
import {
  Store,
  Users,
  TrendingUp,
  FileText,
  Calendar,
  BadgeCheck,
  ArrowRight,
  Zap,
  DollarSign,
  MapPin,
  Bell,
  BarChart3,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { getSiteStats } from '@/lib/api';

interface Benefit {
  icon: React.ReactNode;
  title: string;
  description: string;
}

const benefits: Benefit[] = [
  {
    icon: <FileText className="w-6 h-6" />,
    title: 'Receive Trade-In Quotes',
    description:
      'Collectors build quotes and submit them directly to your store. Review, accept, or counter — all in one dashboard.',
  },
  {
    icon: <Users className="w-6 h-6" />,
    title: 'Find Local Customers',
    description:
      'Get discovered by collectors in your area searching for stores with competitive buylist prices.',
  },
  {
    icon: <Calendar className="w-6 h-6" />,
    title: 'Promote Your Events',
    description:
      'List tournaments, prereleases, and Commander nights. Attract players looking for places to play.',
  },
  {
    icon: <TrendingUp className="w-6 h-6" />,
    title: 'Market Intelligence',
    description:
      'Access the same price data your customers see. Make informed buylist decisions with real-time market insights.',
  },
  {
    icon: <BadgeCheck className="w-6 h-6" />,
    title: 'Build Trust',
    description:
      'Verified store badge and customer reviews help establish credibility with new customers.',
  },
  {
    icon: <Bell className="w-6 h-6" />,
    title: 'Instant Notifications',
    description:
      'Get notified when collectors submit quotes or when high-value trade opportunities arise.',
  },
];

const stats = [
  { value: 'Free', label: 'To Get Started' },
  { value: '0%', label: 'Transaction Fees' },
  { value: '5 min', label: 'Setup Time' },
];

const containerVariants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: { staggerChildren: 0.1 },
  },
};

const itemVariants = {
  hidden: { opacity: 0, y: 20 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.5 } },
};

function BenefitCard({ benefit }: { benefit: Benefit }) {
  return (
    <motion.div variants={itemVariants}>
      <Card className="h-full bg-card/50 border-border/50 backdrop-blur-sm hover:border-[rgb(var(--magic-gold))]/30 hover:bg-card/80 transition-all group">
        <CardContent className="p-5">
          <div className="p-2.5 rounded-xl bg-[rgb(var(--magic-gold))]/10 text-[rgb(var(--magic-gold))] w-fit mb-4 group-hover:scale-110 transition-transform">
            {benefit.icon}
          </div>
          <h3 className="font-heading text-lg font-semibold text-foreground mb-2">
            {benefit.title}
          </h3>
          <p className="text-sm text-muted-foreground leading-relaxed">
            {benefit.description}
          </p>
        </CardContent>
      </Card>
    </motion.div>
  );
}

export function StoreOwnersSection() {
  const [tradingPostCount, setTradingPostCount] = useState<number | null>(null);

  useEffect(() => {
    getSiteStats()
      .then((stats) => setTradingPostCount(stats.trading_posts))
      .catch(() => {});
  }, []);

  return (
    <section className="relative py-24 overflow-hidden">
      {/* Background with gradient */}
      <div className="absolute inset-0 bg-gradient-to-b from-transparent via-[rgb(var(--magic-gold))]/5 to-transparent pointer-events-none" />
      <div className="absolute inset-0 pointer-events-none">
        <div className="absolute top-1/3 right-0 w-[600px] h-[600px] bg-[rgb(var(--magic-gold))]/5 rounded-full blur-3xl" />
        <div className="absolute bottom-1/3 left-0 w-[400px] h-[400px] bg-[rgb(var(--accent))]/5 rounded-full blur-3xl" />
      </div>

      <div className="relative z-10 max-w-7xl mx-auto px-6">
        <div className="grid lg:grid-cols-2 gap-12 items-center">
          {/* Left column - Main pitch */}
          <motion.div
            initial={{ opacity: 0, x: -20 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true, margin: '-100px' }}
            transition={{ duration: 0.6 }}
          >
            <span className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-[rgb(var(--magic-gold))]/10 border border-[rgb(var(--magic-gold))]/20 text-sm text-[rgb(var(--magic-gold))] mb-6">
              <Store className="w-4 h-4" />
              For Store Owners
            </span>

            <h2 className="font-display text-3xl sm:text-4xl md:text-5xl font-bold text-foreground mb-6">
              Turn Your Shop Into a
              <span className="block mt-2">
                <span className="text-[rgb(var(--magic-gold))]">Trading Post</span>
              </span>
            </h2>

            <p className="text-lg text-muted-foreground mb-8 leading-relaxed">
              Join the network of local game stores connecting with collectors.
              Receive trade-in quotes, promote your events, and grow your
              customer base — all without platform fees.
            </p>

            {/* Quick stats */}
            <div className="grid grid-cols-3 gap-4 mb-8">
              {stats.map((stat) => (
                <div key={stat.label} className="text-center">
                  <p className="text-2xl font-bold text-[rgb(var(--magic-gold))]">
                    {stat.value}
                  </p>
                  <p className="text-xs text-muted-foreground">{stat.label}</p>
                </div>
              ))}
            </div>

            {/* CTA buttons */}
            <div className="flex flex-wrap gap-4">
              <Link href="/store/register">
                <Button
                  size="lg"
                  className="bg-[rgb(var(--magic-gold))] hover:bg-[rgb(var(--magic-gold))]/90 text-black font-semibold glow-gold hover-lift press-effect"
                >
                  <Store className="w-5 h-5 mr-2" />
                  Register Your Store
                </Button>
              </Link>
              <Link href="/stores">
                <Button
                  size="lg"
                  variant="outline"
                  className="border-[rgb(var(--magic-gold))]/30 hover:border-[rgb(var(--magic-gold))]/50 hover:bg-[rgb(var(--magic-gold))]/5"
                >
                  <MapPin className="w-5 h-5 mr-2" />
                  Browse Trading Posts
                </Button>
              </Link>
            </div>

            {/* Social proof */}
            {tradingPostCount !== null && tradingPostCount > 0 && (
              <p className="text-sm text-muted-foreground mt-6">
                Join{' '}
                <span className="text-[rgb(var(--magic-gold))] font-medium">
                  {tradingPostCount} Trading Post{tradingPostCount !== 1 ? 's' : ''}
                </span>{' '}
                already on the platform
              </p>
            )}
          </motion.div>

          {/* Right column - Benefits grid */}
          <motion.div
            variants={containerVariants}
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true, margin: '-50px' }}
            className="grid sm:grid-cols-2 gap-4"
          >
            {benefits.map((benefit) => (
              <BenefitCard key={benefit.title} benefit={benefit} />
            ))}
          </motion.div>
        </div>

        {/* Bottom feature highlight */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: '-50px' }}
          transition={{ duration: 0.6, delay: 0.3 }}
          className="mt-16"
        >
          <Card className="bg-gradient-to-r from-[rgb(var(--magic-gold))]/10 via-card/50 to-[rgb(var(--accent))]/10 border-[rgb(var(--magic-gold))]/20 backdrop-blur-sm">
            <CardContent className="p-8">
              <div className="flex flex-col md:flex-row items-center justify-between gap-6">
                <div className="flex items-center gap-4">
                  <div className="p-4 rounded-2xl bg-[rgb(var(--magic-gold))]/20">
                    <Zap className="w-8 h-8 text-[rgb(var(--magic-gold))]" />
                  </div>
                  <div>
                    <h3 className="font-heading text-xl font-semibold text-foreground mb-1">
                      How It Works
                    </h3>
                    <p className="text-muted-foreground max-w-lg">
                      Collectors build trade quotes with cards from their collection.
                      They see instant estimates based on your buylist margin. When
                      they submit, you review and respond — it's that simple.
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <div className="flex items-center gap-2 px-4 py-2 rounded-lg bg-secondary/50 border border-border/50">
                    <DollarSign className="w-5 h-5 text-[rgb(var(--success))]" />
                    <div className="text-sm">
                      <p className="font-medium text-foreground">You Set the Terms</p>
                      <p className="text-xs text-muted-foreground">
                        Control your buylist margin
                      </p>
                    </div>
                  </div>
                  <ArrowRight className="w-5 h-5 text-muted-foreground hidden md:block" />
                  <div className="flex items-center gap-2 px-4 py-2 rounded-lg bg-secondary/50 border border-border/50">
                    <BarChart3 className="w-5 h-5 text-[rgb(var(--accent))]" />
                    <div className="text-sm">
                      <p className="font-medium text-foreground">Track Everything</p>
                      <p className="text-xs text-muted-foreground">
                        Full submission dashboard
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </motion.div>
      </div>
    </section>
  );
}
