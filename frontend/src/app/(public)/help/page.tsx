'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import {
  HelpCircle,
  ChevronDown,
  ChevronRight,
  Search,
  BookOpen,
  Package,
  TrendingUp,
  Bell,
  Settings,
  CreditCard,
  Shield,
  MessageSquare,
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { PageHeader } from '@/components/ornate/page-header';
import { cn } from '@/lib/utils';

interface FAQItem {
  question: string;
  answer: string;
}

interface FAQCategory {
  id: string;
  title: string;
  icon: React.ElementType;
  items: FAQItem[];
}

const faqCategories: FAQCategory[] = [
  {
    id: 'getting-started',
    title: 'Getting Started',
    icon: BookOpen,
    items: [
      {
        question: 'What is Dualcaster Deals?',
        answer: 'Dualcaster Deals is an MTG market intelligence platform that helps you track card prices, manage your collection, and get AI-powered trading recommendations. We aggregate data from multiple sources to give you comprehensive market insights.',
      },
      {
        question: 'How do I create an account?',
        answer: 'Click the "Sign Up" button in the top navigation. You can register with your email and password, or use Google Sign-In for faster access. Your account is free and gives you access to all features.',
      },
      {
        question: 'Is Dualcaster Deals free to use?',
        answer: 'Yes! Dualcaster Deals is completely free. We believe every collector deserves access to professional-grade market intelligence tools.',
      },
    ],
  },
  {
    id: 'inventory',
    title: 'Inventory Management',
    icon: Package,
    items: [
      {
        question: 'How do I import my collection?',
        answer: 'Go to the Inventory page and click "Import Cards". You can paste a list of cards in various formats (one card per line), or upload a CSV file. We support common formats from Moxfield, Archidekt, and other deck builders.',
      },
      {
        question: 'What formats are supported for import?',
        answer: 'We support plain text (card name per line), CSV files, and formats exported from popular sites like Moxfield and Archidekt. The importer will attempt to match card names and find the best printing.',
      },
      {
        question: 'How do I track acquisition prices?',
        answer: 'When importing cards, you can include acquisition prices in your CSV. For manually added cards, you can edit the item and set the purchase price. This helps track your profit/loss accurately.',
      },
      {
        question: 'Can I track foils separately?',
        answer: 'Yes! Each inventory item can be marked as foil or non-foil. Foil cards are priced separately and displayed with a special shimmer effect in the UI.',
      },
    ],
  },
  {
    id: 'recommendations',
    title: 'Recommendations',
    icon: TrendingUp,
    items: [
      {
        question: 'How are recommendations generated?',
        answer: 'Our AI analyzes market trends, price history, tournament data, and supply signals to generate buy/sell/hold recommendations. Each recommendation includes a confidence score and detailed rationale.',
      },
      {
        question: 'What do the confidence levels mean?',
        answer: 'Confidence reflects how certain our model is about the recommendation. Critical (90%+) means high certainty, High (70-90%) is strong confidence, Medium (50-70%) is moderate, and Low (<50%) suggests more risk.',
      },
      {
        question: 'How often are recommendations updated?',
        answer: 'Recommendations are regenerated every 6 hours for general cards, and every 15 minutes for cards in your inventory using more aggressive thresholds.',
      },
    ],
  },
  {
    id: 'alerts',
    title: 'Price Alerts',
    icon: Bell,
    items: [
      {
        question: 'How do I set up price alerts?',
        answer: 'Add cards to your Want List and set a target price. Enable the alert toggle, and we\'ll notify you when the card reaches your target. Alerts are checked with every price update.',
      },
      {
        question: 'How will I be notified?',
        answer: 'Currently, alerts appear in the Insights page when you log in. Email notifications are coming soon for premium alerts.',
      },
    ],
  },
  {
    id: 'pricing',
    title: 'Pricing Data',
    icon: CreditCard,
    items: [
      {
        question: 'Where does pricing data come from?',
        answer: 'We aggregate pricing from TCGPlayer as our primary source, with additional data from CardTrader and other marketplaces. Prices are updated every 30 minutes.',
      },
      {
        question: 'Why might a price be different from what I see on TCGPlayer?',
        answer: 'Prices can fluctuate between our updates. We show market prices (median of recent sales) which may differ from the lowest listing. Always verify current prices before making purchases.',
      },
      {
        question: 'What is the Market Index?',
        answer: 'The Market Index tracks overall MTG market health by averaging price movements across top cards in each format. It helps you understand if the market is generally rising or falling.',
      },
    ],
  },
  {
    id: 'account',
    title: 'Account & Privacy',
    icon: Shield,
    items: [
      {
        question: 'Is my collection data private?',
        answer: 'Yes, your inventory and collection data is completely private. Only you can see your cards. We never share individual user data with third parties.',
      },
      {
        question: 'How do I delete my account?',
        answer: 'Go to Settings and scroll to the bottom. Click "Delete Account" and confirm. This will permanently remove all your data including inventory, want lists, and preferences.',
      },
      {
        question: 'Can I export my data?',
        answer: 'Yes! Go to the Inventory page and use the Export button. You can download your collection as CSV, plain text, or CardTrader-compatible format.',
      },
    ],
  },
];

