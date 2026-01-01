'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import {
  Plus,
  FileText,
  Trash2,
  Loader2,
  Clock,
  CheckCircle,
  Send,
  AlertCircle,
  ChevronRight,
} from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
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
  getQuotes,
  createQuote,
  deleteQuote,
  ApiError,
} from '@/lib/api';
import type { Quote } from '@/lib/api/quotes';

const statusConfig = {
  draft: {
    label: 'Draft',
    icon: FileText,
    color: 'bg-[rgb(var(--muted))]/20 text-muted-foreground border-border',
  },
  submitted: {
    label: 'Submitted',
    icon: Send,
    color: 'bg-[rgb(var(--accent))]/20 text-[rgb(var(--accent))] border-[rgb(var(--accent))]/30',
  },
  completed: {
    label: 'Completed',
    icon: CheckCircle,
    color: 'bg-[rgb(var(--success))]/20 text-[rgb(var(--success))] border-[rgb(var(--success))]/30',
  },
  expired: {
    label: 'Expired',
    icon: Clock,
    color: 'bg-[rgb(var(--destructive))]/20 text-[rgb(var(--destructive))] border-[rgb(var(--destructive))]/30',
  },
};

interface QuoteCardProps {
  quote: Quote;
  onDelete: (id: number) => Promise<void>;
  isDeleting: boolean;
}

