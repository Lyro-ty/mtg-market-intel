'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { SidebarInset, SidebarProvider } from '@/components/ui/sidebar';
import { AppSidebar } from '@/components/layout/app-sidebar';
import { SiteHeader } from '@/components/layout/site-header';
import { useAuth } from '@/contexts/AuthContext';

export default function ProtectedLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { user, isLoading, isOAuthPending } = useAuth();
  const router = useRouter();

  useEffect(() => {
    // Don't redirect during OAuth callback processing
    if (isOAuthPending) return;

    if (!isLoading && !user) {
      router.push('/login');
    }
  }, [user, isLoading, isOAuthPending, router]);

  // Show loading during auth initialization or OAuth processing
  if (isLoading || isOAuthPending) {
    return (
      <div className="flex h-screen items-center justify-center">
        <div className="animate-pulse text-muted-foreground">Loading...</div>
      </div>
    );
  }

  if (!user) {
    return null;
  }

  return (
    <SidebarProvider>
      <AppSidebar />
      <SidebarInset>
        <SiteHeader />
        <main className="flex-1 min-w-0 p-6 overflow-x-hidden">{children}</main>
      </SidebarInset>
    </SidebarProvider>
  );
}
