'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import {
  ArrowLeft,
  Plus,
  Calendar,
  Clock,
  Users,
  DollarSign,
  Trash2,
  Edit2,
  Loader2,
  AlertCircle,
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
  DialogClose,
} from '@/components/ui/dialog';
import { PageHeader } from '@/components/ornate/page-header';
import { formatCurrency, cn } from '@/lib/utils';
import {
  getMyEvents,
  createEvent,
  updateEvent,
  deleteEvent,
  ApiError,
} from '@/lib/api';
import type { TradingPostEvent, EventCreate } from '@/lib/api/trading-posts';

const EVENT_TYPES = [
  { value: 'tournament', label: 'Tournament' },
  { value: 'sale', label: 'Sale' },
  { value: 'release', label: 'Release Event' },
  { value: 'meetup', label: 'Meetup' },
];

const FORMATS = [
  'Standard',
  'Modern',
  'Legacy',
  'Vintage',
  'Commander',
  'Pioneer',
  'Pauper',
  'Draft',
  'Sealed',
  'Two-Headed Giant',
  'Other',
];

const eventTypeColors: Record<string, string> = {
  tournament: 'bg-[rgb(var(--accent))]/20 text-[rgb(var(--accent))] border-[rgb(var(--accent))]/30',
  sale: 'bg-[rgb(var(--success))]/20 text-[rgb(var(--success))] border-[rgb(var(--success))]/30',
  release: 'bg-[rgb(var(--warning))]/20 text-[rgb(var(--warning))] border-[rgb(var(--warning))]/30',
  meetup: 'bg-[rgb(var(--muted))]/20 text-muted-foreground border-border',
};

interface EventFormProps {
  event?: TradingPostEvent;
  onSubmit: (data: EventCreate) => Promise<void>;
  onCancel: () => void;
  isSubmitting: boolean;
}

