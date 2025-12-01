'use client';

import { usePathname } from 'next/navigation';
import { Sidebar } from '@/components/ui/Sidebar';

// Routes where sidebar should not be shown
const fullPageRoutes = ['/login', '/register'];

export function AppLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const isFullPage = fullPageRoutes.some(route => pathname.startsWith(route));

  if (isFullPage) {
    return <>{children}</>;
  }

  return (
    <div className="flex min-h-screen bg-[rgb(var(--background))]">
      <Sidebar />
      <main className="flex-1 ml-64 p-8">
        {children}
      </main>
    </div>
  );
}


