'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  LayoutDashboard,
  Search,
  TrendingUp,
  Settings,
  Sparkles,
  Store,
  Package,
  LogIn,
  LogOut,
  User,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { useAuth } from '@/contexts/AuthContext';
import { Button } from '@/components/ui/Button';

const navigation = [
  { name: 'Dashboard', href: '/', icon: LayoutDashboard },
  { name: 'Search Cards', href: '/cards', icon: Search },
  { name: 'My Inventory', href: '/inventory', icon: Package, requiresAuth: true },
  { name: 'Recommendations', href: '/recommendations', icon: TrendingUp },
  { name: 'Settings', href: '/settings', icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();
  const { user, isAuthenticated, logout, isLoading } = useAuth();

  return (
    <aside className="fixed inset-y-0 left-0 w-64 bg-[rgb(var(--card))] border-r border-[rgb(var(--border))]">
      {/* Logo */}
      <div className="flex items-center gap-3 px-6 py-5 border-b border-[rgb(var(--border))]">
        <div className="p-2 rounded-lg bg-gradient-to-br from-amber-500 to-orange-600">
          <Sparkles className="w-5 h-5 text-white" />
        </div>
        <div>
          <h1 className="text-lg font-bold text-[rgb(var(--foreground))]">Dualcaster</h1>
          <p className="text-xs text-[rgb(var(--muted-foreground))]">Deals & Intelligence</p>
        </div>
      </div>

      {/* Navigation */}
      <nav className="px-3 py-4 space-y-1">
        {navigation.map((item) => {
          const isActive = pathname === item.href || 
            (item.href !== '/' && pathname.startsWith(item.href));
          
          // Skip auth-required items if not authenticated
          if (item.requiresAuth && !isAuthenticated) {
            return null;
          }
          
          return (
            <Link
              key={item.name}
              href={item.href}
              className={cn(
                'flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all',
                isActive
                  ? 'bg-amber-500/10 text-amber-500'
                  : 'text-[rgb(var(--muted-foreground))] hover:text-[rgb(var(--foreground))] hover:bg-[rgb(var(--secondary))]'
              )}
            >
              <item.icon className="w-5 h-5" />
              {item.name}
            </Link>
          );
        })}
      </nav>

      {/* User section */}
      <div className="absolute bottom-0 left-0 right-0 border-t border-[rgb(var(--border))]">
        {!isLoading && (
          isAuthenticated && user ? (
            <div className="p-4 space-y-3">
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-full bg-gradient-to-br from-amber-500 to-orange-600 flex items-center justify-center">
                  <User className="w-5 h-5 text-white" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-[rgb(var(--foreground))] truncate">
                    {user.display_name || user.username}
                  </p>
                  <p className="text-xs text-[rgb(var(--muted-foreground))] truncate">
                    {user.email}
                  </p>
                </div>
              </div>
              <Button
                variant="secondary"
                size="sm"
                className="w-full justify-center"
                onClick={logout}
              >
                <LogOut className="w-4 h-4 mr-2" />
                Sign out
              </Button>
            </div>
          ) : (
            <div className="p-4">
              <Link href="/login">
                <Button
                  variant="primary"
                  size="sm"
                  className="w-full justify-center bg-gradient-to-r from-amber-500 to-orange-600"
                >
                  <LogIn className="w-4 h-4 mr-2" />
                  Sign in
                </Button>
              </Link>
              <p className="mt-2 text-center text-xs text-[rgb(var(--muted-foreground))]">
                <Link href="/register" className="text-amber-500 hover:text-amber-400">
                  Create account
                </Link>
              </p>
            </div>
          )
        )}
      </div>
    </aside>
  );
}

