'use client';

import { PageTransition } from '@/components/layout/PageTransition';

/**
 * AppLayout - Minimal wrapper for page transitions.
 *
 * All actual layout (headers, sidebars, footers) is handled by:
 * - (protected)/layout.tsx - SidebarProvider + AppSidebar + SiteHeader
 * - (public)/layout.tsx - PublicHeader/Footer OR Sidebar+SiteHeader (if logged in)
 */
export function AppLayout({ children }: { children: React.ReactNode }) {
  return <PageTransition>{children}</PageTransition>;
}




