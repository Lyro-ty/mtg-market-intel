import { FileText } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { PageHeader } from '@/components/ornate/page-header';

export default function TermsPage() {
  return (
    <div className="container mx-auto px-4 py-8 space-y-8 max-w-4xl">
      <PageHeader
        title="Terms of Service"
        subtitle="Last updated: December 2024"
      />

      <Card className="glow-accent">
        <CardContent className="p-8 prose prose-invert max-w-none">
          <div className="flex items-center gap-3 mb-6 not-prose">
            <FileText className="w-8 h-8 text-[rgb(var(--accent))]" />
            <p className="text-lg text-muted-foreground">
              By using Dualcaster Deals, you agree to these terms.
            </p>
          </div>

          <h2 className="font-heading text-xl text-foreground mt-8 mb-4">1. Acceptance of Terms</h2>
          <p className="text-muted-foreground mb-4">
            By accessing or using Dualcaster Deals, you agree to be bound by these Terms of Service
            and our Privacy Policy. If you do not agree to these terms, please do not use our service.
          </p>

          <h2 className="font-heading text-xl text-foreground mt-8 mb-4">2. Description of Service</h2>
          <p className="text-muted-foreground mb-4">
            Dualcaster Deals provides MTG market intelligence tools including price tracking,
            collection management, and trading recommendations. The service is provided &quot;as is&quot;
            and we make no guarantees about accuracy or availability.
          </p>

          <h2 className="font-heading text-xl text-foreground mt-8 mb-4">3. User Accounts</h2>
          <p className="text-muted-foreground mb-4">
            You are responsible for:
          </p>
          <ul className="list-disc pl-6 text-muted-foreground space-y-2 mb-6">
            <li>Maintaining the confidentiality of your account credentials</li>
            <li>All activities that occur under your account</li>
            <li>Notifying us immediately of any unauthorized access</li>
            <li>Providing accurate and complete information</li>
          </ul>

          <h2 className="font-heading text-xl text-foreground mt-8 mb-4">4. Acceptable Use</h2>
          <p className="text-muted-foreground mb-4">
            You agree not to:
          </p>
          <ul className="list-disc pl-6 text-muted-foreground space-y-2 mb-6">
            <li>Use the service for any illegal purpose</li>
            <li>Attempt to gain unauthorized access to our systems</li>
            <li>Scrape, copy, or redistribute our data without permission</li>
            <li>Interfere with or disrupt the service</li>
            <li>Create multiple accounts to circumvent limitations</li>
          </ul>

          <h2 className="font-heading text-xl text-foreground mt-8 mb-4">5. Intellectual Property</h2>
          <p className="text-muted-foreground mb-4">
            The Dualcaster Deals name, logo, and original content are our intellectual property.
            Card names, images, and related content are property of Wizards of the Coast.
            See our Attributions page for complete licensing information.
          </p>

          <h2 className="font-heading text-xl text-foreground mt-8 mb-4">6. Disclaimer of Warranties</h2>
          <p className="text-muted-foreground mb-4">
            THE SERVICE IS PROVIDED &quot;AS IS&quot; WITHOUT WARRANTIES OF ANY KIND. We do not guarantee:
          </p>
          <ul className="list-disc pl-6 text-muted-foreground space-y-2 mb-6">
            <li>Accuracy of pricing data or recommendations</li>
            <li>Continuous, uninterrupted access to the service</li>
            <li>That the service will meet your specific requirements</li>
            <li>Financial outcomes from following our recommendations</li>
          </ul>

          <h2 className="font-heading text-xl text-foreground mt-8 mb-4">7. Limitation of Liability</h2>
          <p className="text-muted-foreground mb-4">
            In no event shall Dualcaster Deals be liable for any indirect, incidental, special,
            consequential, or punitive damages, including but not limited to loss of profits,
            data, or other intangible losses resulting from your use of the service.
          </p>

          <h2 className="font-heading text-xl text-foreground mt-8 mb-4">8. Financial Disclaimer</h2>
          <p className="text-muted-foreground mb-4">
            Our recommendations are for informational purposes only and do not constitute
            financial advice. MTG card values can fluctuate significantly. Always do your
            own research before making purchasing decisions.
          </p>

          <h2 className="font-heading text-xl text-foreground mt-8 mb-4">9. Termination</h2>
          <p className="text-muted-foreground mb-4">
            We reserve the right to suspend or terminate your account at any time for
            violations of these terms. You may delete your account at any time through
            the Settings page.
          </p>

          <h2 className="font-heading text-xl text-foreground mt-8 mb-4">10. Changes to Terms</h2>
          <p className="text-muted-foreground mb-4">
            We may modify these terms at any time. Continued use of the service after
            changes constitutes acceptance of the new terms.
          </p>

          <h2 className="font-heading text-xl text-foreground mt-8 mb-4">11. Contact</h2>
          <p className="text-muted-foreground">
            Questions about these terms? Contact us at{' '}
            <a href="mailto:legal@dualcasterdeals.com" className="text-[rgb(var(--accent))] hover:underline">
              legal@dualcasterdeals.com
            </a>
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
