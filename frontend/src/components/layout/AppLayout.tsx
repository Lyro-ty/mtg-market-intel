'use client';

import { usePathname } from 'next/navigation';
import { TopNav } from '@/components/layout/TopNav';
import { MobileNav } from '@/components/layout/MobileNav';
import { PageTransition } from '@/components/layout/PageTransition';

// Routes where navigation should not be shown
const fullPageRoutes = ['/login', '/register'];
const landingPageRoute = '/';

export function AppLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const isFullPage = fullPageRoutes.some(route => pathname.startsWith(route));
  const isLandingPage = pathname === landingPageRoute;

  if (isFullPage || isLandingPage) {
    return (
      <main id="main-content" role="main">
        <PageTransition>{children}</PageTransition>
      </main>
    );
  }

  return (
    <>
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:top-4 focus:left-4 focus:z-[100] focus:px-4 focus:py-2 focus:bg-[rgb(var(--accent))] focus:text-white focus:rounded focus:outline-none focus:ring-2 focus:ring-[rgb(var(--accent))] focus:ring-offset-2"
      >
        Skip to main content
      </a>
      <div className="min-h-screen bg-[rgb(var(--background))]">
        <header role="banner">
          <TopNav />
        </header>
        <main id="main-content" role="main" className="p-4 md:p-8 pb-20 md:pb-8">
          <PageTransition>{children}</PageTransition>
        </main>
        <MobileNav />
      </div>
    </>
  );
}




