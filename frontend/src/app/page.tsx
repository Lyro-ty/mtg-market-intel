'use client';

import { useState, FormEvent } from 'react';
import { useRouter } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import { LogIn, TrendingUp, Search } from 'lucide-react';
import Link from 'next/link';
import Image from 'next/image';
import { Input } from '@/components/ui/Input';
import { Button } from '@/components/ui/Button';
import { Loading } from '@/components/ui/Loading';
import { getTopMovers } from '@/lib/api';
import { useAuth } from '@/contexts/AuthContext';
import { formatCurrency, formatPercent } from '@/lib/utils';
import type { TopMover } from '@/types';

export default function LandingPage() {
  const router = useRouter();
  const { isAuthenticated } = useAuth();
  const [searchQuery, setSearchQuery] = useState('');

  // Get top movers (valued cards) to display
  const { data: topMovers, isLoading: moversLoading } = useQuery({
    queryKey: ['top-movers', '24h'],
    queryFn: () => getTopMovers('24h'),
  });

  const handleSubmit = (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (searchQuery.trim()) {
      router.push(`/cards?q=${encodeURIComponent(searchQuery.trim())}`);
    }
  };

  // Combine gainers and losers, take top 8 most valuable
  const valuedCards = topMovers
    ? [...topMovers.gainers, ...topMovers.losers]
        .sort((a, b) => b.currentPriceUsd - a.currentPriceUsd)
        .slice(0, 8)
    : [];

  return (
    <div className="relative min-h-screen flex flex-col items-center justify-center overflow-hidden">
      {/* Background Image */}
      <div className="absolute inset-0 z-0">
        <Image
          src="/background.jpg"
          alt="Dualcaster Deals Background"
          fill
          priority
          sizes="100vw"
          className="object-contain object-center"
          style={{ 
            objectFit: 'contain',
            objectPosition: 'center'
          }}
          unoptimized={false}
        />
        {/* Fill remaining space with dark background matching image */}
        <div className="absolute inset-0 bg-[#1a1612] -z-10" />
        {/* Overlay for readability - reduced opacity since image has text */}
        <div className="absolute inset-0 bg-black/20" />
      </div>

      {/* Top Right Login Button - Fixed position */}
      <div className="fixed top-4 right-4 z-50">
        {isAuthenticated ? (
          <Link href="/inventory">
            <Button variant="primary" size="sm" className="bg-gradient-to-r from-amber-500 to-orange-600 shadow-lg">
              Go to Inventory
            </Button>
          </Link>
        ) : (
          <Link href="/login">
            <Button variant="primary" size="sm" className="bg-gradient-to-r from-amber-500 to-orange-600 shadow-lg">
              <LogIn className="w-4 h-4 mr-2" />
              Login
            </Button>
          </Link>
        )}
      </div>

      {/* Content */}
      <div className="relative z-10 w-full max-w-7xl mx-auto px-4 py-8">

        {/* Centered Search Section */}
        <div className="flex flex-col items-center justify-center min-h-[60vh] space-y-8">
          {/* Logo/Branding - Image already contains "DUALCASTERDEALS" text, so we show subtitle only */}
          <div className="text-center space-y-4">
            <p className="text-xl md:text-2xl text-white/90 drop-shadow-md font-medium">
              MTG Market Intelligence & Trading Platform
            </p>
          </div>

          {/* Search Bar */}
          <form onSubmit={handleSubmit} className="w-full max-w-2xl">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-white/70" />
              <Input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search for MTG cards..."
                className="pl-10 pr-24 bg-white/10 backdrop-blur-md border-white/20 text-white placeholder:text-white/60 focus:bg-white/15 focus:border-white/30"
              />
              <Button
                type="submit"
                variant="primary"
                size="sm"
                className="absolute right-2 top-1/2 -translate-y-1/2 bg-gradient-to-r from-amber-500 to-orange-600 hover:from-amber-600 hover:to-orange-700"
              >
                Search
              </Button>
            </div>
          </form>

          {/* Valued Cards Section */}
          {moversLoading ? (
            <div className="w-full max-w-6xl mt-12">
              <Loading />
            </div>
          ) : valuedCards.length > 0 ? (
            <div className="w-full max-w-6xl mt-12 space-y-6">
              <div className="text-center">
                <h2 className="text-2xl md:text-3xl font-bold text-white drop-shadow-lg mb-2 flex items-center justify-center gap-2">
                  <TrendingUp className="w-6 h-6" />
                  Valued Cards
                </h2>
                <p className="text-white/80 text-sm md:text-base">
                  Top cards by value (24h)
                </p>
              </div>
              
              {/* Cards Grid */}
              <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-4">
                {valuedCards.map((card, index) => (
                  <Link
                    key={`${card.cardName}-${card.setCode}-${index}`}
                    href={`/cards?q=${encodeURIComponent(card.cardName)}`}
                    className="group"
                  >
                    <div className="bg-white/10 backdrop-blur-md rounded-lg p-4 border border-white/20 hover:bg-white/20 transition-all cursor-pointer">
                      <div className="space-y-2">
                        <h3 className="font-semibold text-white text-sm truncate group-hover:text-amber-400 transition-colors">
                          {card.cardName}
                        </h3>
                        <div className="flex items-center justify-between">
                          <span className="text-xs text-white/70">{card.setCode}</span>
                          <span className="text-sm font-bold text-white">
                            {formatCurrency(card.currentPriceUsd)}
                          </span>
                        </div>
                        <div className="flex items-center justify-between">
                          <span className="text-xs text-white/60">{card.format}</span>
                          <span
                            className={`text-xs font-medium ${
                              card.changePct > 0
                                ? 'text-green-400'
                                : card.changePct < 0
                                ? 'text-red-400'
                                : 'text-white/70'
                            }`}
                          >
                            {card.changePct > 0 ? '+' : ''}
                            {formatPercent(card.changePct)}
                          </span>
                        </div>
                      </div>
                    </div>
                  </Link>
                ))}
              </div>
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}
