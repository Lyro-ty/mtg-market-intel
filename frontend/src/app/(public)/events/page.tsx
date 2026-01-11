'use client';

import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import Link from 'next/link';
import {
  Calendar,
  MapPin,
  Clock,
  Users,
  DollarSign,
  Tag,
  Store,
  ChevronRight,
  Trophy,
  Percent,
  Package,
  Users2,
} from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { LoadingPage } from '@/components/ui/Loading';
import { ErrorDisplay } from '@/components/ui/ErrorDisplay';
import { getNearbyEvents, type TradingPostEvent } from '@/lib/api/trading-posts';
import { safeToFixed } from '@/lib/utils';

const EVENT_TYPE_OPTIONS = [
  { value: '', label: 'All Events', icon: Calendar },
  { value: 'tournament', label: 'Tournaments', icon: Trophy },
  { value: 'sale', label: 'Sales', icon: Percent },
  { value: 'release', label: 'Releases', icon: Package },
  { value: 'meetup', label: 'Meetups', icon: Users2 },
];

const FORMAT_OPTIONS = [
  { value: '', label: 'All Formats' },
  { value: 'Standard', label: 'Standard' },
  { value: 'Modern', label: 'Modern' },
  { value: 'Pioneer', label: 'Pioneer' },
  { value: 'Legacy', label: 'Legacy' },
  { value: 'Commander', label: 'Commander' },
  { value: 'Draft', label: 'Draft' },
  { value: 'Sealed', label: 'Sealed' },
  { value: 'Pauper', label: 'Pauper' },
];

const DAYS_OPTIONS = [
  { value: 7, label: 'Next 7 Days' },
  { value: 14, label: 'Next 2 Weeks' },
  { value: 30, label: 'Next 30 Days' },
  { value: 60, label: 'Next 60 Days' },
];

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

const EVENT_TYPE_COLORS: Record<string, string> = {
  tournament: 'bg-[rgb(var(--accent))]/20 text-[rgb(var(--accent))] border-[rgb(var(--accent))]/30',
  sale: 'bg-[rgb(var(--success))]/20 text-[rgb(var(--success))] border-[rgb(var(--success))]/30',
  release: 'bg-purple-500/20 text-purple-400 border-purple-500/30',
  meetup: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
};

const EVENT_TYPE_ICONS: Record<string, typeof Calendar> = {
  tournament: Trophy,
  sale: Percent,
  release: Package,
  meetup: Users2,
};

function formatDate(dateStr: string) {
  const date = new Date(dateStr);
  return date.toLocaleDateString('en-US', {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
  });
}

function formatTime(dateStr: string) {
  const date = new Date(dateStr);
  return date.toLocaleTimeString('en-US', {
    hour: 'numeric',
    minute: '2-digit',
  });
}

function EventCard({ event }: { event: TradingPostEvent }) {
  const EventIcon = EVENT_TYPE_ICONS[event.event_type] || Calendar;
  const storeLocation = event.trading_post
    ? [event.trading_post.city, event.trading_post.state].filter(Boolean).join(', ')
    : null;

  return (
    <Card interactive>
      <Link href={event.trading_post ? `/stores/${event.trading_post_id}` : '#'}>
        <CardContent className="p-6">
          <div className="flex items-start gap-4">
            {/* Date Block */}
            <div className="text-center min-w-[70px] p-3 rounded-lg bg-secondary">
              <div className="text-2xl font-bold text-[rgb(var(--accent))]">
                {new Date(event.start_time).getDate()}
              </div>
              <div className="text-xs text-muted-foreground uppercase">
                {new Date(event.start_time).toLocaleDateString('en-US', { month: 'short' })}
              </div>
              <div className="text-xs text-muted-foreground">
                {new Date(event.start_time).toLocaleDateString('en-US', { weekday: 'short' })}
              </div>
            </div>

            {/* Event Info */}
            <div className="flex-1">
              <div className="flex items-start justify-between gap-2 mb-2">
                <div>
                  <div className="flex items-center gap-2 mb-1">
                    <h3 className="text-lg font-semibold text-foreground">
                      {event.title}
                    </h3>
                    <Badge className={EVENT_TYPE_COLORS[event.event_type] || ''}>
                      <EventIcon className="w-3 h-3 mr-1" />
                      {event.event_type}
                    </Badge>
                  </div>
                  {event.trading_post && (
                    <div className="flex items-center gap-1 text-sm text-[rgb(var(--accent))]">
                      <Store className="w-4 h-4" />
                      {event.trading_post.store_name}
                    </div>
                  )}
                </div>
                <ChevronRight className="w-5 h-5 text-muted-foreground flex-shrink-0" />
              </div>

              {/* Event Meta */}
              <div className="flex flex-wrap gap-x-4 gap-y-1 text-sm text-muted-foreground mb-2">
                <span className="flex items-center gap-1">
                  <Clock className="w-4 h-4" />
                  {formatTime(event.start_time)}
                </span>
                {storeLocation && (
                  <span className="flex items-center gap-1">
                    <MapPin className="w-4 h-4" />
                    {storeLocation}
                  </span>
                )}
                {event.format && (
                  <span className="flex items-center gap-1">
                    <Tag className="w-4 h-4" />
                    {event.format}
                  </span>
                )}
              </div>

              {/* Event Details */}
              <div className="flex flex-wrap gap-2">
                {event.entry_fee !== null && event.entry_fee !== undefined && (
                  <Badge variant="secondary">
                    <DollarSign className="w-3 h-3 mr-1" />
                    ${safeToFixed(event.entry_fee, 2)} Entry
                  </Badge>
                )}
                {event.max_players && (
                  <Badge variant="secondary">
                    <Users className="w-3 h-3 mr-1" />
                    Max {event.max_players} Players
                  </Badge>
                )}
              </div>

              {/* Description */}
              {event.description && (
                <p className="text-sm text-muted-foreground mt-2 line-clamp-2">
                  {event.description}
                </p>
              )}
            </div>
          </div>
        </CardContent>
      </Link>
    </Card>
  );
}

