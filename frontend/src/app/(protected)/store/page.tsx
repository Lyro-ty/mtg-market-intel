'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import {
  Store,
  Plus,
  Edit2,
  Calendar,
  DollarSign,
  MapPin,
  Globe,
  Phone,
  Clock,
  CheckCircle,
  AlertCircle,
  Loader2,
  FileText,
  Users,
  TrendingUp,
  ExternalLink,
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { PageHeader } from '@/components/ornate/page-header';
import { formatCurrency, cn, safeToFixed } from '@/lib/utils';
import {
  getMyTradingPost,
  getStoreSubmissions,
  getMyEvents,
  ApiError,
} from '@/lib/api';
import type { TradingPost, StoreSubmission, TradingPostEvent } from '@/lib/api/trading-posts';

interface StoreDashboardProps {
  store: TradingPost;
  submissions: StoreSubmission[];
  events: TradingPostEvent[];
  onRefresh: () => void;
}

function StoreDashboard({ store, submissions, events, onRefresh }: StoreDashboardProps) {
  const router = useRouter();

  const pendingSubmissions = submissions.filter((s) => s.status === 'pending');
  const upcomingEvents = events.filter(
    (e) => new Date(e.start_time) > new Date()
  );

  // Calculate potential revenue from pending quotes
  const potentialRevenue = pendingSubmissions.reduce(
    (sum, s) => sum + (s.quote_total_value || 0) * store.buylist_margin,
    0
  );

  return (
    <div className="space-y-6 animate-in">
      <PageHeader
        title={store.store_name}
        subtitle="Manage your Trading Post profile and incoming quotes"
      >
        <Button
          variant="outline"
          onClick={() => router.push('/store/edit')}
        >
          <Edit2 className="w-4 h-4 mr-2" />
          Edit Profile
        </Button>
      </PageHeader>

      {/* Verification Status */}
      {!store.is_email_verified && (
        <Card className="border-[rgb(var(--warning))]/50 bg-[rgb(var(--warning))]/5">
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <AlertCircle className="w-5 h-5 text-[rgb(var(--warning))]" />
              <div>
                <h3 className="font-medium text-[rgb(var(--warning))]">
                  Email Verification Pending
                </h3>
                <p className="text-sm text-muted-foreground">
                  Your store won&apos;t appear in search results until your email is verified.
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {store.is_verified && (
        <Card className="border-[rgb(var(--success))]/50 bg-[rgb(var(--success))]/5">
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <CheckCircle className="w-5 h-5 text-[rgb(var(--success))]" />
              <div>
                <h3 className="font-medium text-[rgb(var(--success))]">
                  Verified Trading Post
                </h3>
                <p className="text-sm text-muted-foreground">
                  Your store has been verified and displays a trust badge.
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Stats Grid */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <Card className="glow-accent">
          <CardContent className="p-4 text-center">
            <FileText className="w-6 h-6 mx-auto text-[rgb(var(--accent))] mb-2" />
            <p className="text-3xl font-bold text-foreground">
              {pendingSubmissions.length}
            </p>
            <p className="text-sm text-muted-foreground">Pending Quotes</p>
          </CardContent>
        </Card>
        <Card className="glow-accent">
          <CardContent className="p-4 text-center">
            <DollarSign className="w-6 h-6 mx-auto text-[rgb(var(--success))] mb-2" />
            <p className="text-3xl font-bold text-[rgb(var(--success))]">
              {formatCurrency(potentialRevenue)}
            </p>
            <p className="text-sm text-muted-foreground">Potential Value</p>
          </CardContent>
        </Card>
        <Card className="glow-accent">
          <CardContent className="p-4 text-center">
            <Calendar className="w-6 h-6 mx-auto text-[rgb(var(--accent))] mb-2" />
            <p className="text-3xl font-bold text-foreground">
              {upcomingEvents.length}
            </p>
            <p className="text-sm text-muted-foreground">Upcoming Events</p>
          </CardContent>
        </Card>
        <Card className="glow-accent">
          <CardContent className="p-4 text-center">
            <TrendingUp className="w-6 h-6 mx-auto text-[rgb(var(--accent))] mb-2" />
            <p className="text-3xl font-bold text-foreground">
              {safeToFixed(store.buylist_margin * 100, 0)}%
            </p>
            <p className="text-sm text-muted-foreground">Buylist Rate</p>
          </CardContent>
        </Card>
      </div>

      {/* Quick Actions */}
      <div className="grid md:grid-cols-2 gap-4">
        {/* Pending Quotes */}
        <Card className="glow-accent">
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle className="flex items-center gap-2">
                <FileText className="w-5 h-5" />
                Incoming Quotes
              </CardTitle>
              <Button
                variant="outline"
                size="sm"
                onClick={() => router.push('/store/submissions')}
              >
                View All
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            {pendingSubmissions.length === 0 ? (
              <p className="text-muted-foreground text-center py-4">
                No pending quotes. They&apos;ll appear here when users submit.
              </p>
            ) : (
              <div className="space-y-2">
                {pendingSubmissions.slice(0, 3).map((sub) => (
                  <div
                    key={sub.id}
                    className="flex items-center justify-between p-2 rounded bg-secondary cursor-pointer hover:bg-secondary/80"
                    onClick={() => router.push('/store/submissions')}
                  >
                    <div>
                      <p className="font-medium">
                        {sub.quote_name || `Quote #${sub.quote_id}`}
                      </p>
                      <p className="text-sm text-muted-foreground">
                        {sub.quote_item_count} cards
                      </p>
                    </div>
                    <p className="font-medium text-[rgb(var(--success))]">
                      {formatCurrency(sub.offer_amount)}
                    </p>
                  </div>
                ))}
                {pendingSubmissions.length > 3 && (
                  <p className="text-sm text-muted-foreground text-center">
                    +{pendingSubmissions.length - 3} more
                  </p>
                )}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Upcoming Events */}
        <Card className="glow-accent">
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle className="flex items-center gap-2">
                <Calendar className="w-5 h-5" />
                Upcoming Events
              </CardTitle>
              <Button
                variant="outline"
                size="sm"
                onClick={() => router.push('/store/events')}
              >
                Manage
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            {upcomingEvents.length === 0 ? (
              <div className="text-center py-4">
                <p className="text-muted-foreground mb-2">No upcoming events.</p>
                <Button
                  size="sm"
                  onClick={() => router.push('/store/events')}
                >
                  <Plus className="w-4 h-4 mr-1" />
                  Create Event
                </Button>
              </div>
            ) : (
              <div className="space-y-2">
                {upcomingEvents.slice(0, 3).map((event) => (
                  <div
                    key={event.id}
                    className="flex items-center justify-between p-2 rounded bg-secondary"
                  >
                    <div>
                      <p className="font-medium">{event.title}</p>
                      <p className="text-sm text-muted-foreground">
                        {new Date(event.start_time).toLocaleDateString()}
                        {event.format && ` - ${event.format}`}
                      </p>
                    </div>
                    <Badge variant="outline">{event.event_type}</Badge>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Store Info */}
      <Card className="glow-accent">
        <CardHeader>
          <CardTitle>Store Information</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid md:grid-cols-2 gap-4">
            {store.address && (
              <div className="flex items-start gap-3">
                <MapPin className="w-5 h-5 text-muted-foreground shrink-0 mt-0.5" />
                <div>
                  <p className="text-sm text-muted-foreground">Address</p>
                  <p>
                    {store.address}
                    {store.city && `, ${store.city}`}
                    {store.state && `, ${store.state}`}
                    {store.postal_code && ` ${store.postal_code}`}
                  </p>
                </div>
              </div>
            )}

            {store.phone && (
              <div className="flex items-start gap-3">
                <Phone className="w-5 h-5 text-muted-foreground shrink-0 mt-0.5" />
                <div>
                  <p className="text-sm text-muted-foreground">Phone</p>
                  <p>{store.phone}</p>
                </div>
              </div>
            )}

            {store.website && (
              <div className="flex items-start gap-3">
                <Globe className="w-5 h-5 text-muted-foreground shrink-0 mt-0.5" />
                <div>
                  <p className="text-sm text-muted-foreground">Website</p>
                  <a
                    href={store.website}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-[rgb(var(--accent))] hover:underline flex items-center gap-1"
                  >
                    {store.website.replace(/^https?:\/\//, '')}
                    <ExternalLink className="w-3 h-3" />
                  </a>
                </div>
              </div>
            )}

            {store.services && store.services.length > 0 && (
              <div className="flex items-start gap-3">
                <Store className="w-5 h-5 text-muted-foreground shrink-0 mt-0.5" />
                <div>
                  <p className="text-sm text-muted-foreground">Services</p>
                  <div className="flex flex-wrap gap-1 mt-1">
                    {store.services.map((service) => (
                      <Badge key={service} variant="secondary">
                        {service}
                      </Badge>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </div>

          {store.description && (
            <div className="mt-4 pt-4 border-t border-border">
              <p className="text-sm text-muted-foreground mb-1">Description</p>
              <p>{store.description}</p>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function RegisterPrompt() {
  const router = useRouter();

  return (
    <div className="space-y-6 animate-in">
      <PageHeader
        title="Trading Post"
        subtitle="Register your local game store to receive trade-in quotes"
      />

      <Card className="glow-accent max-w-2xl mx-auto">
        <CardContent className="py-12 text-center">
          <Store className="w-16 h-16 mx-auto text-[rgb(var(--accent))] mb-6" />
          <h2 className="text-2xl font-heading font-bold mb-4">
            Become a Trading Post
          </h2>
          <p className="text-muted-foreground mb-6 max-w-md mx-auto">
            Register your local game store to receive trade-in quotes from collectors.
            Set your buylist margin and let customers come to you!
          </p>

          <div className="grid md:grid-cols-3 gap-4 mb-8 text-left max-w-lg mx-auto">
            <div className="p-4 rounded-lg bg-secondary">
              <FileText className="w-6 h-6 text-[rgb(var(--accent))] mb-2" />
              <h3 className="font-medium mb-1">Receive Quotes</h3>
              <p className="text-sm text-muted-foreground">
                Users build trade-in lists and submit them to you
              </p>
            </div>
            <div className="p-4 rounded-lg bg-secondary">
              <DollarSign className="w-6 h-6 text-[rgb(var(--accent))] mb-2" />
              <h3 className="font-medium mb-1">Set Your Rate</h3>
              <p className="text-sm text-muted-foreground">
                Configure your buylist margin (% of market)
              </p>
            </div>
            <div className="p-4 rounded-lg bg-secondary">
              <Calendar className="w-6 h-6 text-[rgb(var(--accent))] mb-2" />
              <h3 className="font-medium mb-1">Promote Events</h3>
              <p className="text-sm text-muted-foreground">
                List tournaments and events for local players
              </p>
            </div>
          </div>

          <Button
            size="lg"
            className="gradient-arcane text-white glow-accent"
            onClick={() => router.push('/store/register')}
          >
            <Plus className="w-5 h-5 mr-2" />
            Register Your Store
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}

export default function StorePage() {
  const [store, setStore] = useState<TradingPost | null>(null);
  const [submissions, setSubmissions] = useState<StoreSubmission[]>([]);
  const [events, setEvents] = useState<TradingPostEvent[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [hasStore, setHasStore] = useState<boolean | null>(null);

  const fetchData = useCallback(async () => {
    setIsLoading(true);

    try {
      const storeData = await getMyTradingPost();
      setStore(storeData);
      setHasStore(true);

      // Fetch submissions and events in parallel
      const [subsData, eventsData] = await Promise.all([
        getStoreSubmissions(),
        getMyEvents(),
      ]);

      setSubmissions(subsData.items);
      setEvents(eventsData.items);
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) {
        setHasStore(false);
      } else {
        console.error('Failed to load store data:', err);
      }
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Loader2 className="w-8 h-8 animate-spin text-[rgb(var(--accent))]" />
      </div>
    );
  }

  if (!hasStore) {
    return <RegisterPrompt />;
  }

  if (!store) {
    return null;
  }

  return (
    <StoreDashboard
      store={store}
      submissions={submissions}
      events={events}
      onRefresh={fetchData}
    />
  );
}
