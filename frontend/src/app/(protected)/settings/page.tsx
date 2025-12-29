'use client';

import { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Save,
  RefreshCw,
  Settings,
  Palette,
  Store,
  Sliders,
  Activity,
  User,
  Lock,
  Bell,
  Shield,
  HelpCircle,
  Mail,
  Check,
  X,
  ExternalLink,
  Keyboard,
  BookOpen,
} from 'lucide-react';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { LoadingPage } from '@/components/ui/Loading';
import { ThemePicker } from '@/components/ui/ThemePicker';
import { PageHeader } from '@/components/ornate/page-header';
import {
  getSettings,
  updateSettings,
  getMarketplaces,
  toggleMarketplace,
  getCurrentUser,
  updateProfile,
  changePassword,
} from '@/lib/api';
import { SessionsManager } from '@/components/settings/SessionsManager';
import { useAuth } from '@/contexts/AuthContext';
import { cn } from '@/lib/utils';

export default function SettingsPage() {
  const queryClient = useQueryClient();
  const { user } = useAuth();
  const [activeSection, setActiveSection] = useState('account');

  // Account form state
  const [displayName, setDisplayName] = useState('');
  const [isUpdatingProfile, setIsUpdatingProfile] = useState(false);
  const [profileSuccess, setProfileSuccess] = useState(false);

  // Password form state
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [passwordError, setPasswordError] = useState('');
  const [passwordSuccess, setPasswordSuccess] = useState(false);
  const [isChangingPassword, setIsChangingPassword] = useState(false);

  // Settings queries
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

  // Initialize form data
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

  useEffect(() => {
    if (user?.display_name) {
      setDisplayName(user.display_name);
    }
  }, [user]);

  const handleSaveSettings = () => {
    updateMutation.mutate({
      min_roi_threshold: formData.min_roi_threshold ? Number(formData.min_roi_threshold) / 100 : undefined,
      min_confidence_threshold: formData.min_confidence_threshold ? Number(formData.min_confidence_threshold) / 100 : undefined,
      recommendation_horizon_days: formData.recommendation_horizon_days ? Number(formData.recommendation_horizon_days) : undefined,
      price_history_days: formData.price_history_days ? Number(formData.price_history_days) : undefined,
    });
  };

  const handleUpdateProfile = async () => {
    setIsUpdatingProfile(true);
    setProfileSuccess(false);
    try {
      await updateProfile({ display_name: displayName });
      queryClient.invalidateQueries({ queryKey: ['user'] });
      setProfileSuccess(true);
      setTimeout(() => setProfileSuccess(false), 3000);
    } catch (error) {
      console.error('Failed to update profile:', error);
    } finally {
      setIsUpdatingProfile(false);
    }
  };

  const handleChangePassword = async () => {
    setPasswordError('');
    setPasswordSuccess(false);

    if (newPassword !== confirmPassword) {
      setPasswordError('New passwords do not match');
      return;
    }

    if (newPassword.length < 12) {
      setPasswordError('Password must be at least 12 characters');
      return;
    }

    setIsChangingPassword(true);
    try {
      await changePassword(currentPassword, newPassword);
      setPasswordSuccess(true);
      setCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');
      setTimeout(() => setPasswordSuccess(false), 3000);
    } catch (error) {
      setPasswordError(error instanceof Error ? error.message : 'Failed to change password');
    } finally {
      setIsChangingPassword(false);
    }
  };

  if (settingsLoading || marketplacesLoading) return <LoadingPage />;

  const sections = [
    { id: 'account', label: 'Account', icon: User },
    { id: 'appearance', label: 'Appearance', icon: Palette },
    { id: 'notifications', label: 'Notifications', icon: Bell },
    { id: 'trading', label: 'Trading', icon: Sliders },
    { id: 'marketplaces', label: 'Marketplaces', icon: Store },
    { id: 'security', label: 'Security', icon: Shield },
    { id: 'help', label: 'Help', icon: HelpCircle },
  ];

  return (
    <div className="space-y-6 animate-in max-w-5xl">
      <PageHeader
        title="Settings"
        subtitle="Configure your Dualcaster Deals preferences"
      >
        <div className="p-2 rounded-xl bg-gradient-to-br from-[rgb(var(--accent))]/20 to-[rgb(var(--accent))]/5 border border-[rgb(var(--accent))]/20">
          <Settings className="w-5 h-5 text-[rgb(var(--accent))]" />
        </div>
      </PageHeader>

      <div className="flex gap-6">
        {/* Sidebar Navigation */}
        <div className="w-48 shrink-0">
          <nav className="space-y-1 sticky top-6">
            {sections.map((section) => {
              const Icon = section.icon;
              return (
                <button
                  key={section.id}
                  onClick={() => setActiveSection(section.id)}
                  className={cn(
                    'w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors text-left',
                    activeSection === section.id
                      ? 'bg-[rgb(var(--accent))]/20 text-[rgb(var(--accent))] font-medium'
                      : 'text-muted-foreground hover:text-foreground hover:bg-secondary'
                  )}
                >
                  <Icon className="w-4 h-4" />
                  {section.label}
                </button>
              );
            })}
          </nav>
        </div>

        {/* Content Area */}
        <div className="flex-1 space-y-6">
          {/* Account Section */}
          {activeSection === 'account' && (
            <>
              <Card className="border-[rgb(var(--accent))]/20">
                <CardHeader>
                  <div className="flex items-center gap-3">
                    <div className="p-2 rounded-lg bg-[rgb(var(--accent))]/10">
                      <User className="w-5 h-5 text-[rgb(var(--accent))]" />
                    </div>
                    <div>
                      <CardTitle>Profile</CardTitle>
                      <CardDescription>Your account information</CardDescription>
                    </div>
                  </div>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <label className="text-sm font-medium text-foreground">Email</label>
                      <Input value={user?.email || ''} disabled className="bg-secondary" />
                      <p className="text-xs text-muted-foreground">Email cannot be changed</p>
                    </div>
                    <div className="space-y-2">
                      <label className="text-sm font-medium text-foreground">Username</label>
                      <Input value={user?.username || ''} disabled className="bg-secondary" />
                      <p className="text-xs text-muted-foreground">Username cannot be changed</p>
                    </div>
                  </div>
                  <div className="space-y-2">
                    <label className="text-sm font-medium text-foreground">Display Name</label>
                    <div className="flex gap-2">
                      <Input
                        value={displayName}
                        onChange={(e) => setDisplayName(e.target.value)}
                        placeholder="Enter your display name"
                      />
                      <Button
                        onClick={handleUpdateProfile}
                        disabled={isUpdatingProfile}
                        className="gradient-arcane"
                      >
                        {isUpdatingProfile ? (
                          <RefreshCw className="w-4 h-4 animate-spin" />
                        ) : profileSuccess ? (
                          <Check className="w-4 h-4" />
                        ) : (
                          <Save className="w-4 h-4" />
                        )}
                      </Button>
                    </div>
                  </div>
                  <div className="p-3 rounded-lg bg-secondary/50 text-sm text-muted-foreground">
                    <p>Member since: {user?.created_at ? new Date(user.created_at).toLocaleDateString() : 'Unknown'}</p>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <div className="flex items-center gap-3">
                    <div className="p-2 rounded-lg bg-[rgb(var(--warning))]/10">
                      <Lock className="w-5 h-5 text-[rgb(var(--warning))]" />
                    </div>
                    <div>
                      <CardTitle>Change Password</CardTitle>
                      <CardDescription>Update your account password</CardDescription>
                    </div>
                  </div>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="space-y-2">
                    <label className="text-sm font-medium text-foreground">Current Password</label>
                    <Input
                      type="password"
                      value={currentPassword}
                      onChange={(e) => setCurrentPassword(e.target.value)}
                      placeholder="Enter current password"
                    />
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <label className="text-sm font-medium text-foreground">New Password</label>
                      <Input
                        type="password"
                        value={newPassword}
                        onChange={(e) => setNewPassword(e.target.value)}
                        placeholder="At least 12 characters"
                      />
                    </div>
                    <div className="space-y-2">
                      <label className="text-sm font-medium text-foreground">Confirm New Password</label>
                      <Input
                        type="password"
                        value={confirmPassword}
                        onChange={(e) => setConfirmPassword(e.target.value)}
                        placeholder="Confirm new password"
                      />
                    </div>
                  </div>
                  {passwordError && (
                    <p className="text-sm text-[rgb(var(--destructive))]">{passwordError}</p>
                  )}
                  {passwordSuccess && (
                    <p className="text-sm text-[rgb(var(--success))]">Password changed successfully!</p>
                  )}
                  <Button
                    onClick={handleChangePassword}
                    disabled={isChangingPassword || !currentPassword || !newPassword || !confirmPassword}
                  >
                    {isChangingPassword ? (
                      <>
                        <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
                        Changing...
                      </>
                    ) : (
                      'Change Password'
                    )}
                  </Button>
                </CardContent>
              </Card>
            </>
          )}

          {/* Appearance Section */}
          {activeSection === 'appearance' && (
            <Card className="border-[rgb(var(--accent))]/20">
              <CardHeader>
                <div className="flex items-center gap-3">
                  <div className="p-2 rounded-lg bg-[rgb(var(--accent))]/10">
                    <Palette className="w-5 h-5 text-[rgb(var(--accent))]" />
                  </div>
                  <div>
                    <CardTitle>Appearance</CardTitle>
                    <CardDescription>Customize the look and feel of the application</CardDescription>
                  </div>
                </div>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  <div className="p-4 rounded-lg bg-[rgb(var(--secondary))]/50 border border-[rgb(var(--border))]">
                    <label className="block text-sm font-medium text-foreground mb-3">
                      Mana Theme
                    </label>
                    <ThemePicker />
                    <p className="text-xs text-muted-foreground mt-3">
                      Choose your preferred mana color to personalize the interface
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}

          {/* Notifications Section */}
          {activeSection === 'notifications' && (
            <Card>
              <CardHeader>
                <div className="flex items-center gap-3">
                  <div className="p-2 rounded-lg bg-[rgb(var(--magic-gold))]/10">
                    <Bell className="w-5 h-5 text-[rgb(var(--magic-gold))]" />
                  </div>
                  <div>
                    <CardTitle>Notification Preferences</CardTitle>
                    <CardDescription>Control how and when you receive notifications</CardDescription>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="space-y-6">
                <div className="space-y-4">
                  <h4 className="text-sm font-medium text-foreground">Alert Types</h4>
                  <div className="space-y-3">
                    {[
                      { id: 'price_alerts', label: 'Price Alerts', description: 'When cards hit your target price' },
                      { id: 'recommendations', label: 'Recommendations', description: 'New buy/sell recommendations' },
                      { id: 'portfolio', label: 'Portfolio Alerts', description: 'Significant changes to your inventory value' },
                      { id: 'milestones', label: 'Collection Milestones', description: 'When you reach collection goals' },
                    ].map((item) => (
                      <div key={item.id} className="flex items-center justify-between p-3 rounded-lg bg-secondary/50">
                        <div>
                          <p className="text-sm font-medium text-foreground">{item.label}</p>
                          <p className="text-xs text-muted-foreground">{item.description}</p>
                        </div>
                        <div className="flex items-center gap-2">
                          <Badge variant="info">Coming Soon</Badge>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
                <Separator />
                <div className="space-y-4">
                  <h4 className="text-sm font-medium text-foreground">Delivery Methods</h4>
                  <div className="space-y-3">
                    <div className="flex items-center justify-between p-3 rounded-lg bg-secondary/50">
                      <div className="flex items-center gap-3">
                        <Mail className="w-4 h-4 text-muted-foreground" />
                        <div>
                          <p className="text-sm font-medium text-foreground">Email Notifications</p>
                          <p className="text-xs text-muted-foreground">Receive alerts via email</p>
                        </div>
                      </div>
                      <Badge variant="info">Coming Soon</Badge>
                    </div>
                    <div className="flex items-center justify-between p-3 rounded-lg bg-secondary/50">
                      <div className="flex items-center gap-3">
                        <Bell className="w-4 h-4 text-muted-foreground" />
                        <div>
                          <p className="text-sm font-medium text-foreground">Push Notifications</p>
                          <p className="text-xs text-muted-foreground">Browser push notifications</p>
                        </div>
                      </div>
                      <Badge variant="info">Coming Soon</Badge>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}

          {/* Trading Settings Section */}
          {activeSection === 'trading' && (
            <Card>
              <CardHeader>
                <div className="flex items-center gap-3">
                  <div className="p-2 rounded-lg bg-[rgb(var(--magic-purple))]/10">
                    <Sliders className="w-5 h-5 text-[rgb(var(--magic-purple))]" />
                  </div>
                  <div>
                    <CardTitle>Recommendation Settings</CardTitle>
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
                      value={formData.min_roi_threshold}
                      onChange={(e) => setFormData({ ...formData, min_roi_threshold: e.target.value })}
                      placeholder="10"
                    />
                    <p className="text-xs text-muted-foreground">
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
                      value={formData.min_confidence_threshold}
                      onChange={(e) => setFormData({ ...formData, min_confidence_threshold: e.target.value })}
                      placeholder="60"
                    />
                    <p className="text-xs text-muted-foreground">
                      Minimum confidence score for recommendations
                    </p>
                  </div>
                  <div className="space-y-2">
                    <Input
                      label="Recommendation Horizon (days)"
                      type="number"
                      min="1"
                      max="90"
                      value={formData.recommendation_horizon_days}
                      onChange={(e) => setFormData({ ...formData, recommendation_horizon_days: e.target.value })}
                      placeholder="7"
                    />
                    <p className="text-xs text-muted-foreground">
                      Time horizon for price predictions
                    </p>
                  </div>
                  <div className="space-y-2">
                    <Input
                      label="Price History Days"
                      type="number"
                      min="7"
                      max="365"
                      value={formData.price_history_days}
                      onChange={(e) => setFormData({ ...formData, price_history_days: e.target.value })}
                      placeholder="90"
                    />
                    <p className="text-xs text-muted-foreground">
                      Days of price history to analyze
                    </p>
                  </div>
                </div>

                <Separator className="my-6" />

                <div className="flex items-center justify-between">
                  <div className="text-sm">
                    {updateMutation.isSuccess && (
                      <span className="text-[rgb(var(--success))]">Settings saved successfully!</span>
                    )}
                    {updateMutation.isError && (
                      <span className="text-[rgb(var(--destructive))]">Failed to save settings</span>
                    )}
                  </div>
                  <Button
                    onClick={handleSaveSettings}
                    disabled={updateMutation.isPending}
                    className="gradient-arcane"
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
          )}

          {/* Marketplaces Section */}
          {activeSection === 'marketplaces' && (
            <>
              <Card>
                <CardHeader>
                  <div className="flex items-center gap-3">
                    <div className="p-2 rounded-lg bg-[rgb(var(--magic-gold))]/10">
                      <Store className="w-5 h-5 text-[rgb(var(--magic-gold))]" />
                    </div>
                    <div>
                      <CardTitle>Marketplaces</CardTitle>
                      <CardDescription>Enable or disable marketplace data sources</CardDescription>
                    </div>
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="space-y-2">
                    {marketplacesData?.marketplaces.map((marketplace, index) => (
                      <div key={marketplace.id}>
                        <div className="flex items-center justify-between py-4 px-4 rounded-lg hover:bg-secondary/50 transition-colors">
                          <div className="flex items-center gap-4">
                            <div className={cn(
                              "w-2 h-2 rounded-full",
                              marketplace.is_enabled ? "bg-[rgb(var(--success))]" : "bg-muted-foreground"
                            )} />
                            <div>
                              <p className="font-medium text-foreground">{marketplace.name}</p>
                              <p className="text-sm text-muted-foreground">{marketplace.base_url}</p>
                            </div>
                          </div>
                          <div className="flex items-center gap-3">
                            {marketplace.supports_api && <Badge variant="info" size="sm">API</Badge>}
                            <Button
                              variant={marketplace.is_enabled ? 'primary' : 'secondary'}
                              size="sm"
                              onClick={() => toggleMutation.mutate(marketplace.id)}
                              disabled={toggleMutation.isPending}
                              className={cn("min-w-[90px]", marketplace.is_enabled && "glow-accent")}
                            >
                              {marketplace.is_enabled ? 'Enabled' : 'Disabled'}
                            </Button>
                          </div>
                        </div>
                        {index < marketplacesData.marketplaces.length - 1 && <Separator className="my-1" />}
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <div className="flex items-center gap-3">
                    <div className="p-2 rounded-lg bg-[rgb(var(--success))]/10">
                      <Activity className="w-5 h-5 text-[rgb(var(--success))]" />
                    </div>
                    <div>
                      <CardTitle>System Status</CardTitle>
                      <CardDescription>Current system configuration</CardDescription>
                    </div>
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-2 gap-4">
                    <div className="p-4 rounded-lg bg-secondary/50 border border-border hover:border-[rgb(var(--accent))]/30 transition-colors">
                      <div className="flex items-center justify-between mb-2">
                        <p className="text-sm text-muted-foreground">Scraping</p>
                        <div className={cn(
                          "w-2 h-2 rounded-full",
                          settings?.scraping_enabled ? "bg-[rgb(var(--success))] animate-pulse" : "bg-[rgb(var(--destructive))]"
                        )} />
                      </div>
                      <Badge variant={settings?.scraping_enabled ? 'success' : 'danger'}>
                        {settings?.scraping_enabled ? 'Enabled' : 'Disabled'}
                      </Badge>
                    </div>
                    <div className="p-4 rounded-lg bg-secondary/50 border border-border hover:border-[rgb(var(--accent))]/30 transition-colors">
                      <div className="flex items-center justify-between mb-2">
                        <p className="text-sm text-muted-foreground">Analytics</p>
                        <div className={cn(
                          "w-2 h-2 rounded-full",
                          settings?.analytics_enabled ? "bg-[rgb(var(--success))] animate-pulse" : "bg-[rgb(var(--destructive))]"
                        )} />
                      </div>
                      <Badge variant={settings?.analytics_enabled ? 'success' : 'danger'}>
                        {settings?.analytics_enabled ? 'Enabled' : 'Disabled'}
                      </Badge>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </>
          )}

          {/* Security Section */}
          {activeSection === 'security' && (
            <SessionsManager />
          )}

          {/* Help Section */}
          {activeSection === 'help' && (
            <Card>
              <CardHeader>
                <div className="flex items-center gap-3">
                  <div className="p-2 rounded-lg bg-[rgb(var(--accent))]/10">
                    <HelpCircle className="w-5 h-5 text-[rgb(var(--accent))]" />
                  </div>
                  <div>
                    <CardTitle>Help & Support</CardTitle>
                    <CardDescription>Resources and assistance</CardDescription>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid gap-4">
                  <a
                    href="https://github.com/anthropics/claude-code/issues"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center justify-between p-4 rounded-lg bg-secondary/50 hover:bg-secondary transition-colors group"
                  >
                    <div className="flex items-center gap-3">
                      <BookOpen className="w-5 h-5 text-muted-foreground group-hover:text-[rgb(var(--accent))]" />
                      <div>
                        <p className="font-medium text-foreground">Documentation</p>
                        <p className="text-sm text-muted-foreground">Learn how to use all features</p>
                      </div>
                    </div>
                    <ExternalLink className="w-4 h-4 text-muted-foreground group-hover:text-[rgb(var(--accent))]" />
                  </a>

                  <div className="flex items-center justify-between p-4 rounded-lg bg-secondary/50">
                    <div className="flex items-center gap-3">
                      <Keyboard className="w-5 h-5 text-muted-foreground" />
                      <div>
                        <p className="font-medium text-foreground">Keyboard Shortcuts</p>
                        <p className="text-sm text-muted-foreground">Speed up your workflow</p>
                      </div>
                    </div>
                    <Badge variant="info">Coming Soon</Badge>
                  </div>

                  <div className="p-4 rounded-lg bg-gradient-to-r from-[rgb(var(--accent))]/10 to-[rgb(var(--magic-gold))]/10 border border-[rgb(var(--accent))]/20">
                    <h4 className="font-medium text-foreground mb-2">Contact Support</h4>
                    <p className="text-sm text-muted-foreground mb-3">
                      Having issues or need help? Reach out to us.
                    </p>
                    <Button variant="secondary" size="sm" asChild>
                      <a href="mailto:support@dualcasterdeals.com">
                        <Mail className="w-4 h-4 mr-2" />
                        Email Support
                      </a>
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
