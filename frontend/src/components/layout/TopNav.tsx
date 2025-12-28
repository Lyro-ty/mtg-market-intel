'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  Search,
  TrendingUp,
  Settings,
  Sparkles,
  Package,
  LogIn,
  LogOut,
  User,
  Menu,
  X,
} from 'lucide-react';
import { useState } from 'react';
import { cn } from '@/lib/utils';
import { useAuth } from '@/contexts/AuthContext';
import { Button } from '@/components/ui/button';

const navigation = [
  { name: 'Search Cards', href: '/cards', icon: Search },
  { name: 'My Inventory', href: '/inventory', icon: Package, requiresAuth: true },
  { name: 'Recommendations', href: '/recommendations', icon: TrendingUp },
  { name: 'Settings', href: '/settings', icon: Settings },
];

export function TopNav() {
  const pathname = usePathname();
  const { user, isAuthenticated, logout, isLoading } = useAuth();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  // Don't show nav on login/register pages or landing page
  const isFullPage = ['/login', '/register'].some(route => pathname.startsWith(route));
  const isLandingPage = pathname === '/';

  if (isFullPage || isLandingPage) {
    return null;
  }

  return (
    <nav
      role="navigation"
      aria-label="Main navigation"
      className="sticky top-0 z-50 w-full bg-[rgb(var(--card))] border-b border-[rgb(var(--border))] backdrop-blur-sm"
    >
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Logo */}
          <Link href="/" className="flex items-center gap-3" aria-label="Dualcaster Deals - Home">
            <div className="p-2 rounded-lg bg-gradient-to-br from-amber-500 to-orange-600">
              <Sparkles className="w-5 h-5 text-white" aria-hidden="true" />
            </div>
            <div>
              <span className="text-lg font-bold text-[rgb(var(--foreground))]">Dualcaster</span>
              <p className="text-xs text-[rgb(var(--muted-foreground))]">Deals & Intelligence</p>
            </div>
          </Link>

          {/* Desktop Navigation */}
          <div className="hidden md:flex md:items-center md:gap-1">
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
                  aria-current={isActive ? 'page' : undefined}
                  className={cn(
                    'relative flex items-center gap-2 px-3 py-2 text-sm font-medium transition-all duration-200',
                    isActive
                      ? 'text-[rgb(var(--accent))]'
                      : 'text-[rgb(var(--muted-foreground))] hover:text-[rgb(var(--foreground))] hover:bg-[rgba(var(--accent),0.05)]'
                  )}
                >
                  <item.icon className="w-4 h-4" aria-hidden="true" />
                  {item.name}
                  {isActive && (
                    <span className="absolute bottom-0 left-0 right-0 h-[3px] bg-[rgb(var(--accent))]" aria-hidden="true" />
                  )}
                </Link>
              );
            })}
          </div>

          {/* User Menu / Login */}
          <div className="hidden md:flex md:items-center md:gap-4">
            {!isLoading && (
              isAuthenticated && user ? (
                <div className="flex items-center gap-4">
                  <div className="flex items-center gap-2">
                    <div className="w-8 h-8 rounded-full bg-gradient-to-br from-amber-500 to-orange-600 flex items-center justify-center">
                      <User className="w-4 h-4 text-white" aria-hidden="true" />
                    </div>
                    <div className="hidden lg:block">
                      <p className="text-sm font-medium text-[rgb(var(--foreground))]">
                        {user.display_name || user.username}
                      </p>
                    </div>
                  </div>
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={logout}
                  >
                    <LogOut className="w-4 h-4 mr-2" aria-hidden="true" />
                    Sign out
                  </Button>
                </div>
              ) : (
                <Link href="/login">
                  <Button
                    variant="primary"
                    size="sm"
                    className="bg-gradient-to-r from-amber-500 to-orange-600"
                  >
                    <LogIn className="w-4 h-4 mr-2" aria-hidden="true" />
                    Sign in
                  </Button>
                </Link>
              )
            )}
          </div>

          {/* Mobile menu button */}
          <button
            type="button"
            className="md:hidden p-2 rounded-lg text-[rgb(var(--muted-foreground))] hover:text-[rgb(var(--foreground))] hover:bg-[rgb(var(--secondary))]"
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            aria-expanded={mobileMenuOpen}
            aria-controls="mobile-menu"
            aria-label={mobileMenuOpen ? 'Close menu' : 'Open menu'}
          >
            {mobileMenuOpen ? (
              <X className="w-6 h-6" aria-hidden="true" />
            ) : (
              <Menu className="w-6 h-6" aria-hidden="true" />
            )}
          </button>
        </div>

        {/* Mobile Navigation */}
        {mobileMenuOpen && (
          <div id="mobile-menu" className="md:hidden border-t border-[rgb(var(--border))] py-4">
            <div className="space-y-1">
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
                    onClick={() => setMobileMenuOpen(false)}
                    aria-current={isActive ? 'page' : undefined}
                    className={cn(
                      'relative flex items-center gap-3 px-4 py-3 text-sm font-medium transition-all duration-200',
                      isActive
                        ? 'text-[rgb(var(--accent))] bg-[rgba(var(--accent),0.05)]'
                        : 'text-[rgb(var(--muted-foreground))] hover:text-[rgb(var(--foreground))] hover:bg-[rgba(var(--accent),0.05)]'
                    )}
                  >
                    {isActive && (
                      <span className="absolute left-0 top-0 bottom-0 w-[3px] bg-[rgb(var(--accent))]" aria-hidden="true" />
                    )}
                    <item.icon className="w-5 h-5" aria-hidden="true" />
                    {item.name}
                  </Link>
                );
              })}
            </div>
            
            {/* Mobile User Section */}
            <div className="mt-4 pt-4 border-t border-[rgb(var(--border))]">
              {!isLoading && (
                isAuthenticated && user ? (
                  <div className="space-y-3">
                    <div className="flex items-center gap-3 px-4">
                      <div className="w-9 h-9 rounded-full bg-gradient-to-br from-amber-500 to-orange-600 flex items-center justify-center">
                        <User className="w-5 h-5 text-white" aria-hidden="true" />
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
                      className="w-full justify-center mx-4"
                      onClick={() => {
                        logout();
                        setMobileMenuOpen(false);
                      }}
                    >
                      <LogOut className="w-4 h-4 mr-2" aria-hidden="true" />
                      Sign out
                    </Button>
                  </div>
                ) : (
                  <div className="px-4 space-y-2">
                    <Link href="/login" onClick={() => setMobileMenuOpen(false)}>
                      <Button
                        variant="primary"
                        size="sm"
                        className="w-full justify-center bg-gradient-to-r from-amber-500 to-orange-600"
                      >
                        <LogIn className="w-4 h-4 mr-2" aria-hidden="true" />
                        Sign in
                      </Button>
                    </Link>
                    <p className="text-center text-xs text-[rgb(var(--muted-foreground))]">
                      <Link href="/register" className="text-amber-500 hover:text-amber-400">
                        Create account
                      </Link>
                    </p>
                  </div>
                )
              )}
            </div>
          </div>
        )}
      </div>
    </nav>
  );
}

