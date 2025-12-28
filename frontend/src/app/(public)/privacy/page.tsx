import { Shield } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { PageHeader } from '@/components/ornate/page-header';

export default function PrivacyPage() {
  return (
    <div className="container mx-auto px-4 py-8 space-y-8 max-w-4xl">
      <PageHeader
        title="Privacy Policy"
        subtitle="Last updated: December 2024"
      />

      <Card className="glow-accent">
        <CardContent className="p-8 prose prose-invert max-w-none">
          <div className="flex items-center gap-3 mb-6 not-prose">
            <Shield className="w-8 h-8 text-[rgb(var(--accent))]" />
            <p className="text-lg text-muted-foreground">
              Your privacy matters to us. Here&apos;s how we handle your data.
            </p>
          </div>

          <h2 className="font-heading text-xl text-foreground mt-8 mb-4">1. Information We Collect</h2>
          <p className="text-muted-foreground mb-4">
            We collect information you provide directly to us, including:
          </p>
          <ul className="list-disc pl-6 text-muted-foreground space-y-2 mb-6">
            <li>Account information (email, username, password hash)</li>
            <li>Collection data (cards you add to your inventory)</li>
            <li>Preferences and settings</li>
            <li>Usage data and analytics</li>
          </ul>

          <h2 className="font-heading text-xl text-foreground mt-8 mb-4">2. How We Use Your Information</h2>
          <p className="text-muted-foreground mb-4">
            We use the information we collect to:
          </p>
          <ul className="list-disc pl-6 text-muted-foreground space-y-2 mb-6">
            <li>Provide, maintain, and improve our services</li>
            <li>Generate personalized recommendations for your collection</li>
            <li>Send you alerts and notifications you&apos;ve opted into</li>
            <li>Respond to your comments and questions</li>
            <li>Analyze usage patterns to improve the platform</li>
          </ul>

          <h2 className="font-heading text-xl text-foreground mt-8 mb-4">3. Information Sharing</h2>
          <p className="text-muted-foreground mb-4">
            We do not sell, trade, or rent your personal information to third parties. We may share
            aggregated, anonymized data for analytics purposes, but this data cannot be used to
            identify you personally.
          </p>

          <h2 className="font-heading text-xl text-foreground mt-8 mb-4">4. Data Security</h2>
          <p className="text-muted-foreground mb-4">
            We implement industry-standard security measures to protect your data:
          </p>
          <ul className="list-disc pl-6 text-muted-foreground space-y-2 mb-6">
            <li>Passwords are hashed using bcrypt</li>
            <li>All data is transmitted over HTTPS</li>
            <li>Database access is restricted and monitored</li>
            <li>Regular security audits and updates</li>
          </ul>

          <h2 className="font-heading text-xl text-foreground mt-8 mb-4">5. Your Rights</h2>
          <p className="text-muted-foreground mb-4">
            You have the right to:
          </p>
          <ul className="list-disc pl-6 text-muted-foreground space-y-2 mb-6">
            <li>Access your personal data</li>
            <li>Export your collection data</li>
            <li>Request deletion of your account and data</li>
            <li>Opt out of non-essential communications</li>
          </ul>

          <h2 className="font-heading text-xl text-foreground mt-8 mb-4">6. Cookies</h2>
          <p className="text-muted-foreground mb-4">
            We use essential cookies for authentication and session management. We do not use
            tracking cookies or third-party advertising cookies.
          </p>

          <h2 className="font-heading text-xl text-foreground mt-8 mb-4">7. Third-Party Services</h2>
          <p className="text-muted-foreground mb-4">
            We integrate with the following services:
          </p>
          <ul className="list-disc pl-6 text-muted-foreground space-y-2 mb-6">
            <li><strong>Scryfall</strong> - Card data and images (see their privacy policy)</li>
            <li><strong>Google OAuth</strong> - Optional sign-in (if you choose to use it)</li>
          </ul>

          <h2 className="font-heading text-xl text-foreground mt-8 mb-4">8. Changes to This Policy</h2>
          <p className="text-muted-foreground mb-4">
            We may update this privacy policy from time to time. We will notify you of any
            material changes by posting the new policy on this page and updating the
            &quot;Last updated&quot; date.
          </p>

          <h2 className="font-heading text-xl text-foreground mt-8 mb-4">9. Contact Us</h2>
          <p className="text-muted-foreground">
            If you have any questions about this Privacy Policy, please contact us at{' '}
            <a href="mailto:privacy@dualcasterdeals.com" className="text-[rgb(var(--accent))] hover:underline">
              privacy@dualcasterdeals.com
            </a>
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