export default function EventsPage() {
  const queryClient = useQueryClient();
  const [eventType, setEventType] = useState('');
  const [format, setFormat] = useState('');
  const [stateFilter, setStateFilter] = useState('');
  const [days, setDays] = useState(30);

  const { data, isLoading, error } = useQuery({
    queryKey: ['nearby-events', eventType, format, stateFilter, days],
    queryFn: () =>
      getNearbyEvents({
        event_type: eventType || undefined,
        format: format || undefined,
        state: stateFilter || undefined,
        days,
        limit: 50,
      }),
  });

  // Group events by date
  const groupedEvents: Record<string, TradingPostEvent[]> = {};
  if (data?.items) {
    data.items.forEach((event) => {
      const dateKey = new Date(event.start_time).toISOString().split('T')[0];
      if (!groupedEvents[dateKey]) {
        groupedEvents[dateKey] = [];
      }
      groupedEvents[dateKey].push(event);
    });
  }

  const sortedDates = Object.keys(groupedEvents).sort();

  return (
    <div className="space-y-6 animate-in">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-3xl font-bold text-foreground">Local Events</h1>
          <p className="text-muted-foreground mt-1">
            Discover tournaments, sales, releases, and meetups at local game stores
          </p>
        </div>
        <Link href="/stores">
          <Button variant="secondary">
            <Store className="w-4 h-4 mr-2" />
            Browse Stores
          </Button>
        </Link>
      </div>

      {/* Event Type Tabs */}
      <div className="flex flex-wrap gap-2">
        {EVENT_TYPE_OPTIONS.map((option) => {
          const Icon = option.icon;
          return (
            <Button
              key={option.value}
              variant={eventType === option.value ? 'default' : 'secondary'}
              size="sm"
              onClick={() => setEventType(option.value)}
              className={eventType === option.value ? 'gradient-arcane text-white' : ''}
            >
              <Icon className="w-4 h-4 mr-1" />
              {option.label}
            </Button>
          );
        })}
      </div>

      {/* Filters */}
      <Card>
        <CardContent className="p-4">
          <div className="flex flex-col sm:flex-row gap-4">
            {/* Date Range */}
            <div className="flex-1">
              <label className="text-sm text-muted-foreground mb-2 block">
                Date Range
              </label>
              <select
                value={days}
                onChange={(e) => setDays(Number(e.target.value))}
                className="w-full px-3 py-2 bg-secondary border border-border rounded-md text-foreground focus:outline-none focus:ring-2 focus:ring-accent"
              >
                {DAYS_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </div>

            {/* Format Filter (for tournaments) */}
            <div className="flex-1">
              <label className="text-sm text-muted-foreground mb-2 block">
                Format
              </label>
              <select
                value={format}
                onChange={(e) => setFormat(e.target.value)}
                className="w-full px-3 py-2 bg-secondary border border-border rounded-md text-foreground focus:outline-none focus:ring-2 focus:ring-accent"
              >
                {FORMAT_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </div>

            {/* State Filter */}
            <div className="flex-1">
              <label className="text-sm text-muted-foreground mb-2 block">
                State
              </label>
              <select
                value={stateFilter}
                onChange={(e) => setStateFilter(e.target.value)}
                className="w-full px-3 py-2 bg-secondary border border-border rounded-md text-foreground focus:outline-none focus:ring-2 focus:ring-accent"
              >
                {US_STATES.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Events List */}
      {isLoading ? (
        <LoadingPage />
      ) : error ? (
        <ErrorDisplay
          message={error instanceof Error ? error.message : 'Failed to load events'}
          status={error instanceof Error && 'status' in error ? (error as any).status : undefined}
          onRetry={() =>
            queryClient.invalidateQueries({
              queryKey: ['nearby-events', eventType, format, stateFilter, days],
            })
          }
        />
      ) : data?.items.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center">
            <Calendar className="w-12 h-12 mx-auto text-muted-foreground mb-4" />
            <p className="text-muted-foreground mb-4">
              No events found matching your filters
            </p>
            <p className="text-sm text-muted-foreground">
              Try adjusting your filters or check back later for new events
            </p>
          </CardContent>
        </Card>
      ) : (
        <>
          <div className="text-sm text-muted-foreground">
            Found {data?.total} events in the next {days} days
          </div>

          {/* Events grouped by date */}
          <div className="space-y-6">
            {sortedDates.map((dateKey) => (
              <div key={dateKey}>
                <div className="sticky top-0 bg-background/80 backdrop-blur-sm py-2 mb-3 z-10">
                  <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">
                    {new Date(dateKey).toLocaleDateString('en-US', {
                      weekday: 'long',
                      month: 'long',
                      day: 'numeric',
                    })}
                  </h2>
                </div>
                <div className="space-y-4">
                  {groupedEvents[dateKey].map((event) => (
                    <EventCard key={event.id} event={event} />
                  ))}
                </div>
              </div>
            ))}
          </div>
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
                Register your Trading Post to list events and receive trade-in quotes
              </p>
            </div>
            <div className="flex gap-3">
              <Link href="/store/register">
                <Button className="gradient-arcane text-white glow-accent">
                  Register Store
                </Button>
              </Link>
              <Link href="/stores">
                <Button variant="secondary">
                  <Store className="w-4 h-4 mr-2" />
                  Browse Stores
                </Button>
              </Link>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
