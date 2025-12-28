import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import './fonts.css';
import './globals.css';
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
        <Providers>
          <AppLayout>
            {children}
          </AppLayout>
        </Providers>
      </body>
    </html>
  );
}

