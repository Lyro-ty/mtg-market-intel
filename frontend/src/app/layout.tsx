import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import './fonts.css';
import './globals.css';
import '@/styles/ornate.css';
import { Providers } from './providers';
import { AppLayout } from '@/components/layout/AppLayout';

const inter = Inter({ subsets: ['latin'], variable: '--font-geist-sans' });

export const metadata: Metadata = {
  title: 'Dualcaster Deals',
  description: 'Magic: The Gathering card market intelligence, analytics, and trading recommendations',
  other: {
    'impact-site-verification': '3b7dfe6f-b78f-491e-89fa-6de9fe51a333',
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className={`${inter.variable} font-sans antialiased`}>
        {/* Skip to main content link for accessibility */}
        <a
          href="#main-content"
          className="skip-link sr-only-focusable"
        >
          Skip to main content
        </a>
        <Providers>
          <AppLayout>
            <main id="main-content">
              {children}
            </main>
          </AppLayout>
        </Providers>
      </body>
    </html>
  );
}

