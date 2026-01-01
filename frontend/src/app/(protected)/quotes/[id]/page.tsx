'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useRouter } from 'next/navigation';
import {
  ArrowLeft,
  Plus,
  Trash2,
  Loader2,
  Package,
  Store,
  Send,
  CheckCircle,
  AlertCircle,
  Edit2,
  X,
  Check,
  MapPin,
  DollarSign,
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
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { PageHeader } from '@/components/ornate/page-header';
import { SearchAutocomplete } from '@/components/search/SearchAutocomplete';
import { formatCurrency, cn } from '@/lib/utils';
import {
  getQuote,
  updateQuote,
  addQuoteItem,
  updateQuoteItem,
  deleteQuoteItem,
  getQuoteOffers,
  submitQuote,
  ApiError,
} from '@/lib/api';
import type { Quote, QuoteItem, StoreOffer, QuoteOffersPreview } from '@/lib/api/quotes';

const CONDITIONS = ['NM', 'LP', 'MP', 'HP', 'DMG'];

interface QuoteItemRowProps {
  item: QuoteItem;
  quoteId: number;
  onUpdate: (itemId: number, data: { quantity?: number; condition?: string }) => Promise<void>;
  onDelete: (itemId: number) => Promise<void>;
  isUpdating: boolean;
  isDeleting: boolean;
  disabled: boolean;
}

function QuoteItemRow({
  item,
  quoteId,
  onUpdate,
  onDelete,
  isUpdating,
  isDeleting,
  disabled,
}: QuoteItemRowProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [quantity, setQuantity] = useState(item.quantity.toString());
  const [condition, setCondition] = useState(item.condition);

  const handleSave = async () => {
    const newQty = parseInt(quantity);
    if (isNaN(newQty) || newQty < 1) return;

    await onUpdate(item.id, {
      quantity: newQty !== item.quantity ? newQty : undefined,
      condition: condition !== item.condition ? condition : undefined,
    });
    setIsEditing(false);
  };

  const handleCancel = () => {
    setQuantity(item.quantity.toString());
    setCondition(item.condition);
    setIsEditing(false);
  };

  return (
    <TableRow>
      <TableCell>
        <div>
          <span className="font-medium">{item.card_name}</span>
          {item.set_code && (
            <span className="text-muted-foreground ml-2 text-sm">
              [{item.set_code.toUpperCase()}]
            </span>
          )}
        </div>
      </TableCell>
      <TableCell>
        {isEditing ? (
          <Input
            type="number"
            min="1"
            max="100"
            value={quantity}
            onChange={(e) => setQuantity(e.target.value)}
            className="w-20"
          />
        ) : (
          item.quantity
        )}
      </TableCell>
      <TableCell>
        {isEditing ? (
          <select
            value={condition}
            onChange={(e) => setCondition(e.target.value)}
            className="px-2 py-1 rounded border border-border bg-card text-foreground text-sm"
          >
            {CONDITIONS.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        ) : (
          <Badge variant="outline">{item.condition}</Badge>
        )}
      </TableCell>
      <TableCell className="text-right">
        {item.market_price ? formatCurrency(item.market_price) : '--'}
      </TableCell>
      <TableCell className="text-right font-medium">
        {item.line_total ? formatCurrency(item.line_total) : '--'}
      </TableCell>
      <TableCell>
        <div className="flex items-center justify-end gap-1">
          {isEditing ? (
            <>
              <Button
                variant="ghost"
                size="sm"
                onClick={handleSave}
                disabled={isUpdating}
              >
                {isUpdating ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Check className="w-4 h-4 text-[rgb(var(--success))]" />
                )}
              </Button>
              <Button variant="ghost" size="sm" onClick={handleCancel}>
                <X className="w-4 h-4" />
              </Button>
            </>
          ) : (
            <>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setIsEditing(true)}
                disabled={disabled}
              >
                <Edit2 className="w-4 h-4" />
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => onDelete(item.id)}
                disabled={isDeleting || disabled}
                className="text-muted-foreground hover:text-[rgb(var(--destructive))]"
              >
                {isDeleting ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Trash2 className="w-4 h-4" />
                )}
              </Button>
            </>
          )}
        </div>
      </TableCell>
    </TableRow>
  );
}

