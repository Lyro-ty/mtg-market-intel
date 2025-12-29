'use client';

import { SidebarTrigger } from '@/components/ui/sidebar';
import { Separator } from '@/components/ui/separator';
import { useAuth } from '@/contexts/AuthContext';
import { NotificationBell } from '@/components/layout/NotificationBell';
import { SearchAutocomplete } from '@/components/search/SearchAutocomplete';
import { Button } from '@/components/ui/button';
import Link from 'next/link';

export function SiteHeader() {
  const { user } = useAuth();

  return (
    <header className="flex h-14 shrink-0 items-center gap-2 border-b border-border px-4">
      <SidebarTrigger className="-ml-1" />
      <Separator orientation="vertical" className="mr-2 h-4" />

      {/* Search */}
      <div className="flex-1 max-w-sm">
        <SearchAutocomplete placeholder="Search cards..." />
      </div>

      {/* Right side */}
      <div className="flex items-center gap-2">
        {user && <NotificationBell />}
        {!user && (
          <div className="flex items-center gap-2">
            <Button variant="ghost" asChild>
              <Link href="/login">Login</Link>
            </Button>
            <Button asChild>
              <Link href="/register">Get Started</Link>
            </Button>
          </div>
        )}
      </div>
    </header>
  );
}
