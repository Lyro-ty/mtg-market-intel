'use client';

import { use } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import Link from 'next/link';
import {
  Store,
  MapPin,
  Phone,
  Globe,
  Clock,
  CheckCircle,
  ArrowLeft,
  Calendar,
  Users,
  Tag,
  DollarSign,
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { LoadingPage } from '@/components/ui/Loading';
import { ErrorDisplay } from '@/components/ui/ErrorDisplay';
import {
  getTradingPost,
  getTradingPostEvents,
  type TradingPostPublic,
  type TradingPostEvent,
} from '@/lib/api/trading-posts';
import { safeToFixed } from '@/lib/utils';

const EVENT_TYPE_COLORS: Record<string, string> = {
  tournament: 'bg-[rgb(var(--accent))]/20 text-[rgb(var(--accent))] border-[rgb(var(--accent))]/30',
  sale: 'bg-[rgb(var(--success))]/20 text-[rgb(var(--success))] border-[rgb(var(--success))]/30',
  release: 'bg-purple-500/20 text-purple-400 border-purple-500/30',
  meetup: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
};

const DAY_NAMES = ['sunday', 'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday'];
const DAY_LABELS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

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
  return (
    <Card className="glow-accent">
      <CardContent className="p-4">
        <div className="flex items-start gap-3">
          <div className="text-center min-w-[60px]">
            <div className="text-2xl font-bold text-[rgb(var(--accent))]">
              {new Date(event.start_time).getDate()}
            </div>
            <div className="text-xs text-muted-foreground uppercase">
              {new Date(event.start_time).toLocaleDateString('en-US', { month: 'short' })}
            </div>
          </div>
          <div className="flex-1">
            <div className="flex items-center gap-2 mb-1">
              <h4 className="font-semibold text-foreground">{event.title}</h4>
              <Badge className={EVENT_TYPE_COLORS[event.event_type] || ''}>
                {event.event_type}
              </Badge>
            </div>
            <div className="flex flex-wrap gap-3 text-sm text-muted-foreground">
              <span className="flex items-center gap-1">
                <Clock className="w-4 h-4" />
                {formatTime(event.start_time)}
              </span>
              {event.format && (
                <span className="flex items-center gap-1">
                  <Tag className="w-4 h-4" />
                  {event.format}
                </span>
              )}
              {event.entry_fee !== null && event.entry_fee !== undefined && (
                <span className="flex items-center gap-1">
                  <DollarSign className="w-4 h-4" />
                  ${safeToFixed(event.entry_fee, 2)}
                </span>
              )}
              {event.max_players && (
                <span className="flex items-center gap-1">
                  <Users className="w-4 h-4" />
                  Max {event.max_players}
                </span>
              )}
            </div>
            {event.description && (
              <p className="text-sm text-muted-foreground mt-2 line-clamp-2">
                {event.description}
              </p>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function HoursDisplay({ hours }: { hours: Record<string, string> }) {
  const today = new Date().getDay();

  return (
    <div className="space-y-1">
      {DAY_NAMES.map((day, index) => (
        <div
          key={day}
          className={`flex justify-between text-sm ${
            index === today ? 'font-semibold text-[rgb(var(--accent))]' : 'text-muted-foreground'
          }`}
        >
          <span>{DAY_LABELS[index]}</span>
          <span>{hours[day] || 'Closed'}</span>
        </div>
      ))}
    </div>
  );
}

export default function StoreDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const resolvedParams = use(params);
  const storeId = parseInt(resolvedParams.id, 10);
  const queryClient = useQueryClient();

  const {
    data: store,
    isLoading: storeLoading,
    error: storeError,
  } = useQuery({
    queryKey: ['trading-post', storeId],
    queryFn: () => getTradingPost(storeId),
    enabled: !isNaN(storeId),
  });

  const {
    data: eventsData,
    isLoading: eventsLoading,
    error: eventsError,
  } = useQuery({
    queryKey: ['trading-post-events', storeId],
    queryFn: () => getTradingPostEvents(storeId),
    enabled: !isNaN(storeId),
  });

  if (storeLoading) {
    return <LoadingPage />;
  }

  if (storeError || !store) {
    return (
      <div className="space-y-6 animate-in">
        <Link href="/stores">
          <Button variant="ghost">
            <ArrowLeft className="w-4 h-4 mr-2" />
            Back to Stores
          </Button>
        </Link>
        <ErrorDisplay
          message={storeError instanceof Error ? storeError.message : 'Store not found'}
          status={storeError instanceof Error && 'status' in storeError ? (storeError as any).status : 404}
          onRetry={() => queryClient.invalidateQueries({ queryKey: ['trading-post', storeId] })}
        />
      </div>
    );
  }

  const location = [store.city, store.state, store.country].filter(Boolean).join(', ');

  return (
    <div className="space-y-6 animate-in">
      {/* Back Button */}
      <Link href="/stores">
        <Button variant="ghost">
          <ArrowLeft className="w-4 h-4 mr-2" />
          Back to Stores
        </Button>
      </Link>

      {/* Store Header */}
      <Card className="glow-accent">
        <CardContent className="p-6">
          <div className="flex flex-col md:flex-row gap-6">
            {/* Logo */}
            <div className="w-24 h-24 rounded-xl bg-secondary flex items-center justify-center flex-shrink-0 mx-auto md:mx-0">
              {store.logo_url ? (
                <img
                  src={store.logo_url}
                  alt={store.store_name}
                  className="w-24 h-24 rounded-xl object-cover"
                />
              ) : (
                <Store className="w-12 h-12 text-[rgb(var(--accent))]" />
              )}
            </div>

            {/* Info */}
            <div className="flex-1 text-center md:text-left">
              <div className="flex items-center justify-center md:justify-start gap-2 mb-2">
                <h1 className="text-2xl font-bold text-foreground">{store.store_name}</h1>
                {store.is_verified && (
                  <Badge className="bg-[rgb(var(--success))]/20 text-[rgb(var(--success))] border-[rgb(var(--success))]/30">
                    <CheckCircle className="w-3 h-3 mr-1" />
                    Verified
                  </Badge>
                )}
              </div>

              {location && (
                <div className="flex items-center justify-center md:justify-start gap-1 text-muted-foreground mb-3">
                  <MapPin className="w-4 h-4" />
                  {location}
                </div>
              )}

              {store.description && (
                <p className="text-muted-foreground mb-4">{store.description}</p>
              )}

              {/* Services */}
              {store.services && store.services.length > 0 && (
                <div className="flex flex-wrap justify-center md:justify-start gap-2">
                  {store.services.map((service) => (
                    <Badge key={service} variant="secondary">
                      {service}
                    </Badge>
                  ))}
                </div>
              )}
            </div>

            {/* CTA */}
            <div className="flex flex-col gap-2 flex-shrink-0">
              <Link href="/quotes">
                <Button className="gradient-arcane text-white glow-accent w-full">
                  Get Trade Quote
                </Button>
              </Link>
              {store.website && (
                <a href={store.website} target="_blank" rel="noopener noreferrer">
                  <Button variant="secondary" className="w-full">
                    <Globe className="w-4 h-4 mr-2" />
                    Visit Website
                  </Button>
                </a>
              )}
            </div>
          </div>
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Main Content */}
        <div className="lg:col-span-2 space-y-6">
          {/* Upcoming Events */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Calendar className="w-5 h-5" />
                Upcoming Events
              </CardTitle>
            </CardHeader>
            <CardContent>
              {eventsLoading ? (
                <div className="text-center py-8 text-muted-foreground">
                  Loading events...
                </div>
              ) : eventsError ? (
                <div className="text-center py-8 text-muted-foreground">
                  Failed to load events
                </div>
              ) : eventsData?.items && eventsData.items.length > 0 ? (
                <div className="space-y-4">
                  {eventsData.items.slice(0, 5).map((event) => (
                    <EventCard key={event.id} event={event} />
                  ))}
                </div>
              ) : (
                <div className="text-center py-8 text-muted-foreground">
                  <Calendar className="w-8 h-8 mx-auto mb-2 opacity-50" />
                  <p>No upcoming events scheduled</p>
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Sidebar */}
        <div className="space-y-6">
          {/* Contact Info */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Phone className="w-5 h-5" />
                Contact
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {store.website && (
                <a
                  href={store.website}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-2 text-[rgb(var(--accent))] hover:underline"
                >
                  <Globe className="w-4 h-4" />
                  {new URL(store.website).hostname}
                </a>
              )}
              {!store.website && (
                <p className="text-muted-foreground text-sm">
                  No contact information available
                </p>
              )}
            </CardContent>
          </Card>

          {/* Hours */}
          {store.hours && Object.keys(store.hours).length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Clock className="w-5 h-5" />
                  Hours
                </CardTitle>
              </CardHeader>
              <CardContent>
                <HoursDisplay hours={store.hours} />
              </CardContent>
            </Card>
          )}

          {/* CTA Card */}
          <Card className="bg-gradient-to-br from-[rgb(var(--accent))]/10 to-[rgb(var(--secondary))]/50 border-[rgb(var(--accent))]/30">
            <CardContent className="p-6 text-center">
              <Store className="w-10 h-10 mx-auto text-[rgb(var(--accent))] mb-3" />
              <h3 className="font-semibold text-foreground mb-2">
                Ready to Trade?
              </h3>
              <p className="text-sm text-muted-foreground mb-4">
                Create a trade quote and get an instant offer estimate from this store
              </p>
              <Link href="/quotes">
                <Button className="gradient-arcane text-white glow-accent w-full">
                  Create Quote
                </Button>
              </Link>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
