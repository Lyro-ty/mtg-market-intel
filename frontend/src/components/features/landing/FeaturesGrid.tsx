'use client';

import { motion } from 'framer-motion';
import {
  Eye,
  Sparkles,
  MapPin,
  Shield,
  TrendingUp,
  Bell,
  Users,
  BarChart3,
  Zap,
  Search,
  Store,
  BadgeCheck,
} from 'lucide-react';

interface Feature {
  icon: React.ReactNode;
  title: string;
  description: string;
  highlights: string[];
  accentColor: string;
}

const features: Feature[] = [
  {
    icon: <Eye className="w-8 h-8" />,
    title: 'Market Scrying',
    description:
      'Real-time price intelligence across major marketplaces. Track trends, spot opportunities, and never overpay again.',
    highlights: [
      'Live prices from TCGPlayer, CardKingdom & more',
      'Historical price charts & trend analysis',
      'Price alerts when cards hit your target',
    ],
    accentColor: 'rgb(var(--success))',
  },
  {
    icon: <Sparkles className="w-8 h-8" />,
    title: 'Trade Conjuring',
    description:
      'Automatic matching finds collectors who want what you have — and have what you want. Magic happens when inventories align.',
    highlights: [
      'Smart matching across want lists & collections',
      'See potential trade value instantly',
      'Connect directly with matched traders',
    ],
    accentColor: 'rgb(var(--magic-gold))',
  },
  {
    icon: <MapPin className="w-8 h-8" />,
    title: 'Trading Posts',
    description:
      'Discover local game stores with competitive buylist prices. Get instant trade-in estimates before you walk in the door.',
    highlights: [
      'Find stores by location & services',
      'Compare buylist margins across shops',
      'Submit trade quotes, get real offers',
    ],
    accentColor: 'rgb(var(--accent))',
  },
  {
    icon: <Shield className="w-8 h-8" />,
    title: 'Trusted Network',
    description:
      'Build your reputation as a reliable trader. Endorsements from the community help you trade with confidence.',
    highlights: [
      'Reputation scores & trade history',
      'Verified store badges',
      'Community endorsements & reviews',
    ],
    accentColor: 'rgb(var(--accent))',
  },
];

const secondaryFeatures = [
  {
    icon: <TrendingUp className="w-5 h-5" />,
    title: 'Portfolio Tracking',
    description: 'Watch your collection value grow over time',
  },
  {
    icon: <Bell className="w-5 h-5" />,
    title: 'Price Alerts',
    description: 'Get notified when cards hit your target price',
  },
  {
    icon: <BarChart3 className="w-5 h-5" />,
    title: 'Market Analytics',
    description: 'Insights on meta shifts and price movements',
  },
  {
    icon: <Search className="w-5 h-5" />,
    title: 'Advanced Search',
    description: 'Find any card across 90K+ in the vault',
  },
  {
    icon: <Zap className="w-5 h-5" />,
    title: 'Instant Estimates',
    description: 'Know your collection value in seconds',
  },
  {
    icon: <Users className="w-5 h-5" />,
    title: 'Collector Network',
    description: 'Connect with traders who share your interests',
  },
];

const containerVariants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: {
      staggerChildren: 0.1,
    },
  },
};

const itemVariants = {
  hidden: { opacity: 0, y: 20 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.5 },
  },
};

function FeatureCard({ feature, index }: { feature: Feature; index: number }) {
  return (
    <motion.div
      variants={itemVariants}
      className="group relative p-6 rounded-2xl bg-card/50 border border-border/50 backdrop-blur-sm hover:border-[rgb(var(--accent))]/30 hover:bg-card/80 transition-all duration-300"
    >
      {/* Glow effect on hover */}
      <div
        className="absolute inset-0 rounded-2xl opacity-0 group-hover:opacity-100 transition-opacity duration-300 pointer-events-none"
        style={{
          background: `radial-gradient(circle at 50% 0%, ${feature.accentColor}10 0%, transparent 70%)`,
        }}
      />

      {/* Icon */}
      <div
        className="inline-flex p-3 rounded-xl mb-4 transition-transform duration-300 group-hover:scale-110"
        style={{
          backgroundColor: `${feature.accentColor}15`,
          color: feature.accentColor,
        }}
      >
        {feature.icon}
      </div>

      {/* Title */}
      <h3 className="font-heading text-xl font-semibold text-foreground mb-2">
        {feature.title}
      </h3>

      {/* Description */}
      <p className="text-muted-foreground mb-4 leading-relaxed">
        {feature.description}
      </p>

      {/* Highlights */}
      <ul className="space-y-2">
        {feature.highlights.map((highlight, i) => (
          <li key={i} className="flex items-start gap-2 text-sm">
            <BadgeCheck
              className="w-4 h-4 mt-0.5 flex-shrink-0"
              style={{ color: feature.accentColor }}
            />
            <span className="text-muted-foreground">{highlight}</span>
          </li>
        ))}
      </ul>
    </motion.div>
  );
}

function SecondaryFeature({
  feature,
}: {
  feature: (typeof secondaryFeatures)[0];
}) {
  return (
    <motion.div
      variants={itemVariants}
      className="flex items-start gap-3 p-4 rounded-xl bg-secondary/30 border border-border/30 hover:bg-secondary/50 hover:border-border/50 transition-all"
    >
      <div className="p-2 rounded-lg bg-[rgb(var(--accent))]/10 text-[rgb(var(--accent))]">
        {feature.icon}
      </div>
      <div>
        <h4 className="font-medium text-foreground text-sm">{feature.title}</h4>
        <p className="text-xs text-muted-foreground mt-0.5">
          {feature.description}
        </p>
      </div>
    </motion.div>
  );
}

export function FeaturesGrid() {
  return (
    <section className="relative py-24 overflow-hidden">
      {/* Background decoration */}
      <div className="absolute inset-0 pointer-events-none">
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[800px] bg-[rgb(var(--accent))]/5 rounded-full blur-3xl" />
      </div>

      <div className="relative z-10 max-w-7xl mx-auto px-6">
        {/* Section header */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: '-100px' }}
          transition={{ duration: 0.6 }}
          className="text-center mb-16"
        >
          <span className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-[rgb(var(--accent))]/10 border border-[rgb(var(--accent))]/20 text-sm text-[rgb(var(--accent))] mb-4">
            <Zap className="w-4 h-4" />
            Powerful Tools
          </span>
          <h2 className="font-display text-3xl sm:text-4xl md:text-5xl font-bold text-foreground mb-4">
            Everything You Need to
            <span className="block mt-2">
              <span className="foil-shimmer">Trade Smarter</span>
            </span>
          </h2>
          <p className="text-lg text-muted-foreground max-w-2xl mx-auto">
            From real-time market data to local store discovery, we give you the
            tools to make informed decisions and find the best deals.
          </p>
        </motion.div>

        {/* Main features grid */}
        <motion.div
          variants={containerVariants}
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, margin: '-50px' }}
          className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-16"
        >
          {features.map((feature, index) => (
            <FeatureCard key={feature.title} feature={feature} index={index} />
          ))}
        </motion.div>

        {/* Secondary features */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: '-50px' }}
          transition={{ duration: 0.6, delay: 0.2 }}
          className="text-center mb-8"
        >
          <h3 className="font-heading text-xl font-semibold text-foreground">
            And Much More
          </h3>
        </motion.div>

        <motion.div
          variants={containerVariants}
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, margin: '-50px' }}
          className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4"
        >
          {secondaryFeatures.map((feature) => (
            <SecondaryFeature key={feature.title} feature={feature} />
          ))}
        </motion.div>
      </div>
    </section>
  );
}
