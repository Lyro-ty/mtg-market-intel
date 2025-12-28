'use client';

import { usePathname } from 'next/navigation';
import { TopNav } from '@/components/layout/TopNav';
import { MobileNav } from '@/components/layout/MobileNav';
import { PageTransition } from '@/components/layout/PageTransition';

// Routes that have their own layout (public routes with header/footer)
// These routes use the (public) layout group instead
const publicRoutes = ['/', '/login', '/register'];

export function AppLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const isPublicRoute = publicRoutes.includes(pathname);

  // Public routes have their own layout with header/footer
  if (isPublicRoute) {
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




