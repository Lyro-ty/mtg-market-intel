'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import {
  Shield,
  AlertTriangle,
  Clock,
  CheckCircle,
  Loader2,
  AlertCircle,
  Users,
  Gavel,
  MessageSquareWarning,
} from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { PageHeader } from '@/components/ornate/page-header';
import { useAuth } from '@/contexts/AuthContext';
import {
  getModerationQueue,
  getModerationStats,
  getAppeals,
  getDisputes,
  ApiError,
} from '@/lib/api';
import { ModerationQueue } from './components/ModerationQueue';
import { CaseDetail } from './components/CaseDetail';
import { AppealsQueue } from './components/AppealsQueue';
import { DisputesQueue } from './components/DisputesQueue';
import type {
  ModerationQueueResponse,
  ModerationStats,
  AppealResponse,
  TradeDisputeResponse,
} from '@/lib/api/moderation';

// =============================================================================
// Stats Card Component
// =============================================================================

interface StatsCardProps {
  title: string;
  value: number;
  icon: React.ReactNode;
  variant?: 'default' | 'warning' | 'success';
}

function StatsCard({ title, value, icon, variant = 'default' }: StatsCardProps) {
  const variantStyles = {
    default: 'text-foreground',
    warning: 'text-[rgb(var(--warning))]',
    success: 'text-[rgb(var(--success))]',
  };

  return (
    <Card className="glow-accent">
      <CardContent className="p-4">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm text-muted-foreground">{title}</p>
            <p className={`text-3xl font-bold ${variantStyles[variant]}`}>
              {value}
            </p>
          </div>
          <div className="p-3 rounded-lg bg-muted/50">{icon}</div>
        </div>
      </CardContent>
    </Card>
  );
}

// =============================================================================
// Main Page Component
// =============================================================================