function QuoteCard({ quote, onDelete, isDeleting }: QuoteCardProps) {
  const router = useRouter();
  const status = statusConfig[quote.status] || statusConfig.draft;
  const StatusIcon = status.icon;

  const handleClick = () => {
    router.push(`/quotes/${quote.id}`);
  };

  const handleDelete = async (e: React.MouseEvent) => {
    e.stopPropagation();
    if (confirm('Are you sure you want to delete this quote?')) {
      await onDelete(quote.id);
    }
  };

  return (
    <Card
      className="glow-accent transition-all hover:border-[rgb(var(--accent))]/30 cursor-pointer"
      onClick={handleClick}
    >
      <CardContent className="p-4">
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <h3 className="font-heading text-foreground font-medium truncate">
                {quote.name || `Quote #${quote.id}`}
              </h3>
              <Badge className={status.color}>
                <StatusIcon className="w-3 h-3 mr-1" />
                {status.label}
              </Badge>
            </div>

            <div className="mt-2 flex items-center gap-4 text-sm text-muted-foreground">
              <span>{quote.item_count} card{quote.item_count !== 1 ? 's' : ''}</span>
              <span>
                {quote.total_market_value
                  ? formatCurrency(quote.total_market_value)
                  : '$0.00'}
              </span>
              <span>
                Updated {new Date(quote.updated_at).toLocaleDateString()}
              </span>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {quote.status === 'draft' && (
              <Button
                variant="ghost"
                size="sm"
                className="text-muted-foreground hover:text-[rgb(var(--destructive))]"
                onClick={handleDelete}
                disabled={isDeleting}
              >
                {isDeleting ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Trash2 className="w-4 h-4" />
                )}
              </Button>
            )}
            <ChevronRight className="w-5 h-5 text-muted-foreground" />
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

interface NewQuoteDialogProps {
  onCreate: (name?: string) => Promise<void>;
  isCreating: boolean;
}

function NewQuoteDialog({ onCreate, isCreating }: NewQuoteDialogProps) {
  const [name, setName] = useState('');
  const [isOpen, setIsOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async () => {
    setError(null);
    try {
      await onCreate(name || undefined);
      setName('');
      setIsOpen(false);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError('Failed to create quote');
      }
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={setIsOpen}>
      <DialogTrigger asChild>
        <Button className="gradient-arcane text-white glow-accent">
          <Plus className="w-4 h-4 mr-1" />
          New Quote
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Create Trade Quote</DialogTitle>
        </DialogHeader>
        <div className="space-y-4 pt-4">
          <div className="space-y-2">
            <label className="text-sm font-medium text-foreground">
              Quote Name (optional)
            </label>
            <Input
              placeholder="e.g., Commander Staples, Modern Deck"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
            <p className="text-sm text-muted-foreground">
              Give your quote a name to help you remember what it&apos;s for.
            </p>
          </div>

          {error && (
            <p className="text-sm text-[rgb(var(--destructive))]">{error}</p>
          )}

          <div className="flex justify-end gap-2 pt-2">
            <DialogClose asChild>
              <Button variant="secondary">Cancel</Button>
            </DialogClose>
            <Button
              className="gradient-arcane text-white"
              onClick={handleSubmit}
              disabled={isCreating}
            >
              {isCreating ? (
                <>
                  <Loader2 className="w-4 h-4 mr-1 animate-spin" />
                  Creating...
                </>
              ) : (
                'Create Quote'
              )}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

export default function QuotesPage() {
  const router = useRouter();
  const [quotes, setQuotes] = useState<Quote[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [isLoading, setIsLoading] = useState(true);
  const [isCreating, setIsCreating] = useState(false);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [filterStatus, setFilterStatus] = useState<string>('all');

  const fetchQuotes = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      const response = await getQuotes({
        status: filterStatus === 'all' ? undefined : filterStatus,
        page,
        page_size: 20,
      });

      setQuotes(response.items);
      setTotal(response.total);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError('Failed to load quotes');
      }
    } finally {
      setIsLoading(false);
    }
  }, [page, filterStatus]);

  useEffect(() => {
    fetchQuotes();
  }, [fetchQuotes]);

  const handleCreate = async (name?: string) => {
    setIsCreating(true);
    try {
      const newQuote = await createQuote(name);
      // Navigate to the new quote
      router.push(`/quotes/${newQuote.id}`);
    } finally {
      setIsCreating(false);
    }
  };

  const handleDelete = async (id: number) => {
    setDeletingId(id);
    try {
      await deleteQuote(id);
      setQuotes((prev) => prev.filter((q) => q.id !== id));
      setTotal((prev) => prev - 1);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError('Failed to delete quote');
      }
    } finally {
      setDeletingId(null);
    }
  };

  // Count by status
  const draftCount = quotes.filter((q) => q.status === 'draft').length;
  const submittedCount = quotes.filter((q) => q.status === 'submitted').length;

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Loader2 className="w-8 h-8 animate-spin text-[rgb(var(--accent))]" />
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-in">
      <PageHeader
        title="Trade Quotes"
        subtitle="Build trade-in quotes and get offers from local game stores"
      >
        <NewQuoteDialog onCreate={handleCreate} isCreating={isCreating} />
      </PageHeader>

      {error && (
        <div className="p-4 rounded-lg bg-[rgb(var(--destructive))]/10 border border-[rgb(var(--destructive))]/20">
          <div className="flex items-center gap-2">
            <AlertCircle className="w-5 h-5 text-[rgb(var(--destructive))]" />
            <p className="text-[rgb(var(--destructive))]">{error}</p>
          </div>
        </div>
      )}

      {/* Summary Stats */}
      <div className="grid grid-cols-3 gap-4">
        <Card className="glow-accent">
          <CardContent className="p-4 text-center">
            <p className="text-3xl font-bold text-foreground">{total}</p>
            <p className="text-sm text-muted-foreground">Total Quotes</p>
          </CardContent>
        </Card>
        <Card className="glow-accent">
          <CardContent className="p-4 text-center">
            <p className="text-3xl font-bold text-foreground">{draftCount}</p>
            <p className="text-sm text-muted-foreground">Drafts</p>
          </CardContent>
        </Card>
        <Card className="glow-accent">
          <CardContent className="p-4 text-center">
            <p className="text-3xl font-bold text-[rgb(var(--accent))]">
              {submittedCount}
            </p>
            <p className="text-sm text-muted-foreground">Submitted</p>
          </CardContent>
        </Card>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-2">
        <span className="text-sm text-muted-foreground">Status:</span>
        {(['all', 'draft', 'submitted', 'completed'] as const).map((status) => (
          <Button
            key={status}
            variant={filterStatus === status ? 'default' : 'secondary'}
            size="sm"
            onClick={() => {
              setFilterStatus(status);
              setPage(1);
            }}
            className={filterStatus === status ? 'gradient-arcane text-white' : ''}
          >
            {status === 'all' ? 'All' : status.charAt(0).toUpperCase() + status.slice(1)}
          </Button>
        ))}
      </div>

      {/* Quotes List */}
      {quotes.length === 0 ? (
        <Card className="glow-accent">
          <CardContent className="py-12 text-center">
            <FileText className="w-12 h-12 mx-auto text-muted-foreground mb-4" />
            <p className="text-muted-foreground mb-4">
              {filterStatus === 'all'
                ? 'No trade quotes yet. Create one to start building your trade-in list!'
                : `No ${filterStatus} quotes found.`}
            </p>
            {filterStatus === 'all' && (
              <NewQuoteDialog onCreate={handleCreate} isCreating={isCreating} />
            )}
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-3">
          {quotes.map((quote) => (
            <QuoteCard
              key={quote.id}
              quote={quote}
              onDelete={handleDelete}
              isDeleting={deletingId === quote.id}
            />
          ))}
        </div>
      )}

      {/* Pagination */}
      {total > 20 && (
        <div className="flex justify-center gap-2">
          <Button
            variant="secondary"
            disabled={page === 1}
            onClick={() => setPage((p) => p - 1)}
          >
            Previous
          </Button>
          <span className="flex items-center px-4 text-sm text-muted-foreground">
            Page {page} of {Math.ceil(total / 20)}
          </span>
          <Button
            variant="secondary"
            disabled={page >= Math.ceil(total / 20)}
            onClick={() => setPage((p) => p + 1)}
          >
            Next
          </Button>
        </div>
      )}
    </div>
  );
}
