'use client';

import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Store,
  MapPin,
  CheckCircle,
  Globe,
  Calendar,
  ChevronRight,
} from 'lucide-react';
import Link from 'next/link';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { LoadingPage } from '@/components/ui/Loading';
import { ErrorDisplay } from '@/components/ui/ErrorDisplay';
import { getNearbyTradingPosts, type TradingPostPublic } from '@/lib/api/trading-posts';

const US_STATES = [
  { value: '', label: 'All States' },
  { value: 'AL', label: 'Alabama' },
  { value: 'AK', label: 'Alaska' },
  { value: 'AZ', label: 'Arizona' },
  { value: 'AR', label: 'Arkansas' },
  { value: 'CA', label: 'California' },
  { value: 'CO', label: 'Colorado' },
  { value: 'CT', label: 'Connecticut' },
  { value: 'DE', label: 'Delaware' },
  { value: 'FL', label: 'Florida' },
  { value: 'GA', label: 'Georgia' },
  { value: 'HI', label: 'Hawaii' },
  { value: 'ID', label: 'Idaho' },
  { value: 'IL', label: 'Illinois' },
  { value: 'IN', label: 'Indiana' },
  { value: 'IA', label: 'Iowa' },
  { value: 'KS', label: 'Kansas' },
  { value: 'KY', label: 'Kentucky' },
  { value: 'LA', label: 'Louisiana' },
  { value: 'ME', label: 'Maine' },
  { value: 'MD', label: 'Maryland' },
  { value: 'MA', label: 'Massachusetts' },
  { value: 'MI', label: 'Michigan' },
  { value: 'MN', label: 'Minnesota' },
  { value: 'MS', label: 'Mississippi' },
  { value: 'MO', label: 'Missouri' },
  { value: 'MT', label: 'Montana' },
  { value: 'NE', label: 'Nebraska' },
  { value: 'NV', label: 'Nevada' },
  { value: 'NH', label: 'New Hampshire' },
  { value: 'NJ', label: 'New Jersey' },
  { value: 'NM', label: 'New Mexico' },
  { value: 'NY', label: 'New York' },
  { value: 'NC', label: 'North Carolina' },
  { value: 'ND', label: 'North Dakota' },
  { value: 'OH', label: 'Ohio' },
  { value: 'OK', label: 'Oklahoma' },
  { value: 'OR', label: 'Oregon' },
  { value: 'PA', label: 'Pennsylvania' },
  { value: 'RI', label: 'Rhode Island' },
  { value: 'SC', label: 'South Carolina' },
  { value: 'SD', label: 'South Dakota' },
  { value: 'TN', label: 'Tennessee' },
  { value: 'TX', label: 'Texas' },
  { value: 'UT', label: 'Utah' },
  { value: 'VT', label: 'Vermont' },
  { value: 'VA', label: 'Virginia' },
  { value: 'WA', label: 'Washington' },
  { value: 'WV', label: 'West Virginia' },
  { value: 'WI', label: 'Wisconsin' },
  { value: 'WY', label: 'Wyoming' },
];

function StoreCard({ store }: { store: TradingPostPublic }) {
  const location = [store.city, store.state].filter(Boolean).join(', ');

  return (
    <Card interactive>
      <Link href={`/stores/${store.id}`}>
        <CardContent className="p-6">
          <div className="flex items-start justify-between gap-4">
            <div className="flex-1">
              {/* Store Header */}
              <div className="flex items-start gap-3 mb-3">
                <div className="w-12 h-12 rounded-lg bg-secondary flex items-center justify-center flex-shrink-0">
                  {store.logo_url ? (
                    <img
                      src={store.logo_url}
                      alt={store.store_name}
                      className="w-12 h-12 rounded-lg object-cover"
                    />
                  ) : (
                    <Store className="w-6 h-6 text-[rgb(var(--accent))]" />
                  )}
                </div>
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    <h3 className="text-lg font-semibold text-foreground">
                      {store.store_name}
                    </h3>
                    {store.is_verified && (
                      <CheckCircle className="w-4 h-4 text-[rgb(var(--success))]" />
                    )}
                  </div>
                  {location && (
                    <div className="flex items-center gap-1 text-sm text-muted-foreground">
                      <MapPin className="w-4 h-4" />
                      {location}
                    </div>
                  )}
                </div>
              </div>

              {/* Description */}
              {store.description && (
                <p className="text-sm text-muted-foreground mb-3 line-clamp-2">
                  {store.description}
                </p>
              )}

              {/* Services */}
              {store.services && store.services.length > 0 && (
                <div className="flex flex-wrap gap-1.5">
                  {store.services.slice(0, 4).map((service) => (
                    <Badge key={service} variant="secondary" className="text-xs">
                      {service}
                    </Badge>
                  ))}
                  {store.services.length > 4 && (
                    <Badge variant="secondary" className="text-xs">
                      +{store.services.length - 4} more
                    </Badge>
                  )}
                </div>
              )}
            </div>

            {/* Arrow */}
            <ChevronRight className="w-5 h-5 text-muted-foreground flex-shrink-0 mt-4" />
          </div>
        </CardContent>
      </Link>
    </Card>
  );
}