export default function ModerationPage() {
  const { user, isLoading: authLoading } = useAuth();
  const router = useRouter();
  const [selectedUserId, setSelectedUserId] = useState<number | null>(null);
  const [activeTab, setActiveTab] = useState('queue');

  // Access check - redirect if not admin/moderator
  useEffect(() => {
    if (!authLoading && user) {
      // Check for admin/moderator status
      // Since UserResponse doesn't have is_admin/is_moderator in generated types,
      // we'll trust the backend to reject unauthorized requests
      // For now, allow access and let API errors guide us
    }
  }, [user, authLoading, router]);

  // Fetch moderation stats
  const {
    data: stats,
    isLoading: statsLoading,
    error: statsError,
  } = useQuery<ModerationStats, ApiError>({
    queryKey: ['moderation-stats'],
    queryFn: getModerationStats,
    enabled: !!user,
  });

  // Fetch moderation queue
  const {
    data: queueData,
    isLoading: queueLoading,
    error: queueError,
    refetch: refetchQueue,
  } = useQuery<ModerationQueueResponse, ApiError>({
    queryKey: ['moderation-queue'],
    queryFn: () => getModerationQueue({ limit: 50 }),
    enabled: !!user,
  });

  // Fetch appeals
  const {
    data: appeals,
    isLoading: appealsLoading,
    error: appealsError,
    refetch: refetchAppeals,
  } = useQuery<AppealResponse[], ApiError>({
    queryKey: ['moderation-appeals'],
    queryFn: () => getAppeals('pending'),
    enabled: !!user && activeTab === 'appeals',
  });

  // Fetch disputes
  const {
    data: disputes,
    isLoading: disputesLoading,
    error: disputesError,
    refetch: refetchDisputes,
  } = useQuery<TradeDisputeResponse[], ApiError>({
    queryKey: ['moderation-disputes'],
    queryFn: () => getDisputes('open'),
    enabled: !!user && activeTab === 'disputes',
  });

  // Handle case selection
  const handleSelectCase = (userId: number) => {
    setSelectedUserId(userId);
  };

  // Handle action completion - refresh queue
  const handleActionComplete = () => {
    refetchQueue();
    setSelectedUserId(null);
  };

  // Show loading state
  if (authLoading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Loader2 className="w-8 h-8 animate-spin text-[rgb(var(--accent))]" />
      </div>
    );
  }

  // Check for permission errors
  const hasPermissionError =
    statsError?.message?.includes('Moderator access required') ||
    queueError?.message?.includes('Moderator access required');

  if (hasPermissionError) {
    return (
      <div className="space-y-6 animate-in">
        <PageHeader
          title="Moderation Dashboard"
          subtitle="Admin access required"
        />
        <Card className="glow-accent">
          <CardContent className="py-12 text-center">
            <Shield className="w-16 h-16 mx-auto text-muted-foreground mb-4" />
            <h3 className="text-lg font-semibold text-foreground mb-2">
              Access Denied
            </h3>
            <p className="text-muted-foreground">
              You do not have permission to access the moderation dashboard.
              This area is restricted to moderators and administrators.
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  // Calculate counts for tabs
  const queueCount = queueData?.items?.filter(
    (i) => i.flag_type === 'report' || i.flag_type === 'auto_flag'
  ).length ?? 0;
  const appealsCount = appeals?.length ?? 0;
  const disputesCount = disputes?.length ?? 0;

  return (
    <div className="space-y-6 animate-in">
      <PageHeader
        title="Moderation Dashboard"
        subtitle="Review reports, handle disputes, and manage user appeals"
      >
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-muted/50">
          <Shield className="w-4 h-4 text-[rgb(var(--accent))]" />
          <span className="text-sm text-muted-foreground">Moderator</span>
        </div>
      </PageHeader>

      {/* Error Display */}
      {(statsError || queueError) && !hasPermissionError && (
        <div className="p-4 rounded-lg bg-[rgb(var(--destructive))]/10 border border-[rgb(var(--destructive))]/20">
          <div className="flex items-center gap-2">
            <AlertCircle className="w-5 h-5 text-[rgb(var(--destructive))]" />
            <p className="text-[rgb(var(--destructive))]">
              {statsError?.message || queueError?.message || 'Failed to load moderation data'}
            </p>
          </div>
        </div>
      )}

      {/* Stats Summary */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <StatsCard
          title="Pending Items"
          value={stats?.pending ?? 0}
          icon={<Clock className="w-6 h-6 text-muted-foreground" />}
        />
        <StatsCard
          title="High Priority"
          value={stats?.high_priority ?? 0}
          icon={<AlertTriangle className="w-6 h-6 text-[rgb(var(--warning))]" />}
          variant="warning"
        />
        <StatsCard
          title="Resolved Today"
          value={stats?.resolved_today ?? 0}
          icon={<CheckCircle className="w-6 h-6 text-[rgb(var(--success))]" />}
          variant="success"
        />
      </div>

      {/* Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="w-full sm:w-auto grid grid-cols-3 sm:inline-flex">
          <TabsTrigger value="queue" className="gap-1.5">
            <Users className="w-4 h-4 hidden sm:inline" />
            <span>Queue</span>
            {queueCount > 0 && (
              <span className="ml-1 px-1.5 py-0.5 text-xs rounded-full bg-[rgb(var(--accent))]/20 text-[rgb(var(--accent))]">
                {queueCount}
              </span>
            )}
          </TabsTrigger>
          <TabsTrigger value="appeals" className="gap-1.5">
            <MessageSquareWarning className="w-4 h-4 hidden sm:inline" />
            <span>Appeals</span>
            {appealsCount > 0 && (
              <span className="ml-1 px-1.5 py-0.5 text-xs rounded-full bg-[rgb(var(--warning))]/20 text-[rgb(var(--warning))]">
                {appealsCount}
              </span>
            )}
          </TabsTrigger>
          <TabsTrigger value="disputes" className="gap-1.5">
            <Gavel className="w-4 h-4 hidden sm:inline" />
            <span>Disputes</span>
            {disputesCount > 0 && (
              <span className="ml-1 px-1.5 py-0.5 text-xs rounded-full bg-[rgb(var(--destructive))]/20 text-[rgb(var(--destructive))]">
                {disputesCount}
              </span>
            )}
          </TabsTrigger>
        </TabsList>

        {/* Queue Tab */}
        <TabsContent value="queue">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <ModerationQueue
              items={queueData?.items ?? []}
              isLoading={queueLoading}
              selectedUserId={selectedUserId}
              onSelectCase={handleSelectCase}
            />
            {selectedUserId ? (
              <CaseDetail
                userId={selectedUserId}
                onClose={() => setSelectedUserId(null)}
                onActionComplete={handleActionComplete}
              />
            ) : (
              <Card className="glow-accent h-fit">
                <CardContent className="py-12 text-center">
                  <Shield className="w-12 h-12 mx-auto text-muted-foreground mb-3" />
                  <p className="text-muted-foreground">
                    Select a case from the queue to view details
                  </p>
                </CardContent>
              </Card>
            )}
          </div>
        </TabsContent>

        {/* Appeals Tab */}
        <TabsContent value="appeals">
          <AppealsQueue
            appeals={appeals ?? []}
            isLoading={appealsLoading}
            error={appealsError}
            onRefresh={refetchAppeals}
          />
        </TabsContent>

        {/* Disputes Tab */}
        <TabsContent value="disputes">
          <DisputesQueue
            disputes={disputes ?? []}
            isLoading={disputesLoading}
            error={disputesError}
            onRefresh={refetchDisputes}
          />
        </TabsContent>
      </Tabs>
    </div>
  );
}
