'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Monitor, Smartphone, Trash2, LogOut } from 'lucide-react';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { fetchApi } from '@/lib/api';

interface Session {
  id: number;
  device_info: string | null;
  ip_address: string | null;
  created_at: string;
  last_active: string;
  is_current: boolean;
}

export function SessionsManager() {
  const queryClient = useQueryClient();

  const { data: sessions, isLoading, isError } = useQuery<Session[]>({
    queryKey: ['sessions'],
    queryFn: () => fetchApi<Session[]>('/sessions', {}, true),
  });

  const revokeMutation = useMutation({
    mutationFn: (sessionId: number) => fetchApi<void>(`/sessions/${sessionId}`, { method: 'DELETE' }, true),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['sessions'] }),
  });

  const revokeAllMutation = useMutation({
    mutationFn: () => fetchApi<void>('/sessions', { method: 'DELETE' }, true),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['sessions'] }),
  });

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const getDeviceIcon = (deviceInfo: string | null) => {
    if (deviceInfo?.toLowerCase().includes('mobile')) {
      return <Smartphone className="w-5 h-5" />;
    }
    return <Monitor className="w-5 h-5" />;
  };

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle>Active Sessions</CardTitle>
            <CardDescription>Manage your logged-in devices</CardDescription>
          </div>
          <Button
            variant="danger"
            size="sm"
            onClick={() => {
              if (window.confirm('Are you sure you want to log out of all devices? You will need to log in again.')) {
                revokeAllMutation.mutate();
              }
            }}
            disabled={revokeAllMutation.isPending}
          >
            <LogOut className="w-4 h-4 mr-2" />
            Log out all devices
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        {isError ? (
          <p className="text-red-500">Failed to load sessions. Please try again.</p>
        ) : isLoading ? (
          <p className="text-[rgb(var(--muted-foreground))]">Loading sessions...</p>
        ) : sessions?.length === 0 ? (
          <p className="text-[rgb(var(--muted-foreground))]">No active sessions</p>
        ) : (
          <div className="space-y-3">
            {sessions?.map((session) => (
              <div
                key={session.id}
                className="flex items-center justify-between p-4 rounded-lg bg-[rgb(var(--secondary))]"
              >
                <div className="flex items-center gap-4">
                  <div className="p-2 rounded-lg bg-[rgb(var(--background))]">
                    {getDeviceIcon(session.device_info)}
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <p className="font-medium text-[rgb(var(--foreground))]">
                        {session.device_info || 'Unknown Device'}
                      </p>
                      {session.is_current && (
                        <Badge variant="success" size="sm">Current</Badge>
                      )}
                    </div>
                    <p className="text-sm text-[rgb(var(--muted-foreground))]">
                      {session.ip_address || 'Unknown IP'} - Last active {formatDate(session.last_active)}
                    </p>
                  </div>
                </div>
                {!session.is_current && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => revokeMutation.mutate(session.id)}
                    disabled={revokeMutation.isPending}
                    aria-label="Revoke session"
                  >
                    <Trash2 className="w-4 h-4" />
                  </Button>
                )}
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