export default function StoresPage() {
  const queryClient = useQueryClient();
  const [stateFilter, setStateFilter] = useState('');
  const [cityFilter, setCityFilter] = useState('');
  const [verifiedOnly, setVerifiedOnly] = useState(false);
  const [page, setPage] = useState(1);
  const pageSize = 20;

  const { data, isLoading, error } = useQuery({
    queryKey: ['trading-posts', stateFilter, cityFilter, verifiedOnly, page],
    queryFn: () =>
      getNearbyTradingPosts({
        state: stateFilter || undefined,
        city: cityFilter || undefined,
        verified_only: verifiedOnly || undefined,
        page,
        page_size: pageSize,
      }),
  });

  const totalPages = data ? Math.ceil(data.total / pageSize) : 0;

  return (
    <div className="space-y-6 animate-in">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-3xl font-bold text-foreground">Trading Posts</h1>
          <p className="text-muted-foreground mt-1">
            Find local game stores that accept trade-ins and offer competitive buylist prices
          </p>
        </div>
        <Link href="/store/register">
          <Button className="gradient-arcane text-white glow-accent">
            <Store className="w-4 h-4 mr-2" />
            Register Your Store
          </Button>
        </Link>
      </div>

      {/* Filters */}
      <Card>
        <CardContent className="p-4">
          <div className="flex flex-col sm:flex-row gap-4">
            {/* State Filter */}
            <div className="flex-1">
              <label className="text-sm text-muted-foreground mb-2 block">
                State
              </label>
              <select
                value={stateFilter}
                onChange={(e) => {
                  setStateFilter(e.target.value);
                  setPage(1);
                }}
                className="w-full px-3 py-2 bg-secondary border border-border rounded-md text-foreground focus:outline-none focus:ring-2 focus:ring-accent"
              >
                {US_STATES.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </div>

            {/* City Filter */}
            <div className="flex-1">
              <label className="text-sm text-muted-foreground mb-2 block">
                City
              </label>
              <input
                type="text"
                placeholder="Enter city name..."
                value={cityFilter}
                onChange={(e) => {
                  setCityFilter(e.target.value);
                  setPage(1);
                }}
                className="w-full px-3 py-2 bg-secondary border border-border rounded-md text-foreground focus:outline-none focus:ring-2 focus:ring-accent placeholder:text-muted-foreground"
              />
            </div>

            {/* Verified Only Toggle */}
            <div className="flex items-end">
              <label className="flex items-center gap-2 cursor-pointer px-4 py-2 rounded-md bg-secondary border border-border hover:border-accent transition-colors">
                <input
                  type="checkbox"
                  checked={verifiedOnly}
                  onChange={(e) => {
                    setVerifiedOnly(e.target.checked);
                    setPage(1);
                  }}
                  className="rounded border-border text-accent focus:ring-accent"
                />
                <span className="text-sm text-foreground">Verified Only</span>
                <CheckCircle className="w-4 h-4 text-[rgb(var(--success))]" />
              </label>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Store List */}
      {isLoading ? (
        <LoadingPage />
      ) : error ? (
        <ErrorDisplay
          message={error instanceof Error ? error.message : 'Failed to load stores'}
          status={error instanceof Error && 'status' in error ? (error as any).status : undefined}
          onRetry={() =>
            queryClient.invalidateQueries({
              queryKey: ['trading-posts', stateFilter, cityFilter, verifiedOnly, page],
            })
          }
        />
      ) : data?.items.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center">
            <Store className="w-12 h-12 mx-auto text-muted-foreground mb-4" />
            <p className="text-muted-foreground mb-4">
              No trading posts found matching your filters
            </p>
            <Link href="/store/register">
              <Button variant="secondary">
                Be the first to register in your area
              </Button>
            </Link>
          </CardContent>
        </Card>
      ) : (
        <>
          <div className="text-sm text-muted-foreground">
            Showing {data?.items.length} of {data?.total} trading posts
          </div>

          <div className="space-y-4">
            {data?.items.map((store) => (
              <StoreCard key={store.id} store={store} />
            ))}
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-center gap-2">
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
              >
                Previous
              </Button>
              <span className="text-sm text-muted-foreground">
                Page {page} of {totalPages}
              </span>
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setPage((p) => p + 1)}
                disabled={page >= totalPages}
              >
                Next
              </Button>
            </div>
          )}
        </>
      )}

      {/* CTA Section */}
      <Card className="bg-gradient-to-r from-[rgb(var(--accent))]/10 to-[rgb(var(--secondary))]/50 border-[rgb(var(--accent))]/30">
        <CardContent className="p-6">
          <div className="flex flex-col md:flex-row items-center justify-between gap-4">
            <div>
              <h3 className="text-lg font-semibold text-foreground mb-1">
                Own a Game Store?
              </h3>
              <p className="text-muted-foreground">
                Register your Trading Post to receive trade-in quotes from local collectors
              </p>
            </div>
            <div className="flex gap-3">
              <Link href="/store/register">
                <Button className="gradient-arcane text-white glow-accent">
                  Register Now
                </Button>
              </Link>
              <Link href="/events">
                <Button variant="secondary">
                  <Calendar className="w-4 h-4 mr-2" />
                  View Events
                </Button>
              </Link>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
