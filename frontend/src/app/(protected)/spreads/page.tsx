'use client';

import React from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  TrendingUp,
  TrendingDown,
  ArrowRightLeft,
  DollarSign,
  Percent,
  Store,
  AlertTriangle,
  Info,
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { PageHeader } from '@/components/ornate/page-header';
import { formatCurrency, cn } from '@/lib/utils';
import {
  getBuylistOpportunities,
  getSellingOpportunities,
  getArbitrageOpportunities,
  getSpreadMarketSummary,
} from '@/lib/api/spreads';
import type { BuylistOpportunity, ArbitrageOpportunity } from '@/lib/api/spreads';
import Link from 'next/link';
import Image from 'next/image';

function OpportunityCardSkeleton() {
  return (
    <Card className="glow-accent">
      <CardContent className="p-4">
        <div className="flex gap-4">
          <Skeleton className="w-16 h-20 rounded" />
          <div className="flex-1">
            <Skeleton className="h-5 w-40 mb-2" />
            <Skeleton className="h-4 w-24 mb-3" />
            <div className="flex gap-4">
              <Skeleton className="h-8 w-24" />
              <Skeleton className="h-8 w-24" />
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function BuylistOpportunityCard({ opportunity }: { opportunity: BuylistOpportunity }) {
  return (
    <Card className="glow-accent hover:border-[rgb(var(--accent))]/30 transition-colors">
      <CardContent className="p-4">
        <Link href={`/cards/${opportunity.card_id}`} className="flex gap-4">
          {/* Card Image */}
          {opportunity.image_url ? (
            <div className="relative w-16 h-22 shrink-0">
              <Image
                src={opportunity.image_url}
                alt={opportunity.card_name}
                fill
                className="object-contain rounded"
                sizes="64px"
              />
            </div>
          ) : (
            <div className="w-16 h-22 bg-secondary rounded flex items-center justify-center shrink-0">
              <DollarSign className="w-6 h-6 text-muted-foreground" />
            </div>
          )}

          {/* Info */}
          <div className="flex-1 min-w-0">
            <div className="flex items-start justify-between gap-2">
              <div>
                <h3 className="font-heading font-medium text-foreground truncate">
                  {opportunity.card_name}
                </h3>
                <p className="text-sm text-muted-foreground">
                  {opportunity.set_code} &bull; {opportunity.vendor}
                </p>
              </div>
              <Badge
                className={cn(
                  'shrink-0',
                  opportunity.spread_pct < 30
                    ? 'bg-[rgb(var(--success))]/20 text-[rgb(var(--success))]'
                    : opportunity.spread_pct < 50
                    ? 'bg-[rgb(var(--warning))]/20 text-[rgb(var(--warning))]'
                    : 'bg-[rgb(var(--destructive))]/20 text-[rgb(var(--destructive))]'
                )}
              >
                {opportunity.spread_pct.toFixed(1)}% spread
              </Badge>
            </div>

            <div className="mt-3 grid grid-cols-3 gap-4 text-sm">
              <div>
                <p className="text-muted-foreground">Retail</p>
                <p className="font-medium text-foreground">
                  {formatCurrency(opportunity.retail_price)}
                </p>
              </div>
              <div>
                <p className="text-muted-foreground">Buylist</p>
                <p className="font-medium text-[rgb(var(--success))]">
                  {formatCurrency(opportunity.buylist_price)}
                </p>
              </div>
              <div>
                <p className="text-muted-foreground">Spread</p>
                <p className="font-medium text-foreground">
                  {formatCurrency(opportunity.spread)}
                </p>
              </div>
            </div>

            {opportunity.credit_price && (
              <div className="mt-2 text-sm text-muted-foreground">
                Store Credit: {formatCurrency(opportunity.credit_price)}
                {opportunity.credit_spread_pct && (
                  <span className="ml-2">({opportunity.credit_spread_pct.toFixed(1)}% spread)</span>
                )}
              </div>
            )}
          </div>
        </Link>
      </CardContent>
    </Card>
  );
}

function ArbitrageOpportunityCard({ opportunity }: { opportunity: ArbitrageOpportunity }) {
  return (
    <Card className="glow-accent hover:border-[rgb(var(--accent))]/30 transition-colors">
      <CardContent className="p-4">
        <Link href={`/cards/${opportunity.card_id}`} className="flex gap-4">
          {/* Card Image */}
          {opportunity.image_url ? (
            <div className="relative w-16 h-22 shrink-0">
              <Image
                src={opportunity.image_url}
                alt={opportunity.card_name}
                fill
                className="object-contain rounded"
                sizes="64px"
              />
            </div>
          ) : (
            <div className="w-16 h-22 bg-secondary rounded flex items-center justify-center shrink-0">
              <ArrowRightLeft className="w-6 h-6 text-muted-foreground" />
            </div>
          )}

          {/* Info */}
          <div className="flex-1 min-w-0">
            <div className="flex items-start justify-between gap-2">
              <div>
                <h3 className="font-heading font-medium text-foreground truncate">
                  {opportunity.card_name}
                </h3>
                <p className="text-sm text-muted-foreground">{opportunity.set_code}</p>
              </div>
              <Badge className="shrink-0 bg-[rgb(var(--success))]/20 text-[rgb(var(--success))]">
                +{opportunity.profit_pct.toFixed(1)}%
              </Badge>
            </div>

            <div className="mt-3 flex items-center gap-2 text-sm">
              <div className="flex-1 p-2 rounded bg-secondary/50">
                <p className="text-muted-foreground">Buy from</p>
                <p className="font-medium text-foreground">{opportunity.buy_marketplace}</p>
                <p className="font-medium text-foreground">{formatCurrency(opportunity.buy_price)}</p>
              </div>
              <TrendingUp className="w-5 h-5 text-[rgb(var(--success))] shrink-0" />
              <div className="flex-1 p-2 rounded bg-secondary/50">
                <p className="text-muted-foreground">Sell to</p>
                <p className="font-medium text-foreground">{opportunity.sell_marketplace}</p>
                <p className="font-medium text-[rgb(var(--success))]">
                  {formatCurrency(opportunity.sell_price)}
                </p>
              </div>
            </div>

            <div className="mt-2 text-sm text-center">
              <span className="text-muted-foreground">Potential Profit: </span>
              <span className="font-medium text-[rgb(var(--success))]">
                {formatCurrency(opportunity.profit)}
              </span>
            </div>
          </div>
        </Link>
      </CardContent>
    </Card>
  );
}

export default function SpreadsPage() {
  const { data: summary, isLoading: summaryLoading } = useQuery({
    queryKey: ['spread-summary'],
    queryFn: getSpreadMarketSummary,
  });

  const { data: buylistOpps, isLoading: buylistLoading } = useQuery({
    queryKey: ['buylist-opportunities'],
    queryFn: () => getBuylistOpportunities({ limit: 20, min_spread_pct: 15 }),
  });

  const { data: sellingOpps, isLoading: sellingLoading } = useQuery({
    queryKey: ['selling-opportunities'],
    queryFn: () => getSellingOpportunities({ limit: 20, max_spread_pct: 35, min_buylist: 1 }),
  });

  const { data: arbitrageOpps, isLoading: arbitrageLoading } = useQuery({
    queryKey: ['arbitrage-opportunities'],
    queryFn: () => getArbitrageOpportunities({ limit: 20, min_profit_pct: 10, min_profit: 0.5 }),
  });

  return (
    <div className="space-y-6 animate-in">
      <PageHeader
        title="Spread Analysis"
        subtitle="Buylist opportunities, arbitrage plays, and market inefficiencies"
      />

      {/* Market Summary */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card className="glow-accent">
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-[rgb(var(--accent))]/10 flex items-center justify-center">
                <Store className="w-5 h-5 text-[rgb(var(--accent))]" />
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Cards with Buylist Data</p>
                {summaryLoading ? (
                  <Skeleton className="h-7 w-16" />
                ) : (
                  <p className="text-2xl font-bold text-foreground">
                    {summary?.cards_with_buylist_data?.toLocaleString() ?? 0}
                  </p>
                )}
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="glow-accent">
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-[rgb(var(--magic-gold))]/10 flex items-center justify-center">
                <Percent className="w-5 h-5 text-[rgb(var(--magic-gold))]" />
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Average Spread</p>
                {summaryLoading ? (
                  <Skeleton className="h-7 w-16" />
                ) : (
                  <p className="text-2xl font-bold text-foreground">
                    {summary?.average_spread_pct
                      ? `${summary.average_spread_pct.toFixed(1)}%`
                      : 'N/A'}
                  </p>
                )}
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="glow-accent">
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-[rgb(var(--success))]/10 flex items-center justify-center">
                <TrendingUp className="w-5 h-5 text-[rgb(var(--success))]" />
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Sample Size</p>
                {summaryLoading ? (
                  <Skeleton className="h-7 w-16" />
                ) : (
                  <p className="text-2xl font-bold text-foreground">
                    {summary?.sample_size?.toLocaleString() ?? 0}
                  </p>
                )}
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Disclaimer */}
      <Card className="bg-[rgb(var(--warning))]/5 border-[rgb(var(--warning))]/20">
        <CardContent className="p-4 flex items-start gap-3">
          <AlertTriangle className="w-5 h-5 text-[rgb(var(--warning))] shrink-0 mt-0.5" />
          <div className="text-sm">
            <p className="font-medium text-foreground">Important Disclaimer</p>
            <p className="text-muted-foreground">
              These opportunities do not account for fees, shipping costs, condition grading
              differences, or transaction times. Always verify prices before making purchasing
              decisions. Buylist data updates daily.
            </p>
          </div>
        </CardContent>
      </Card>

      {/* Tabs for different opportunity types */}
      <Tabs defaultValue="selling" className="space-y-4">
        <TabsList className="grid w-full grid-cols-3">
          <TabsTrigger value="selling" className="flex items-center gap-2">
            <TrendingUp className="w-4 h-4" />
            Best to Sell
          </TabsTrigger>
          <TabsTrigger value="buylist" className="flex items-center gap-2">
            <TrendingDown className="w-4 h-4" />
            Wide Spreads
          </TabsTrigger>
          <TabsTrigger value="arbitrage" className="flex items-center gap-2">
            <ArrowRightLeft className="w-4 h-4" />
            Arbitrage
          </TabsTrigger>
        </TabsList>

        <TabsContent value="selling" className="space-y-4">
          <Card className="glow-accent border-[rgb(var(--success))]/20">
            <CardHeader className="pb-2">
              <CardTitle className="flex items-center gap-2 text-lg">
                <TrendingUp className="w-5 h-5 text-[rgb(var(--success))]" />
                Best Selling Opportunities
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground mb-4">
                Cards where buylist prices are closest to retail. These are the best cards to sell
                to vendors rather than waiting for a buyer.
              </p>
              {sellingLoading ? (
                <div className="space-y-4">
                  {[1, 2, 3].map((i) => (
                    <OpportunityCardSkeleton key={i} />
                  ))}
                </div>
              ) : sellingOpps?.opportunities.length === 0 ? (
                <div className="text-center py-8 text-muted-foreground">
                  <Info className="w-12 h-12 mx-auto mb-4 opacity-50" />
                  <p>No selling opportunities found.</p>
                  <p className="text-sm">Buylist data may still be collecting.</p>
                </div>
              ) : (
                <div className="space-y-4">
                  {sellingOpps?.opportunities.map((opp) => (
                    <BuylistOpportunityCard key={`${opp.card_id}-${opp.vendor}`} opportunity={opp} />
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="buylist" className="space-y-4">
          <Card className="glow-accent border-[rgb(var(--warning))]/20">
            <CardHeader className="pb-2">
              <CardTitle className="flex items-center gap-2 text-lg">
                <TrendingDown className="w-5 h-5 text-[rgb(var(--warning))]" />
                Wide Buylist Spreads
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground mb-4">
                Cards with large gaps between retail and buylist prices. High spreads can indicate
                vendor risk assessment or market uncertainty.
              </p>
              {buylistLoading ? (
                <div className="space-y-4">
                  {[1, 2, 3].map((i) => (
                    <OpportunityCardSkeleton key={i} />
                  ))}
                </div>
              ) : buylistOpps?.opportunities.length === 0 ? (
                <div className="text-center py-8 text-muted-foreground">
                  <Info className="w-12 h-12 mx-auto mb-4 opacity-50" />
                  <p>No wide spread opportunities found.</p>
                  <p className="text-sm">Buylist data may still be collecting.</p>
                </div>
              ) : (
                <div className="space-y-4">
                  {buylistOpps?.opportunities.map((opp) => (
                    <BuylistOpportunityCard key={`${opp.card_id}-${opp.vendor}`} opportunity={opp} />
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="arbitrage" className="space-y-4">
          <Card className="glow-accent border-[rgb(var(--accent))]/20">
            <CardHeader className="pb-2">
              <CardTitle className="flex items-center gap-2 text-lg">
                <ArrowRightLeft className="w-5 h-5 text-[rgb(var(--accent))]" />
                Cross-Market Arbitrage
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground mb-4">
                Price differences between marketplaces that could be profitable. Buy low on one
                marketplace and sell high on another.
              </p>
              {arbitrageLoading ? (
                <div className="space-y-4">
                  {[1, 2, 3].map((i) => (
                    <OpportunityCardSkeleton key={i} />
                  ))}
                </div>
              ) : arbitrageOpps?.opportunities.length === 0 ? (
                <div className="text-center py-8 text-muted-foreground">
                  <Info className="w-12 h-12 mx-auto mb-4 opacity-50" />
                  <p>No arbitrage opportunities found.</p>
                  <p className="text-sm">
                    This requires price data from multiple marketplaces.
                  </p>
                </div>
              ) : (
                <div className="space-y-4">
                  {arbitrageOpps?.opportunities.map((opp) => (
                    <ArbitrageOpportunityCard key={opp.card_id} opportunity={opp} />
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
