'use client';

import { usePathname } from 'next/navigation';
import { TopNav } from '@/components/layout/TopNav';
import { PageTransition } from '@/components/layout/PageTransition';

// Routes where navigation should not be shown
const fullPageRoutes = ['/login', '/register'];
const landingPageRoute = '/';

export function AppLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const isFullPage = fullPageRoutes.some(route => pathname.startsWith(route));
  const isLandingPage = pathname === landingPageRoute;

  if (isFullPage || isLandingPage) {
    return <PageTransition>{children}</PageTransition>;
  }

  return (
    <div className="min-h-screen bg-[rgb(var(--background))]">
      <TopNav />
      <main className="p-8">
        <PageTransition>{children}</PageTransition>
      </main>
    </div>
  );
}