function EventForm({ event, onSubmit, onCancel, isSubmitting }: EventFormProps) {
  const [title, setTitle] = useState(event?.title || '');
  const [description, setDescription] = useState(event?.description || '');
  const [eventType, setEventType] = useState<EventCreate['event_type']>(
    (event?.event_type as EventCreate['event_type']) || 'tournament'
  );
  const [format, setFormat] = useState(event?.format || '');
  const [startTime, setStartTime] = useState(
    event?.start_time
      ? new Date(event.start_time).toISOString().slice(0, 16)
      : ''
  );
  const [endTime, setEndTime] = useState(
    event?.end_time
      ? new Date(event.end_time).toISOString().slice(0, 16)
      : ''
  );
  const [entryFee, setEntryFee] = useState(
    event?.entry_fee?.toString() || ''
  );
  const [maxPlayers, setMaxPlayers] = useState(
    event?.max_players?.toString() || ''
  );
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!title.trim()) {
      setError('Title is required');
      return;
    }

    if (!startTime) {
      setError('Start time is required');
      return;
    }

    try {
      await onSubmit({
        title: title.trim(),
        description: description.trim() || undefined,
        event_type: eventType,
        format: format || undefined,
        start_time: new Date(startTime).toISOString(),
        end_time: endTime ? new Date(endTime).toISOString() : undefined,
        entry_fee: entryFee ? parseFloat(entryFee) : undefined,
        max_players: maxPlayers ? parseInt(maxPlayers) : undefined,
      });
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError('Failed to save event');
      }
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="space-y-2">
        <label className="text-sm font-medium text-foreground">
          Event Title <span className="text-[rgb(var(--destructive))]">*</span>
        </label>
        <Input
          placeholder="Friday Night Magic"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          required
        />
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-2">
          <label className="text-sm font-medium text-foreground">
            Event Type
          </label>
          <select
            className="w-full px-3 py-2 rounded-lg border border-border bg-card text-foreground"
            value={eventType}
            onChange={(e) => setEventType(e.target.value as EventCreate['event_type'])}
          >
            {EVENT_TYPES.map((type) => (
              <option key={type.value} value={type.value}>
                {type.label}
              </option>
            ))}
          </select>
        </div>
        <div className="space-y-2">
          <label className="text-sm font-medium text-foreground">Format</label>
          <select
            className="w-full px-3 py-2 rounded-lg border border-border bg-card text-foreground"
            value={format}
            onChange={(e) => setFormat(e.target.value)}
          >
            <option value="">Select Format</option>
            {FORMATS.map((f) => (
              <option key={f} value={f.toLowerCase()}>
                {f}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-2">
          <label className="text-sm font-medium text-foreground">
            Start Time <span className="text-[rgb(var(--destructive))]">*</span>
          </label>
          <Input
            type="datetime-local"
            value={startTime}
            onChange={(e) => setStartTime(e.target.value)}
            required
          />
        </div>
        <div className="space-y-2">
          <label className="text-sm font-medium text-foreground">
            End Time
          </label>
          <Input
            type="datetime-local"
            value={endTime}
            onChange={(e) => setEndTime(e.target.value)}
          />
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-2">
          <label className="text-sm font-medium text-foreground">
            Entry Fee ($)
          </label>
          <Input
            type="number"
            min="0"
            step="0.01"
            placeholder="0.00"
            value={entryFee}
            onChange={(e) => setEntryFee(e.target.value)}
          />
        </div>
        <div className="space-y-2">
          <label className="text-sm font-medium text-foreground">
            Max Players
          </label>
          <Input
            type="number"
            min="1"
            placeholder="No limit"
            value={maxPlayers}
            onChange={(e) => setMaxPlayers(e.target.value)}
          />
        </div>
      </div>

      <div className="space-y-2">
        <label className="text-sm font-medium text-foreground">
          Description
        </label>
        <textarea
          className="w-full px-3 py-2 rounded-lg border border-border bg-card text-foreground min-h-[80px]"
          placeholder="Event details, prizes, etc..."
          value={description}
          onChange={(e) => setDescription(e.target.value)}
        />
      </div>

      {error && (
        <p className="text-sm text-[rgb(var(--destructive))]">{error}</p>
      )}

      <div className="flex justify-end gap-2 pt-2">
        <Button type="button" variant="secondary" onClick={onCancel}>
          Cancel
        </Button>
        <Button
          type="submit"
          className="gradient-arcane text-white"
          disabled={isSubmitting}
        >
          {isSubmitting ? (
            <>
              <Loader2 className="w-4 h-4 mr-1 animate-spin" />
              Saving...
            </>
          ) : event ? (
            'Update Event'
          ) : (
            'Create Event'
          )}
        </Button>
      </div>
    </form>
  );
}

interface EventCardProps {
  event: TradingPostEvent;
  onEdit: () => void;
  onDelete: () => void;
  isDeleting: boolean;
}

function EventCard({ event, onEdit, onDelete, isDeleting }: EventCardProps) {
  const isPast = new Date(event.start_time) < new Date();
  const typeColor = eventTypeColors[event.event_type] || eventTypeColors.meetup;

  return (
    <Card className={cn('glow-accent', isPast && 'opacity-60')}>
      <CardContent className="p-4">
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1">
            <div className="flex items-center gap-2 mb-2">
              <h3 className="font-heading font-medium">{event.title}</h3>
              <Badge className={typeColor}>{event.event_type}</Badge>
              {event.format && (
                <Badge variant="outline">{event.format}</Badge>
              )}
            </div>

            <div className="flex items-center gap-4 text-sm text-muted-foreground">
              <span className="flex items-center gap-1">
                <Calendar className="w-4 h-4" />
                {new Date(event.start_time).toLocaleDateString()}
              </span>
              <span className="flex items-center gap-1">
                <Clock className="w-4 h-4" />
                {new Date(event.start_time).toLocaleTimeString([], {
                  hour: '2-digit',
                  minute: '2-digit',
                })}
              </span>
              {event.entry_fee && (
                <span className="flex items-center gap-1">
                  <DollarSign className="w-4 h-4" />
                  {formatCurrency(event.entry_fee)}
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
              <p className="mt-2 text-sm text-muted-foreground line-clamp-2">
                {event.description}
              </p>
            )}
          </div>

          {!isPast && (
            <div className="flex items-center gap-1">
              <Button variant="ghost" size="sm" onClick={onEdit}>
                <Edit2 className="w-4 h-4" />
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={onDelete}
                disabled={isDeleting}
                className="text-muted-foreground hover:text-[rgb(var(--destructive))]"
              >
                {isDeleting ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Trash2 className="w-4 h-4" />
                )}
              </Button>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

export default function StoreEventsPage() {
  const router = useRouter();
  const [events, setEvents] = useState<TradingPostEvent[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [editingEvent, setEditingEvent] = useState<TradingPostEvent | null>(null);
  const [includePast, setIncludePast] = useState(false);

  const fetchEvents = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      const response = await getMyEvents({ include_past: includePast });
      setEvents(response.items);
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.status === 403) {
          router.push('/store/register');
          return;
        }
        setError(err.message);
      } else {
        setError('Failed to load events');
      }
    } finally {
      setIsLoading(false);
    }
  }, [includePast, router]);

  useEffect(() => {
    fetchEvents();
  }, [fetchEvents]);

  const handleCreate = async (data: EventCreate) => {
    setIsSubmitting(true);
    try {
      await createEvent(data);
      setShowCreateDialog(false);
      await fetchEvents();
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleUpdate = async (data: EventCreate) => {
    if (!editingEvent) return;

    setIsSubmitting(true);
    try {
      await updateEvent(editingEvent.id, data);
      setEditingEvent(null);
      await fetchEvents();
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm('Are you sure you want to delete this event?')) return;

    setDeletingId(id);
    try {
      await deleteEvent(id);
      await fetchEvents();
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError('Failed to delete event');
      }
    } finally {
      setDeletingId(null);
    }
  };

  const upcomingEvents = events.filter(
    (e) => new Date(e.start_time) >= new Date()
  );
  const pastEvents = events.filter(
    (e) => new Date(e.start_time) < new Date()
  );

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Loader2 className="w-8 h-8 animate-spin text-[rgb(var(--accent))]" />
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-in">
      <div className="flex items-center gap-4">
        <Button variant="ghost" onClick={() => router.push('/store')}>
          <ArrowLeft className="w-4 h-4 mr-2" />
          Back
        </Button>
        <PageHeader
          title="Store Events"
          subtitle="Manage your tournaments and events"
        >
          <Dialog open={showCreateDialog} onOpenChange={setShowCreateDialog}>
            <DialogTrigger asChild>
              <Button className="gradient-arcane text-white glow-accent">
                <Plus className="w-4 h-4 mr-1" />
                Create Event
              </Button>
            </DialogTrigger>
            <DialogContent className="sm:max-w-lg">
              <DialogHeader>
                <DialogTitle>Create Event</DialogTitle>
              </DialogHeader>
              <EventForm
                onSubmit={handleCreate}
                onCancel={() => setShowCreateDialog(false)}
                isSubmitting={isSubmitting}
              />
            </DialogContent>
          </Dialog>
        </PageHeader>
      </div>

      {error && (
        <div className="p-4 rounded-lg bg-[rgb(var(--destructive))]/10 border border-[rgb(var(--destructive))]/20">
          <div className="flex items-center gap-2">
            <AlertCircle className="w-5 h-5 text-[rgb(var(--destructive))]" />
            <p className="text-[rgb(var(--destructive))]">{error}</p>
          </div>
        </div>
      )}

      {/* Edit Dialog */}
      <Dialog
        open={!!editingEvent}
        onOpenChange={(open) => !open && setEditingEvent(null)}
      >
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>Edit Event</DialogTitle>
          </DialogHeader>
          {editingEvent && (
            <EventForm
              event={editingEvent}
              onSubmit={handleUpdate}
              onCancel={() => setEditingEvent(null)}
              isSubmitting={isSubmitting}
            />
          )}
        </DialogContent>
      </Dialog>

      {/* Stats */}
      <div className="grid grid-cols-2 gap-4">
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
            <Clock className="w-6 h-6 mx-auto text-muted-foreground mb-2" />
            <p className="text-3xl font-bold text-muted-foreground">
              {pastEvents.length}
            </p>
            <p className="text-sm text-muted-foreground">Past Events</p>
          </CardContent>
        </Card>
      </div>

      {/* Include Past Toggle */}
      <div className="flex items-center gap-2">
        <input
          type="checkbox"
          id="includePast"
          checked={includePast}
          onChange={(e) => setIncludePast(e.target.checked)}
          className="rounded"
        />
        <label htmlFor="includePast" className="text-sm text-muted-foreground">
          Show past events
        </label>
      </div>

      {/* Events List */}
      {events.length === 0 ? (
        <Card className="glow-accent">
          <CardContent className="py-12 text-center">
            <Calendar className="w-12 h-12 mx-auto text-muted-foreground mb-4" />
            <p className="text-muted-foreground mb-4">
              No events yet. Create your first event to attract local players!
            </p>
            <Button
              className="gradient-arcane text-white"
              onClick={() => setShowCreateDialog(true)}
            >
              <Plus className="w-4 h-4 mr-1" />
              Create Event
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-3">
          {events.map((event) => (
            <EventCard
              key={event.id}
              event={event}
              onEdit={() => setEditingEvent(event)}
              onDelete={() => handleDelete(event.id)}
              isDeleting={deletingId === event.id}
            />
          ))}
        </div>
      )}
    </div>
  );
}
