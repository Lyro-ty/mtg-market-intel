'use client';

import { usePathname } from 'next/navigation';
import { TopNav } from '@/components/layout/TopNav';

// Routes where navigation should not be shown
const fullPageRoutes = ['/login', '/register'];
const landingPageRoute = '/';

export function AppLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const isFullPage = fullPageRoutes.some(route => pathname.startsWith(route));
  const isLandingPage = pathname === landingPageRoute;

  if (isFullPage || isLandingPage) {
    return <>{children}</>;
  }

  return (
    <div className="min-h-screen bg-[rgb(var(--background))]">
      <TopNav />
      <main className="p-8">
        {children}
      </main>
    </div>
  );
}




