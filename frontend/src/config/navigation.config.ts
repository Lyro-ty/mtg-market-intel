// frontend/src/config/navigation.config.ts
import {
  LayoutDashboard,
  Search,
  Package,
  Star,
  TrendingUp,
  Lightbulb,
  BarChart3,
  Trophy,
  Settings,
  HelpCircle,
  FileText,
  Store,
  Calendar,
  type LucideIcon,
} from 'lucide-react';

export interface NavItem {
  title: string;
  href: string;
  icon: LucideIcon;
  requiresAuth?: boolean;
  badge?: string;
}

export interface NavSection {
  title: string;
  items: NavItem[];
}

export const mainNavItems: NavItem[] = [
  { title: 'Dashboard', href: '/dashboard', icon: LayoutDashboard, requiresAuth: true },
  { title: 'Market', href: '/market', icon: BarChart3 },
  { title: 'Cards', href: '/cards', icon: Search },
  { title: 'Tournaments', href: '/tournaments', icon: Trophy },
  { title: 'Stores', href: '/stores', icon: Store },
  { title: 'Events', href: '/events', icon: Calendar },
];

export const collectionNavItems: NavItem[] = [
  { title: 'Inventory', href: '/inventory', icon: Package, requiresAuth: true },
  { title: 'Collection', href: '/collection', icon: Package, requiresAuth: true },
  { title: 'Want List', href: '/want-list', icon: Star, requiresAuth: true },
  { title: 'Trade Quotes', href: '/quotes', icon: FileText, requiresAuth: true },
];

export const insightsNavItems: NavItem[] = [
  { title: 'Recommendations', href: '/recommendations', icon: TrendingUp, requiresAuth: true },
  { title: 'Insights', href: '/insights', icon: Lightbulb, requiresAuth: true },
];

export const storeNavItems: NavItem[] = [
  { title: 'Trading Post', href: '/store', icon: Store, requiresAuth: true },
];

export const bottomNavItems: NavItem[] = [
  { title: 'Settings', href: '/settings', icon: Settings, requiresAuth: true },
  { title: 'Help', href: '/help', icon: HelpCircle },
];