interface AddCardDialogProps {
  onAdd: (cardId: number, quantity: number, condition: string) => Promise<void>;
  isAdding: boolean;
}

function AddCardDialog({ onAdd, isAdding }: AddCardDialogProps) {
  const [selectedCard, setSelectedCard] = useState<{
    id: number;
    name: string;
    set_code: string;
  } | null>(null);
  const [quantity, setQuantity] = useState('1');
  const [condition, setCondition] = useState('NM');
  const [isOpen, setIsOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async () => {
    if (!selectedCard) {
      setError('Please select a card');
      return;
    }

    const qty = parseInt(quantity);
    if (isNaN(qty) || qty < 1) {
      setError('Please enter a valid quantity');
      return;
    }

    setError(null);
    try {
      await onAdd(selectedCard.id, qty, condition);
      setSelectedCard(null);
      setQuantity('1');
      setCondition('NM');
      setIsOpen(false);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError('Failed to add card');
      }
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={setIsOpen}>
      <DialogTrigger asChild>
        <Button className="gradient-arcane text-white glow-accent">
          <Plus className="w-4 h-4 mr-1" />
          Add Card
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Add Card to Quote</DialogTitle>
        </DialogHeader>
        <div className="space-y-4 pt-4">
          <div className="space-y-2">
            <label className="text-sm font-medium text-foreground">Card</label>
            {selectedCard ? (
              <div className="flex items-center justify-between p-2 border rounded-lg bg-secondary">
                <div>
                  <p className="font-medium">{selectedCard.name}</p>
                  <p className="text-sm text-muted-foreground">
                    {selectedCard.set_code}
                  </p>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setSelectedCard(null)}
                >
                  Change
                </Button>
              </div>
            ) : (
              <SearchAutocomplete
                placeholder="Search for a card..."
                onSelect={(card) => {
                  setSelectedCard(card);
                  setError(null);
                }}
              />
            )}
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <label className="text-sm font-medium text-foreground">
                Quantity
              </label>
              <Input
                type="number"
                min="1"
                max="100"
                value={quantity}
                onChange={(e) => setQuantity(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium text-foreground">
                Condition
              </label>
              <select
                value={condition}
                onChange={(e) => setCondition(e.target.value)}
                className="w-full px-3 py-2 rounded-lg border border-border bg-card text-foreground"
              >
                {CONDITIONS.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
            </div>
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
              disabled={isAdding}
            >
              {isAdding ? (
                <>
                  <Loader2 className="w-4 h-4 mr-1 animate-spin" />
                  Adding...
                </>
              ) : (
                'Add to Quote'
              )}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

interface OfferCardProps {
  offer: StoreOffer;
  isSelected: boolean;
  onToggle: () => void;
  disabled: boolean;
}

function OfferCard({ offer, isSelected, onToggle, disabled }: OfferCardProps) {
  return (
    <Card
      className={cn(
        'cursor-pointer transition-all',
        isSelected
          ? 'border-[rgb(var(--accent))] bg-[rgb(var(--accent))]/5'
          : 'hover:border-[rgb(var(--accent))]/30',
        disabled && 'opacity-50 cursor-not-allowed'
      )}
      onClick={() => !disabled && onToggle()}
    >
      <CardContent className="p-4">
        <div className="flex items-start justify-between">
          <div>
            <div className="flex items-center gap-2">
              <h4 className="font-heading font-medium">{offer.store_name}</h4>
              {offer.is_verified && (
                <Badge className="bg-[rgb(var(--success))]/20 text-[rgb(var(--success))] border-[rgb(var(--success))]/30">
                  <CheckCircle className="w-3 h-3 mr-1" />
                  Verified
                </Badge>
              )}
            </div>
            {(offer.city || offer.state) && (
              <p className="text-sm text-muted-foreground flex items-center gap-1 mt-1">
                <MapPin className="w-3 h-3" />
                {[offer.city, offer.state].filter(Boolean).join(', ')}
              </p>
            )}
            <p className="text-sm text-muted-foreground mt-1">
              Buylist: {(offer.buylist_margin * 100).toFixed(0)}% of market
            </p>
          </div>
          <div className="text-right">
            <p className="text-2xl font-bold text-[rgb(var(--success))]">
              {formatCurrency(offer.offer_amount)}
            </p>
            {isSelected && (
              <Badge className="mt-1 bg-[rgb(var(--accent))]/20 text-[rgb(var(--accent))]">
                Selected
              </Badge>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

interface SubmitDialogProps {
  offers: QuoteOffersPreview | null;
  selectedStores: number[];
  onSubmit: (storeIds: number[], message?: string) => Promise<void>;
  isSubmitting: boolean;
}

function SubmitDialog({
  offers,
  selectedStores,
  onSubmit,
  isSubmitting,
}: SubmitDialogProps) {
  const [message, setMessage] = useState('');
  const [isOpen, setIsOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const selectedOffers = offers?.offers.filter((o) =>
    selectedStores.includes(o.trading_post_id)
  );

  const handleSubmit = async () => {
    if (selectedStores.length === 0) {
      setError('Please select at least one store');
      return;
    }

    setError(null);
    try {
      await onSubmit(selectedStores, message || undefined);
      setMessage('');
      setIsOpen(false);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError('Failed to submit quote');
      }
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={setIsOpen}>
      <DialogTrigger asChild>
        <Button
          className="gradient-arcane text-white glow-accent"
          disabled={selectedStores.length === 0}
        >
          <Send className="w-4 h-4 mr-1" />
          Submit to {selectedStores.length} Store{selectedStores.length !== 1 ? 's' : ''}
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Submit Quote</DialogTitle>
        </DialogHeader>
        <div className="space-y-4 pt-4">
          <div>
            <h4 className="font-medium mb-2">Selected Stores</h4>
            <div className="space-y-2">
              {selectedOffers?.map((offer) => (
                <div
                  key={offer.trading_post_id}
                  className="flex justify-between p-2 rounded bg-secondary"
                >
                  <span>{offer.store_name}</span>
                  <span className="font-medium text-[rgb(var(--success))]">
                    {formatCurrency(offer.offer_amount)}
                  </span>
                </div>
              ))}
            </div>
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium text-foreground">
              Message to stores (optional)
            </label>
            <textarea
              className="w-full px-3 py-2 rounded-lg border border-border bg-card text-foreground min-h-[80px]"
              placeholder="Any notes about your cards..."
              value={message}
              onChange={(e) => setMessage(e.target.value)}
            />
          </div>

          <div className="p-3 rounded-lg bg-[rgb(var(--warning))]/10 border border-[rgb(var(--warning))]/20">
            <p className="text-sm text-[rgb(var(--warning))]">
              After submitting, stores will review your quote and respond with
              acceptance, counter-offer, or decline. You&apos;ll be notified of
              their response.
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
              disabled={isSubmitting}
            >
              {isSubmitting ? (
                <>
                  <Loader2 className="w-4 h-4 mr-1 animate-spin" />
                  Submitting...
                </>
              ) : (
                'Submit Quote'
              )}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

export default function QuoteDetailPage() {
  const params = useParams();
  const router = useRouter();
  const quoteId = parseInt(params.id as string);

  const [quote, setQuote] = useState<Quote | null>(null);
  const [offers, setOffers] = useState<QuoteOffersPreview | null>(null);
  const [selectedStores, setSelectedStores] = useState<number[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isLoadingOffers, setIsLoadingOffers] = useState(false);
  const [isAdding, setIsAdding] = useState(false);
  const [updatingItemId, setUpdatingItemId] = useState<number | null>(null);
  const [deletingItemId, setDeletingItemId] = useState<number | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isDraft = quote?.status === 'draft';

  const fetchQuote = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      const data = await getQuote(quoteId);
      setQuote(data);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError('Failed to load quote');
      }
    } finally {
      setIsLoading(false);
    }
  }, [quoteId]);

  const fetchOffers = useCallback(async () => {
    if (!quote || quote.items.length === 0) return;

    setIsLoadingOffers(true);
    try {
      const data = await getQuoteOffers(quoteId);
      setOffers(data);
    } catch (err) {
      console.error('Failed to load offers:', err);
    } finally {
      setIsLoadingOffers(false);
    }
  }, [quoteId, quote]);

  useEffect(() => {
    fetchQuote();
  }, [fetchQuote]);

  useEffect(() => {
    if (quote && quote.items.length > 0 && isDraft) {
      fetchOffers();
    }
  }, [quote, isDraft, fetchOffers]);

  const handleAddCard = async (
    cardId: number,
    quantity: number,
    condition: string
  ) => {
    setIsAdding(true);
    try {
      await addQuoteItem(quoteId, { card_id: cardId, quantity, condition });
      await fetchQuote();
    } finally {
      setIsAdding(false);
    }
  };

  const handleUpdateItem = async (
    itemId: number,
    data: { quantity?: number; condition?: string }
  ) => {
    setUpdatingItemId(itemId);
    try {
      await updateQuoteItem(quoteId, itemId, data);
      await fetchQuote();
    } finally {
      setUpdatingItemId(null);
    }
  };

  const handleDeleteItem = async (itemId: number) => {
    setDeletingItemId(itemId);
    try {
      await deleteQuoteItem(quoteId, itemId);
      await fetchQuote();
    } finally {
      setDeletingItemId(null);
    }
  };

  const handleToggleStore = (storeId: number) => {
    setSelectedStores((prev) =>
      prev.includes(storeId)
        ? prev.filter((id) => id !== storeId)
        : [...prev, storeId].slice(0, 5) // Max 5 stores
    );
  };

  const handleSubmit = async (storeIds: number[], message?: string) => {
    setIsSubmitting(true);
    try {
      await submitQuote(quoteId, { trading_post_ids: storeIds, message });
      router.push('/quotes');
    } finally {
      setIsSubmitting(false);
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Loader2 className="w-8 h-8 animate-spin text-[rgb(var(--accent))]" />
      </div>
    );
  }

  if (error || !quote) {
    return (
      <div className="space-y-6">
        <Button variant="ghost" onClick={() => router.push('/quotes')}>
          <ArrowLeft className="w-4 h-4 mr-2" />
          Back to Quotes
        </Button>
        <Card className="glow-accent">
          <CardContent className="py-12 text-center">
            <AlertCircle className="w-12 h-12 mx-auto text-[rgb(var(--destructive))] mb-4" />
            <p className="text-[rgb(var(--destructive))]">
              {error || 'Quote not found'}
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-in">
      <div className="flex items-center gap-4">
        <Button variant="ghost" onClick={() => router.push('/quotes')}>
          <ArrowLeft className="w-4 h-4 mr-2" />
          Back
        </Button>
        <PageHeader
          title={quote.name || `Quote #${quote.id}`}
          subtitle={`${quote.item_count} cards - ${quote.total_market_value ? formatCurrency(quote.total_market_value) : '$0.00'} market value`}
        >
          {isDraft && (
            <AddCardDialog onAdd={handleAddCard} isAdding={isAdding} />
          )}
        </PageHeader>
      </div>

      {/* Quote Items */}
      <Card className="glow-accent">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Package className="w-5 h-5" />
            Cards in Quote
          </CardTitle>
        </CardHeader>
        <CardContent>
          {quote.items.length === 0 ? (
            <div className="py-8 text-center text-muted-foreground">
              <Package className="w-12 h-12 mx-auto mb-4 opacity-50" />
              <p>No cards in this quote yet.</p>
              <p className="text-sm mt-1">
                Add cards to see offers from local stores.
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto -mx-6 px-6">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Card</TableHead>
                    <TableHead>Qty</TableHead>
                    <TableHead>Condition</TableHead>
                    <TableHead className="text-right">Price</TableHead>
                    <TableHead className="text-right">Total</TableHead>
                    <TableHead className="w-24"></TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {quote.items.map((item) => (
                    <QuoteItemRow
                      key={item.id}
                      item={item}
                      quoteId={quoteId}
                      onUpdate={handleUpdateItem}
                      onDelete={handleDeleteItem}
                      isUpdating={updatingItemId === item.id}
                      isDeleting={deletingItemId === item.id}
                      disabled={!isDraft}
                    />
                  ))}
                </TableBody>
              </Table>
            </div>
          )}

          {quote.items.length > 0 && (
            <div className="mt-4 pt-4 border-t border-border flex justify-end">
              <div className="text-right">
                <p className="text-sm text-muted-foreground">Total Market Value</p>
                <p className="text-2xl font-bold text-foreground">
                  {quote.total_market_value
                    ? formatCurrency(quote.total_market_value)
                    : '$0.00'}
                </p>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Store Offers */}
      {isDraft && quote.items.length > 0 && (
        <Card className="glow-accent">
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle className="flex items-center gap-2">
                <Store className="w-5 h-5" />
                Store Offers
              </CardTitle>
              {offers && (
                <SubmitDialog
                  offers={offers}
                  selectedStores={selectedStores}
                  onSubmit={handleSubmit}
                  isSubmitting={isSubmitting}
                />
              )}
            </div>
          </CardHeader>
          <CardContent>
            {isLoadingOffers ? (
              <div className="py-8 text-center">
                <Loader2 className="w-8 h-8 animate-spin mx-auto text-[rgb(var(--accent))]" />
                <p className="text-muted-foreground mt-2">Loading offers...</p>
              </div>
            ) : offers && offers.offers.length > 0 ? (
              <div className="space-y-3">
                <p className="text-sm text-muted-foreground mb-4">
                  Select up to 5 stores to submit your quote. They&apos;ll review
                  and respond with their offer.
                </p>
                {offers.offers.map((offer) => (
                  <OfferCard
                    key={offer.trading_post_id}
                    offer={offer}
                    isSelected={selectedStores.includes(offer.trading_post_id)}
                    onToggle={() => handleToggleStore(offer.trading_post_id)}
                    disabled={
                      !selectedStores.includes(offer.trading_post_id) &&
                      selectedStores.length >= 5
                    }
                  />
                ))}
              </div>
            ) : (
              <div className="py-8 text-center text-muted-foreground">
                <Store className="w-12 h-12 mx-auto mb-4 opacity-50" />
                <p>No stores available in your area.</p>
                <p className="text-sm mt-1">
                  Check back later or try a different location.
                </p>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Submitted Status */}
      {quote.status === 'submitted' && (
        <Card className="border-[rgb(var(--accent))]/50 bg-[rgb(var(--accent))]/5">
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <Send className="w-5 h-5 text-[rgb(var(--accent))]" />
              <div>
                <h3 className="font-medium text-[rgb(var(--accent))]">
                  Quote Submitted
                </h3>
                <p className="text-sm text-muted-foreground">
                  Your quote has been submitted to stores. Check your submissions
                  page for responses.
                </p>
              </div>
              <Button
                variant="outline"
                className="ml-auto"
                onClick={() => router.push('/quotes/submissions')}
              >
                View Submissions
              </Button>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
