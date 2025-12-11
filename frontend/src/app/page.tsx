'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import { LogIn, TrendingUp } from 'lucide-react';
import Link from 'next/link';
import Image from 'next/image';
import { SearchBar } from '@/components/cards/SearchBar';
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

  const handleSearch = (query: string) => {
    setSearchQuery(query);
    if (query.trim()) {
      router.push(`/cards?q=${encodeURIComponent(query.trim())}`);
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
          className="object-cover object-center"
          style={{ 
            objectFit: 'cover',
            objectPosition: 'center'
          }}
          unoptimized={false}
        />
        {/* Overlay for readability - reduced opacity since image has text */}
        <div className="absolute inset-0 bg-black/20" />
      </div>

      {/* Content */}
      <div className="relative z-10 w-full max-w-7xl mx-auto px-4 py-8">
        {/* Top Right Login Button */}
        <div className="absolute top-4 right-4 z-20">
          {isAuthenticated ? (
            <Link href="/inventory">
              <Button variant="primary" size="sm">
                Go to Inventory
              </Button>
            </Link>
          ) : (
            <Link href="/login">
              <Button variant="primary" size="sm" className="bg-gradient-to-r from-amber-500 to-orange-600">
                <LogIn className="w-4 h-4 mr-2" />
                Login
              </Button>
            </Link>
          )}
        </div>

        {/* Centered Search Section */}
        <div className="flex flex-col items-center justify-center min-h-[60vh] space-y-8">
          {/* Logo/Branding - Image already contains "DUALCASTERDEALS" text, so we show subtitle only */}
          <div className="text-center space-y-4">
            <p className="text-xl md:text-2xl text-white/90 drop-shadow-md font-medium">
              MTG Market Intelligence & Trading Platform
            </p>
          </div>

          {/* Search Bar */}
          <div className="w-full max-w-2xl">
            <SearchBar
              onSearch={handleSearch}
              placeholder="Search for MTG cards..."
              value={searchQuery}
            />
          </div>

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
