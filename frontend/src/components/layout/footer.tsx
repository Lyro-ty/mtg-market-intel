import Link from 'next/link';
import { OrnateDivider } from '@/components/ornate/divider';

export function Footer() {
  return (
    <footer className="border-t border-border bg-card">
      <div className="max-w-7xl mx-auto px-6 py-12">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-8">
          <div>
            <h4 className="font-heading text-sm font-semibold mb-4">Product</h4>
            <ul className="space-y-2 text-sm text-muted-foreground">
              <li><Link href="/market" className="hover:text-foreground">Market</Link></li>
              <li><Link href="/cards" className="hover:text-foreground">Card Search</Link></li>
              <li><Link href="/tournaments" className="hover:text-foreground">Tournaments</Link></li>
            </ul>
          </div>
          <div>
            <h4 className="font-heading text-sm font-semibold mb-4">Company</h4>
            <ul className="space-y-2 text-sm text-muted-foreground">
              <li><Link href="/about" className="hover:text-foreground">About</Link></li>
              <li><Link href="/contact" className="hover:text-foreground">Contact</Link></li>
              <li><Link href="/changelog" className="hover:text-foreground">Changelog</Link></li>
            </ul>
          </div>
          <div>
            <h4 className="font-heading text-sm font-semibold mb-4">Support</h4>
            <ul className="space-y-2 text-sm text-muted-foreground">
              <li><Link href="/help" className="hover:text-foreground">Help & FAQ</Link></li>
              <li><a href="mailto:support@dualcasterdeals.com" className="hover:text-foreground">Email Support</a></li>
            </ul>
          </div>
          <div>
            <h4 className="font-heading text-sm font-semibold mb-4">Legal</h4>
            <ul className="space-y-2 text-sm text-muted-foreground">
              <li><Link href="/privacy" className="hover:text-foreground">Privacy Policy</Link></li>
              <li><Link href="/terms" className="hover:text-foreground">Terms of Service</Link></li>
              <li><Link href="/attributions" className="hover:text-foreground">Attributions</Link></li>
            </ul>
          </div>
        </div>

        <OrnateDivider className="my-8" />

        <div className="flex flex-col md:flex-row justify-between items-center gap-4 text-sm text-muted-foreground">
          <p>&copy; 2025 Dualcaster Deals. Not affiliated with Wizards of the Coast.</p>
          <a href="mailto:support@dualcasterdeals.com" className="hover:text-[rgb(var(--accent))]">
            support@dualcasterdeals.com
          </a>
        </div>
      </div>
    </footer>
  );
}
