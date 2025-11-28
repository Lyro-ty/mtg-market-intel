'use client';

import { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Save, RefreshCw } from 'lucide-react';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Badge } from '@/components/ui/Badge';
import { LoadingPage } from '@/components/ui/Loading';
import { getSettings, updateSettings, getMarketplaces, toggleMarketplace } from '@/lib/api';

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
      <div>
        <h1 className="text-3xl font-bold text-[rgb(var(--foreground))]">Settings</h1>
        <p className="text-[rgb(var(--muted-foreground))] mt-1">
          Configure your MTG Market Intel preferences
        </p>
      </div>

      {/* Marketplace Settings */}
      <Card>
        <CardHeader>
          <CardTitle>Marketplaces</CardTitle>
          <CardDescription>Enable or disable marketplace data sources</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {marketplacesData?.marketplaces.map((marketplace) => (
              <div
                key={marketplace.id}
                className="flex items-center justify-between py-3 border-b border-[rgb(var(--border))] last:border-0"
              >
                <div>
                  <p className="font-medium text-[rgb(var(--foreground))]">{marketplace.name}</p>
                  <p className="text-sm text-[rgb(var(--muted-foreground))]">
                    {marketplace.base_url}
                  </p>
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
                  >
                    {marketplace.is_enabled ? 'Enabled' : 'Disabled'}
                  </Button>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Recommendation Settings */}
      <Card>
        <CardHeader>
          <CardTitle>Recommendation Settings</CardTitle>
          <CardDescription>Configure how recommendations are generated</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <Input
              label="Minimum ROI Threshold (%)"
              type="number"
              min="0"
              max="100"
              step="1"
              value={formData.min_roi_threshold || (settings?.min_roi_threshold ? settings.min_roi_threshold * 100 : '')}
              onChange={(e) => setFormData({ ...formData, min_roi_threshold: e.target.value })}
              placeholder="10"
            />
            <Input
              label="Minimum Confidence (%)"
              type="number"
              min="0"
              max="100"
              step="1"
              value={formData.min_confidence_threshold || (settings?.min_confidence_threshold ? settings.min_confidence_threshold * 100 : '')}
              onChange={(e) => setFormData({ ...formData, min_confidence_threshold: e.target.value })}
              placeholder="60"
            />
            <Input
              label="Recommendation Horizon (days)"
              type="number"
              min="1"
              max="90"
              value={formData.recommendation_horizon_days || settings?.recommendation_horizon_days || ''}
              onChange={(e) => setFormData({ ...formData, recommendation_horizon_days: e.target.value })}
              placeholder="7"
            />
            <Input
              label="Price History Days"
              type="number"
              min="7"
              max="365"
              value={formData.price_history_days || settings?.price_history_days || ''}
              onChange={(e) => setFormData({ ...formData, price_history_days: e.target.value })}
              placeholder="90"
            />
          </div>

          <div className="flex justify-end mt-6">
            <Button onClick={handleSave} disabled={updateMutation.isPending}>
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

          {updateMutation.isSuccess && (
            <p className="text-green-500 text-sm mt-4">Settings saved successfully!</p>
          )}
          {updateMutation.isError && (
            <p className="text-red-500 text-sm mt-4">Failed to save settings</p>
          )}
        </CardContent>
      </Card>

      {/* System Status */}
      <Card>
        <CardHeader>
          <CardTitle>System Status</CardTitle>
          <CardDescription>Current system configuration</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 gap-4">
            <div className="p-4 rounded-lg bg-[rgb(var(--secondary))]">
              <p className="text-sm text-[rgb(var(--muted-foreground))]">Scraping</p>
              <Badge variant={settings?.scraping_enabled ? 'success' : 'danger'}>
                {settings?.scraping_enabled ? 'Enabled' : 'Disabled'}
              </Badge>
            </div>
            <div className="p-4 rounded-lg bg-[rgb(var(--secondary))]">
              <p className="text-sm text-[rgb(var(--muted-foreground))]">Analytics</p>
              <Badge variant={settings?.analytics_enabled ? 'success' : 'danger'}>
                {settings?.analytics_enabled ? 'Enabled' : 'Disabled'}
              </Badge>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

