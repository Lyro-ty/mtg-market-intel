'use client';

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import {
  ArrowLeft,
  Store,
  MapPin,
  Phone,
  Globe,
  DollarSign,
  Loader2,
  AlertCircle,
  Info,
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { PageHeader } from '@/components/ornate/page-header';
import { registerTradingPost, ApiError } from '@/lib/api';
import { safeToFixed } from '@/lib/utils';

const US_STATES = [
  'AL', 'AK', 'AZ', 'AR', 'CA', 'CO', 'CT', 'DE', 'FL', 'GA',
  'HI', 'ID', 'IL', 'IN', 'IA', 'KS', 'KY', 'LA', 'ME', 'MD',
  'MA', 'MI', 'MN', 'MS', 'MO', 'MT', 'NE', 'NV', 'NH', 'NJ',
  'NM', 'NY', 'NC', 'ND', 'OH', 'OK', 'OR', 'PA', 'RI', 'SC',
  'SD', 'TN', 'TX', 'UT', 'VT', 'VA', 'WA', 'WV', 'WI', 'WY',
];

const SERVICES = [
  'Singles',
  'Sealed Product',
  'Buylist',
  'Tournaments',
  'Commander Nights',
  'Draft Events',
  'Pre-releases',
  'Card Grading',
];

export default function RegisterStorePage() {
  const router = useRouter();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Form state
  const [storeName, setStoreName] = useState('');
  const [description, setDescription] = useState('');
  const [address, setAddress] = useState('');
  const [city, setCity] = useState('');
  const [state, setState] = useState('');
  const [postalCode, setPostalCode] = useState('');
  const [phone, setPhone] = useState('');
  const [website, setWebsite] = useState('');
  const [buylistMargin, setBuylistMargin] = useState('50');
  const [selectedServices, setSelectedServices] = useState<string[]>([]);

  const toggleService = (service: string) => {
    setSelectedServices((prev) =>
      prev.includes(service)
        ? prev.filter((s) => s !== service)
        : [...prev, service]
    );
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!storeName.trim()) {
      setError('Store name is required');
      return;
    }

    const margin = parseFloat(buylistMargin);
    if (isNaN(margin) || margin < 1 || margin > 99) {
      setError('Buylist margin must be between 1% and 99%');
      return;
    }

    setIsSubmitting(true);

    try {
      await registerTradingPost({
        store_name: storeName.trim(),
        description: description.trim() || undefined,
        address: address.trim() || undefined,
        city: city.trim() || undefined,
        state: state || undefined,
        country: 'US',
        postal_code: postalCode.trim() || undefined,
        phone: phone.trim() || undefined,
        website: website.trim() || undefined,
        services: selectedServices.length > 0 ? selectedServices : undefined,
        buylist_margin: margin / 100,
      });

      router.push('/store');
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError('Failed to register store. Please try again.');
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="space-y-6 animate-in">
      <div className="flex items-center gap-4">
        <Button variant="ghost" onClick={() => router.push('/store')}>
          <ArrowLeft className="w-4 h-4 mr-2" />
          Back
        </Button>
        <PageHeader
          title="Register Trading Post"
          subtitle="Set up your local game store profile"
        />
      </div>

      <form onSubmit={handleSubmit} className="max-w-2xl mx-auto space-y-6">
        {error && (
          <div className="p-4 rounded-lg bg-[rgb(var(--destructive))]/10 border border-[rgb(var(--destructive))]/20">
            <div className="flex items-center gap-2">
              <AlertCircle className="w-5 h-5 text-[rgb(var(--destructive))]" />
              <p className="text-[rgb(var(--destructive))]">{error}</p>
            </div>
          </div>
        )}

        {/* Basic Info */}
        <Card className="glow-accent">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Store className="w-5 h-5" />
              Store Information
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <label className="text-sm font-medium text-foreground">
                Store Name <span className="text-[rgb(var(--destructive))]">*</span>
              </label>
              <Input
                placeholder="e.g., Dragon's Lair Games"
                value={storeName}
                onChange={(e) => setStoreName(e.target.value)}
                required
              />
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium text-foreground">
                Description
              </label>
              <textarea
                className="w-full px-3 py-2 rounded-lg border border-border bg-card text-foreground min-h-[100px]"
                placeholder="Tell customers about your store..."
                value={description}
                onChange={(e) => setDescription(e.target.value)}
              />
            </div>
          </CardContent>
        </Card>

        {/* Location */}
        <Card className="glow-accent">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <MapPin className="w-5 h-5" />
              Location
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <label className="text-sm font-medium text-foreground">
                Street Address
              </label>
              <Input
                placeholder="123 Main Street"
                value={address}
                onChange={(e) => setAddress(e.target.value)}
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <label className="text-sm font-medium text-foreground">
                  City
                </label>
                <Input
                  placeholder="City"
                  value={city}
                  onChange={(e) => setCity(e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium text-foreground">
                  State
                </label>
                <select
                  className="w-full px-3 py-2 rounded-lg border border-border bg-card text-foreground"
                  value={state}
                  onChange={(e) => setState(e.target.value)}
                >
                  <option value="">Select State</option>
                  {US_STATES.map((s) => (
                    <option key={s} value={s}>
                      {s}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium text-foreground">
                ZIP Code
              </label>
              <Input
                placeholder="12345"
                value={postalCode}
                onChange={(e) => setPostalCode(e.target.value)}
                maxLength={10}
                className="max-w-[150px]"
              />
            </div>
          </CardContent>
        </Card>

        {/* Contact */}
        <Card className="glow-accent">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Phone className="w-5 h-5" />
              Contact Information
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <label className="text-sm font-medium text-foreground">
                  Phone Number
                </label>
                <Input
                  type="tel"
                  placeholder="(555) 123-4567"
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium text-foreground">
                  Website
                </label>
                <Input
                  type="url"
                  placeholder="https://yourstore.com"
                  value={website}
                  onChange={(e) => setWebsite(e.target.value)}
                />
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Buylist Settings */}
        <Card className="glow-accent">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <DollarSign className="w-5 h-5" />
              Buylist Settings
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <label className="text-sm font-medium text-foreground">
                Buylist Margin (% of Market Price)
              </label>
              <div className="flex items-center gap-2">
                <Input
                  type="number"
                  min="1"
                  max="99"
                  value={buylistMargin}
                  onChange={(e) => setBuylistMargin(e.target.value)}
                  className="max-w-[100px]"
                />
                <span className="text-muted-foreground">%</span>
              </div>
              <p className="text-sm text-muted-foreground flex items-start gap-2">
                <Info className="w-4 h-4 shrink-0 mt-0.5" />
                This is the percentage of market value you pay for trade-ins.
                For example, 50% means you pay $5 for a $10 card.
              </p>
            </div>

            <div className="p-4 rounded-lg bg-secondary">
              <p className="text-sm">
                <strong>Example:</strong> At {buylistMargin}%, a quote with
                $100 market value would show as{' '}
                <span className="text-[rgb(var(--success))] font-medium">
                  ${safeToFixed(100 * (parseFloat(buylistMargin) / 100 || 0), 2)}
                </span>{' '}
                offer to customers.
              </p>
            </div>
          </CardContent>
        </Card>

        {/* Services */}
        <Card className="glow-accent">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Store className="w-5 h-5" />
              Services Offered
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-2">
              {SERVICES.map((service) => (
                <button
                  key={service}
                  type="button"
                  onClick={() => toggleService(service)}
                  className={`px-3 py-1.5 rounded-lg border transition-colors ${
                    selectedServices.includes(service)
                      ? 'bg-[rgb(var(--accent))]/20 border-[rgb(var(--accent))] text-[rgb(var(--accent))]'
                      : 'bg-secondary border-border text-muted-foreground hover:border-[rgb(var(--accent))]/50'
                  }`}
                >
                  {service}
                </button>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Submit */}
        <div className="flex justify-end gap-4">
          <Button
            type="button"
            variant="secondary"
            onClick={() => router.push('/store')}
          >
            Cancel
          </Button>
          <Button
            type="submit"
            className="gradient-arcane text-white glow-accent"
            disabled={isSubmitting}
          >
            {isSubmitting ? (
              <>
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                Registering...
              </>
            ) : (
              <>
                <Store className="w-4 h-4 mr-2" />
                Register Store
              </>
            )}
          </Button>
        </div>
      </form>
    </div>
  );
}
