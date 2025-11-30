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
} from 'lucide-react';
import { cn } from '@/lib/utils';

const navigation = [
  { name: 'Dashboard', href: '/', icon: LayoutDashboard },
  { name: 'Search Cards', href: '/cards', icon: Search },
  { name: 'My Inventory', href: '/inventory', icon: Package },
  { name: 'Recommendations', href: '/recommendations', icon: TrendingUp },
  { name: 'Settings', href: '/settings', icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="fixed inset-y-0 left-0 w-64 bg-[rgb(var(--card))] border-r border-[rgb(var(--border))]">
      {/* Logo */}
      <div className="flex items-center gap-3 px-6 py-5 border-b border-[rgb(var(--border))]">
        <div className="p-2 rounded-lg bg-gradient-to-br from-primary-500 to-primary-700">
          <Sparkles className="w-5 h-5 text-white" />
        </div>
        <div>
          <h1 className="text-lg font-bold text-[rgb(var(--foreground))]">MTG Intel</h1>
          <p className="text-xs text-[rgb(var(--muted-foreground))]">Market Intelligence</p>
        </div>
      </div>

      {/* Navigation */}
      <nav className="px-3 py-4 space-y-1">
        {navigation.map((item) => {
          const isActive = pathname === item.href || 
            (item.href !== '/' && pathname.startsWith(item.href));
          
          return (
            <Link
              key={item.name}
              href={item.href}
              className={cn(
                'flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all',
                isActive
                  ? 'bg-primary-500/10 text-primary-500'
                  : 'text-[rgb(var(--muted-foreground))] hover:text-[rgb(var(--foreground))] hover:bg-[rgb(var(--secondary))]'
              )}
            >
              <item.icon className="w-5 h-5" />
              {item.name}
            </Link>
          );
        })}
      </nav>

      {/* Stats Footer */}
      <div className="absolute bottom-0 left-0 right-0 p-4 border-t border-[rgb(var(--border))]">
        <div className="flex items-center gap-2 text-xs text-[rgb(var(--muted-foreground))]">
          <Store className="w-4 h-4" />
          <span>3 marketplaces active</span>
        </div>
      </div>
    </aside>
  );
}

