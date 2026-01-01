'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import Image from 'next/image';
import { motion } from 'framer-motion';
import {
  TrendingUp,
  TrendingDown,
  BarChart3,
  Activity,
  Database,
  Layers,
  ArrowRight,
  RefreshCw,
  Sparkles,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { getMarketOverview, searchCards } from '@/lib/api';
import type { MarketOverview } from '@/types';

interface FeaturedCard {
  id: number;
  name: string;
  set_code: string;
  set_name: string;
  rarity: string;
  image_url: string | null;
  image_url_small: string | null;
  price_usd?: number;
  price_change_pct?: number;
}

// Featured cards to showcase (iconic/popular)
const FEATURED_SEARCHES = [
  'Force of Will',
  'Ragavan',
  'The One Ring',
  'Sheoldred',
  'Orcish Bowmasters',
  'Atraxa',
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

function StatCard({
  icon: Icon,
  label,
  value,
  subValue,
  color,
}: {
  icon: typeof TrendingUp;
  label: string;
  value: string;
  subValue?: string;
  color: string;
}) {
  return (
    <motion.div variants={itemVariants}>
      <Card className="bg-card/50 border-border/50 backdrop-blur-sm hover:border-[rgb(var(--accent))]/30 transition-colors">
        <CardContent className="p-4">
          <div className="flex items-start gap-3">
            <div
              className="p-2 rounded-lg"
              style={{ backgroundColor: `${color}15`, color }}
            >
              <Icon className="w-5 h-5" />
            </div>
            <div>
              <p className="text-2xl font-bold text-foreground">{value}</p>
              <p className="text-sm text-muted-foreground">{label}</p>
              {subValue && (
                <p className="text-xs text-muted-foreground/70 mt-0.5">
                  {subValue}
                </p>
              )}
            </div>
          </div>
        </CardContent>
      </Card>
    </motion.div>
  );
}

function CardPreview({ card }: { card: FeaturedCard }) {
  const imageUrl = card.image_url_small || card.image_url;

  return (
    <motion.div
      variants={itemVariants}
      whileHover={{ y: -4, scale: 1.02 }}
      transition={{ duration: 0.2 }}
    >
      <Link href={`/cards/${card.id}`}>
        <Card className="group overflow-hidden bg-card/50 border-border/50 backdrop-blur-sm hover:border-[rgb(var(--accent))]/50 transition-all cursor-pointer">
          <div className="aspect-[488/680] relative bg-secondary/50">
            {imageUrl ? (
              <Image
                src={imageUrl}
                alt={card.name}
                fill
                className="object-cover transition-transform group-hover:scale-105"
                sizes="(max-width: 768px) 50vw, 200px"
              />
            ) : (
              <div className="w-full h-full flex items-center justify-center">
                <Sparkles className="w-8 h-8 text-muted-foreground/30" />
              </div>
            )}
            {/* Rarity indicator */}
            <div className="absolute top-2 right-2">
              <Badge
                variant="secondary"
                className={`text-xs capitalize ${
                  card.rarity === 'mythic'
                    ? 'bg-orange-500/80 text-white'
                    : card.rarity === 'rare'
                      ? 'bg-yellow-500/80 text-black'
                      : ''
                }`}
              >
                {card.rarity}
              </Badge>
            </div>
          </div>
          <CardContent className="p-3">
            <p className="font-medium text-sm text-foreground truncate group-hover:text-[rgb(var(--accent))] transition-colors">
              {card.name}
            </p>
            <p className="text-xs text-muted-foreground truncate">
              {card.set_name}
            </p>
          </CardContent>
        </Card>
      </Link>
    </motion.div>
  );
}

export function LiveMarketPreview() {
  const [overview, setOverview] = useState<MarketOverview | null>(null);
  const [featuredCards, setFeaturedCards] = useState<FeaturedCard[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  useEffect(() => {
    async function fetchData() {
      setIsLoading(true);
      try {
        // Fetch market overview
        const overviewData = await getMarketOverview();
        setOverview(overviewData);

        // Fetch featured cards
        const cards: FeaturedCard[] = [];
        for (const query of FEATURED_SEARCHES.slice(0, 6)) {
          try {
            const result = await searchCards(query, { pageSize: 1 });
            if (result.cards && result.cards.length > 0) {
              cards.push(result.cards[0] as FeaturedCard);
            }
          } catch {
            // Skip failed searches
          }
        }
        setFeaturedCards(cards);
        setLastUpdated(new Date());
      } catch (error) {
        console.error('Failed to fetch market data:', error);
      } finally {
        setIsLoading(false);
      }
    }

    fetchData();
  }, []);

  const formatNumber = (num: number) => {
    if (num >= 1000000) {
      return `${(num / 1000000).toFixed(1)}M`;
    }
    if (num >= 1000) {
      return `${(num / 1000).toFixed(0)}K`;
    }
    return num.toLocaleString();
  };

  const formatCurrency = (num: number) => {
    if (num >= 1000000) {
      return `$${(num / 1000000).toFixed(1)}M`;
    }
    if (num >= 1000) {
      return `$${(num / 1000).toFixed(0)}K`;
    }
    return `$${num.toLocaleString()}`;
  };

  return (
    <section className="relative py-24 overflow-hidden bg-gradient-to-b from-transparent via-secondary/20 to-transparent">
      {/* Background decoration */}
      <div className="absolute inset-0 pointer-events-none">
        <div className="absolute top-0 left-1/4 w-[500px] h-[500px] bg-[rgb(var(--success))]/5 rounded-full blur-3xl" />
        <div className="absolute bottom-0 right-1/4 w-[400px] h-[400px] bg-[rgb(var(--accent))]/5 rounded-full blur-3xl" />
      </div>

      <div className="relative z-10 max-w-7xl mx-auto px-6">
        {/* Section header */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: '-100px' }}
          transition={{ duration: 0.6 }}
          className="text-center mb-12"
        >
          <span className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-[rgb(var(--success))]/10 border border-[rgb(var(--success))]/20 text-sm text-[rgb(var(--success))] mb-4">
            <Activity className="w-4 h-4" />
            Live Data
          </span>
          <h2 className="font-display text-3xl sm:text-4xl md:text-5xl font-bold text-foreground mb-4">
            The Market at a Glance
          </h2>
          <p className="text-lg text-muted-foreground max-w-2xl mx-auto">
            Real-time intelligence from across the MTG marketplace ecosystem
          </p>
          {lastUpdated && (
            <p className="text-xs text-muted-foreground/60 mt-2 flex items-center justify-center gap-1">
              <RefreshCw className="w-3 h-3" />
              Updated {lastUpdated.toLocaleTimeString()}
            </p>
          )}
        </motion.div>

        {/* Stats grid */}
        <motion.div
          variants={containerVariants}
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, margin: '-50px' }}
          className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-12"
        >
          <StatCard
            icon={Database}
            label="Cards Tracked"
            value={overview ? formatNumber(overview.totalCardsTracked) : '—'}
            subValue="Across all sets"
            color="rgb(var(--accent))"
          />
          <StatCard
            icon={BarChart3}
            label="Active Listings"
            value={
              overview?.totalListings
                ? formatNumber(overview.totalListings)
                : '1.3M+'
            }
            subValue="Price data points"
            color="rgb(var(--success))"
          />
          <StatCard
            icon={Activity}
            label="24h Volume"
            value={overview ? formatCurrency(overview.volume24hUsd) : '—'}
            subValue="Market activity"
            color="rgb(var(--magic-gold))"
          />
          <StatCard
            icon={Layers}
            label="Formats Tracked"
            value={overview ? String(overview.activeFormatsTracked) : '—'}
            subValue="Standard, Modern, Legacy..."
            color="rgb(var(--accent))"
          />
        </motion.div>

        {/* Featured cards */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: '-50px' }}
          transition={{ duration: 0.6, delay: 0.2 }}
          className="mb-8"
        >
          <div className="flex items-center justify-between mb-6">
            <h3 className="font-heading text-xl font-semibold text-foreground">
              Popular Cards in the Vault
            </h3>
            <Link href="/cards">
              <Button variant="ghost" size="sm" className="text-muted-foreground hover:text-foreground">
                Browse All
                <ArrowRight className="w-4 h-4 ml-1" />
              </Button>
            </Link>
          </div>

          {isLoading ? (
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4">
              {[...Array(6)].map((_, i) => (
                <div
                  key={i}
                  className="aspect-[488/680] rounded-lg bg-secondary/50 animate-pulse"
                />
              ))}
            </div>
          ) : featuredCards.length > 0 ? (
            <motion.div
              variants={containerVariants}
              initial="hidden"
              whileInView="visible"
              viewport={{ once: true }}
              className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4"
            >
              {featuredCards.map((card) => (
                <CardPreview key={card.id} card={card} />
              ))}
            </motion.div>
          ) : (
            <div className="text-center py-12 text-muted-foreground">
              <Sparkles className="w-8 h-8 mx-auto mb-2 opacity-50" />
              <p>Loading featured cards...</p>
            </div>
          )}
        </motion.div>

        {/* CTA */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: '-50px' }}
          transition={{ duration: 0.6, delay: 0.3 }}
          className="text-center"
        >
          <Link href="/market">
            <Button
              size="lg"
              className="gradient-arcane text-white glow-accent hover-lift press-effect"
            >
              <BarChart3 className="w-5 h-5 mr-2" />
              Explore Full Market Dashboard
            </Button>
          </Link>
        </motion.div>
      </div>
    </section>
  );
}