function FAQAccordion({ category }: { category: FAQCategory }) {
  const [openItems, setOpenItems] = useState<Set<number>>(new Set());
  const Icon = category.icon;

  const toggleItem = (index: number) => {
    const newOpen = new Set(openItems);
    if (newOpen.has(index)) {
      newOpen.delete(index);
    } else {
      newOpen.add(index);
    }
    setOpenItems(newOpen);
  };

  return (
    <Card className="glow-accent">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Icon className="w-5 h-5 text-[rgb(var(--accent))]" />
          {category.title}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        {category.items.map((item, index) => (
          <div key={index} className="border border-border rounded-lg overflow-hidden">
            <button
              onClick={() => toggleItem(index)}
              className="w-full flex items-center justify-between p-4 text-left hover:bg-secondary/50 transition-colors"
            >
              <span className="font-medium text-foreground pr-4">{item.question}</span>
              {openItems.has(index) ? (
                <ChevronDown className="w-5 h-5 text-muted-foreground shrink-0" />
              ) : (
                <ChevronRight className="w-5 h-5 text-muted-foreground shrink-0" />
              )}
            </button>
            {openItems.has(index) && (
              <div className="px-4 pb-4 text-muted-foreground border-t border-border pt-3">
                {item.answer}
              </div>
            )}
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

export default function HelpPage() {
  const [searchQuery, setSearchQuery] = useState('');
  const [activeCategory, setActiveCategory] = useState<string | null>(null);

  // Filter categories based on search
  const filteredCategories = faqCategories
    .map(category => ({
      ...category,
      items: category.items.filter(
        item =>
          item.question.toLowerCase().includes(searchQuery.toLowerCase()) ||
          item.answer.toLowerCase().includes(searchQuery.toLowerCase())
      ),
    }))
    .filter(category => category.items.length > 0);

  const displayCategories = activeCategory
    ? filteredCategories.filter(c => c.id === activeCategory)
    : filteredCategories;

  return (
    <div className="container mx-auto px-4 py-8 space-y-8">
      <PageHeader
        title="Help & FAQ"
        subtitle="Find answers to common questions"
      />

      {/* Search */}
      <div className="max-w-xl mx-auto">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
          <Input
            placeholder="Search for answers..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-10"
          />
        </div>
      </div>

      {/* Category Pills */}
      <div className="flex flex-wrap justify-center gap-2">
        <Button
          variant={activeCategory === null ? 'default' : 'secondary'}
          size="sm"
          onClick={() => setActiveCategory(null)}
          className={activeCategory === null ? 'gradient-arcane text-white' : ''}
        >
          All Topics
        </Button>
        {faqCategories.map((category) => {
          const Icon = category.icon;
          return (
            <Button
              key={category.id}
              variant={activeCategory === category.id ? 'default' : 'secondary'}
              size="sm"
              onClick={() => setActiveCategory(category.id)}
              className={activeCategory === category.id ? 'gradient-arcane text-white' : ''}
            >
              <Icon className="w-4 h-4 mr-1" />
              {category.title}
            </Button>
          );
        })}
      </div>

      {/* FAQ Content */}
      {displayCategories.length === 0 ? (
        <Card className="glow-accent">
          <CardContent className="py-12 text-center">
            <HelpCircle className="w-12 h-12 mx-auto text-muted-foreground mb-4" />
            <p className="text-muted-foreground mb-4">
              No results found for &quot;{searchQuery}&quot;
            </p>
            <Button variant="secondary" onClick={() => setSearchQuery('')}>
              Clear Search
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-6">
          {displayCategories.map((category) => (
            <FAQAccordion key={category.id} category={category} />
          ))}
        </div>
      )}

      {/* Still need help? */}
      <Card className="glow-accent bg-gradient-to-r from-[rgb(var(--accent))]/10 to-[rgb(var(--magic-gold))]/10">
        <CardContent className="p-8 text-center">
          <MessageSquare className="w-10 h-10 mx-auto text-[rgb(var(--accent))] mb-4" />
          <h2 className="font-display text-xl text-foreground mb-2">
            Still have questions?
          </h2>
          <p className="text-muted-foreground mb-4">
            Can&apos;t find what you&apos;re looking for? We&apos;re here to help.
          </p>
          <Button asChild className="gradient-arcane text-white">
            <Link href="/contact">Contact Support</Link>
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
