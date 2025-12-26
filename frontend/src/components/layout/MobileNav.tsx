'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { Home, Search, Package, TrendingUp, Settings } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useAuth } from '@/contexts/AuthContext';

const NAV_ITEMS = [
  { href: '/dashboard', label: 'Home', icon: Home },
  { href: '/cards', label: 'Cards', icon: Search },
  { href: '/inventory', label: 'Inventory', icon: Package, requiresAuth: true },
  { href: '/recommendations', label: 'Recs', icon: TrendingUp },
  { href: '/settings', label: 'Settings', icon: Settings },
];

export function MobileNav() {
  const pathname = usePathname();
  const { isAuthenticated } = useAuth();

  return (
    <nav
      role="navigation"
      aria-label="Mobile navigation"
      className="fixed bottom-0 left-0 right-0 z-40 bg-[rgb(var(--surface))] border-t border-[rgb(var(--border))] md:hidden safe-area-inset-bottom"
    >
      <div className="flex justify-around items-center h-16 px-2">
        {NAV_ITEMS.map((item) => {
          // Skip auth-required items if not authenticated
          if (item.requiresAuth && !isAuthenticated) {
            return null;
          }

          const isActive = pathname === item.href || pathname.startsWith(item.href + '/');
          const Icon = item.icon;

          return (
            <Link
              key={item.href}
              href={item.href}
              aria-current={isActive ? 'page' : undefined}
              className={cn(
                'flex flex-col items-center justify-center gap-1 px-3 py-2 rounded-lg transition-colors min-w-[60px]',
                isActive
                  ? 'text-[rgb(var(--accent))]'
                  : 'text-[rgb(var(--muted-foreground))] hover:text-[rgb(var(--foreground))]'
              )}
            >
              <Icon className="w-5 h-5" aria-hidden="true" />
              <span className="text-xs font-medium">{item.label}</span>
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
