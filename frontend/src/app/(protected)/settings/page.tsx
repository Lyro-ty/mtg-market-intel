'use client';

import { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Save, RefreshCw, Settings, Palette, Store, Sliders, Activity } from 'lucide-react';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { LoadingPage } from '@/components/ui/Loading';
import { ThemePicker } from '@/components/ui/ThemePicker';
import { PageHeader } from '@/components/ornate/page-header';
import { getSettings, updateSettings, getMarketplaces, toggleMarketplace } from '@/lib/api';
import { SessionsManager } from '@/components/settings/SessionsManager';
import { cn } from '@/lib/utils';

export default function SettingsPage() {
  const queryClient = useQueryClient();

  const { data: settings, isLoading: settingsLoading } = useQuery({
    queryKey: ['settings'],
    queryFn: getSettings,
  });

  const { data: marketplacesData, isLoading: marketplacesLoading } = useQuery({
    queryKey: ['marketplaces'],
    queryFn: () => getMarketplaces(false),
  });

  const updateMutation = useMutation({
    mutationFn: updateSettings,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['settings'] });
    },
  });

  const toggleMutation = useMutation({
    mutationFn: toggleMarketplace,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['marketplaces'] });
    },
  });

  const [formData, setFormData] = useState({
    min_roi_threshold: '',
    min_confidence_threshold: '',
    recommendation_horizon_days: '',
    price_history_days: '',
  });

  // Initialize form data when settings load
  useEffect(() => {
    if (settings) {
      setFormData({
        min_roi_threshold: String(settings.min_roi_threshold * 100),
        min_confidence_threshold: String(settings.min_confidence_threshold * 100),
        recommendation_horizon_days: String(settings.recommendation_horizon_days),
        price_history_days: String(settings.price_history_days),
      });
    }
  }, [settings]);

  const handleSave = () => {
    updateMutation.mutate({
      min_roi_threshold: formData.min_roi_threshold ? Number(formData.min_roi_threshold) / 100 : undefined,
      min_confidence_threshold: formData.min_confidence_threshold ? Number(formData.min_confidence_threshold) / 100 : undefined,
      recommendation_horizon_days: formData.recommendation_horizon_days ? Number(formData.recommendation_horizon_days) : undefined,
      price_history_days: formData.price_history_days ? Number(formData.price_history_days) : undefined,
    });
  };

  if (settingsLoading || marketplacesLoading) return <LoadingPage />;

  return (
    <div className="space-y-6 animate-in max-w-4xl">
      {/* Header */}
      <PageHeader
        title="Settings"
        subtitle="Configure your MTG Market Intel preferences"
      >
        <div className="p-2 rounded-xl bg-gradient-to-br from-[rgb(var(--accent))]/20 to-[rgb(var(--accent))]/5 border border-[rgb(var(--accent))]/20">
          <Settings className="w-5 h-5 text-[rgb(var(--accent))]" />
        </div>
      </PageHeader>

      {/* Appearance Settings */}
      <Card className="border-[rgb(var(--accent))]/20 bg-gradient-to-br from-[rgb(var(--card))] to-[rgb(var(--card))]/80">
        <CardHeader>
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-[rgb(var(--accent))]/10">
              <Palette className="w-5 h-5 text-[rgb(var(--accent))]" />
            </div>
            <div>
              <CardTitle className="text-[rgb(var(--foreground))]">Appearance</CardTitle>
              <CardDescription>Customize the look and feel of the application</CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <div className="p-4 rounded-lg bg-[rgb(var(--secondary))]/50 border border-[rgb(var(--border))]">
              <label className="block text-sm font-medium text-[rgb(var(--foreground))] mb-3">
                Mana Theme
              </label>
              <ThemePicker />
              <p className="text-xs text-[rgb(var(--muted-foreground))] mt-3">
                Choose your preferred mana color to personalize the interface
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Marketplace Settings */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-[rgb(var(--magic-gold))]/10">
              <Store className="w-5 h-5 text-[rgb(var(--magic-gold))]" />
            </div>
            <div>
              <CardTitle className="text-[rgb(var(--foreground))]">Marketplaces</CardTitle>
              <CardDescription>Enable or disable marketplace data sources</CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="space-y-2">
            {marketplacesData?.marketplaces.map((marketplace, index) => (
              <div key={marketplace.id}>
                <div
                  className={cn(
                    "flex items-center justify-between py-4 px-4 rounded-lg transition-colors",
                    "hover:bg-[rgb(var(--secondary))]/50"
                  )}
                >
                  <div className="flex items-center gap-4">
                    <div className={cn(
                      "w-2 h-2 rounded-full",
                      marketplace.is_enabled
                        ? "bg-[rgb(var(--success))]"
                        : "bg-[rgb(var(--muted-foreground))]"
                    )} />
                    <div>
                      <p className="font-medium text-[rgb(var(--foreground))]">{marketplace.name}</p>
                      <p className="text-sm text-[rgb(var(--muted-foreground))]">
                        {marketplace.base_url}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    {marketplace.supports_api && (
                      <Badge variant="info" size="sm">API</Badge>
                    )}
                    <Button
                      variant={marketplace.is_enabled ? 'primary' : 'secondary'}
                      size="sm"
                      onClick={() => toggleMutation.mutate(marketplace.id)}
                      disabled={toggleMutation.isPending}
                      className={cn(
                        "min-w-[90px] transition-all",
                        marketplace.is_enabled && "glow-accent"
                      )}
                    >
                      {marketplace.is_enabled ? 'Enabled' : 'Disabled'}
                    </Button>
                  </div>
                </div>
                {index < marketplacesData.marketplaces.length - 1 && (
                  <Separator className="my-1" />
                )}
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Recommendation Settings */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-[rgb(var(--magic-purple))]/10">
              <Sliders className="w-5 h-5 text-[rgb(var(--magic-purple))]" />
            </div>
            <div>
              <CardTitle className="text-[rgb(var(--foreground))]">Recommendation Settings</CardTitle>
              <CardDescription>Configure how recommendations are generated</CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="space-y-2">
              <Input
                label="Minimum ROI Threshold (%)"
                type="number"
                min="0"
                max="100"
                step="1"
                value={formData.min_roi_threshold || (settings?.min_roi_threshold ? settings.min_roi_threshold * 100 : '')}
                onChange={(e) => setFormData({ ...formData, min_roi_threshold: e.target.value })}
                placeholder="10"
                className="focus:ring-[rgb(var(--accent))]/50 focus:border-[rgb(var(--accent))]"
              />
              <p className="text-xs text-[rgb(var(--muted-foreground))]">
                Minimum return on investment to trigger a recommendation
              </p>
            </div>
            <div className="space-y-2">
              <Input
                label="Minimum Confidence (%)"
                type="number"
                min="0"
                max="100"
                step="1"
                value={formData.min_confidence_threshold || (settings?.min_confidence_threshold ? settings.min_confidence_threshold * 100 : '')}
                onChange={(e) => setFormData({ ...formData, min_confidence_threshold: e.target.value })}
                placeholder="60"
                className="focus:ring-[rgb(var(--accent))]/50 focus:border-[rgb(var(--accent))]"
              />
              <p className="text-xs text-[rgb(var(--muted-foreground))]">
                Minimum confidence score for recommendations
              </p>
            </div>
            <div className="space-y-2">
              <Input
                label="Recommendation Horizon (days)"
                type="number"
                min="1"
                max="90"
                value={formData.recommendation_horizon_days || settings?.recommendation_horizon_days || ''}
                onChange={(e) => setFormData({ ...formData, recommendation_horizon_days: e.target.value })}
                placeholder="7"
                className="focus:ring-[rgb(var(--accent))]/50 focus:border-[rgb(var(--accent))]"
              />
              <p className="text-xs text-[rgb(var(--muted-foreground))]">
                Time horizon for price predictions
              </p>
            </div>
            <div className="space-y-2">
              <Input
                label="Price History Days"
                type="number"
                min="7"
                max="365"
                value={formData.price_history_days || settings?.price_history_days || ''}
                onChange={(e) => setFormData({ ...formData, price_history_days: e.target.value })}
                placeholder="90"
                className="focus:ring-[rgb(var(--accent))]/50 focus:border-[rgb(var(--accent))]"
              />
              <p className="text-xs text-[rgb(var(--muted-foreground))]">
                Days of price history to analyze
              </p>
            </div>
          </div>

          <Separator className="my-6" />

          <div className="flex items-center justify-between">
            <div className="text-sm text-[rgb(var(--muted-foreground))]">
              {updateMutation.isSuccess && (
                <span className="text-[rgb(var(--success))]">Settings saved successfully!</span>
              )}
              {updateMutation.isError && (
                <span className="text-[rgb(var(--destructive))]">Failed to save settings</span>
              )}
            </div>
            <Button
              onClick={handleSave}
              disabled={updateMutation.isPending}
              className="bg-gradient-to-r from-[rgb(var(--accent))] to-[rgb(var(--accent))]/80 hover:from-[rgb(var(--accent))]/90 hover:to-[rgb(var(--accent))]/70"
            >
              {updateMutation.isPending ? (
                <>
                  <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
                  Saving...
                </>
              ) : (
                <>
                  <Save className="w-4 h-4 mr-2" />
                  Save Changes
                </>
              )}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* System Status */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-[rgb(var(--success))]/10">
              <Activity className="w-5 h-5 text-[rgb(var(--success))]" />
            </div>
            <div>
              <CardTitle className="text-[rgb(var(--foreground))]">System Status</CardTitle>
              <CardDescription>Current system configuration</CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 gap-4">
            <div className="p-4 rounded-lg bg-[rgb(var(--secondary))]/50 border border-[rgb(var(--border))] hover:border-[rgb(var(--accent))]/30 transition-colors">
              <div className="flex items-center justify-between mb-2">
                <p className="text-sm text-[rgb(var(--muted-foreground))]">Scraping</p>
                <div className={cn(
                  "w-2 h-2 rounded-full",
                  settings?.scraping_enabled
                    ? "bg-[rgb(var(--success))] animate-pulse"
                    : "bg-[rgb(var(--destructive))]"
                )} />
              </div>
              <Badge variant={settings?.scraping_enabled ? 'success' : 'danger'}>
                {settings?.scraping_enabled ? 'Enabled' : 'Disabled'}
              </Badge>
            </div>
            <div className="p-4 rounded-lg bg-[rgb(var(--secondary))]/50 border border-[rgb(var(--border))] hover:border-[rgb(var(--accent))]/30 transition-colors">
              <div className="flex items-center justify-between mb-2">
                <p className="text-sm text-[rgb(var(--muted-foreground))]">Analytics</p>
                <div className={cn(
                  "w-2 h-2 rounded-full",
                  settings?.analytics_enabled
                    ? "bg-[rgb(var(--success))] animate-pulse"
                    : "bg-[rgb(var(--destructive))]"
                )} />
              </div>
              <Badge variant={settings?.analytics_enabled ? 'success' : 'danger'}>
                {settings?.analytics_enabled ? 'Enabled' : 'Disabled'}
              </Badge>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Sessions */}
      <SessionsManager />
    </div>
  );
}
