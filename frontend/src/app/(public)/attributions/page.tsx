import { Heart, ExternalLink } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { PageHeader } from '@/components/ornate/page-header';

const attributions = [
  {
    name: 'Wizards of the Coast',
    description: 'Magic: The Gathering card content',
    license: 'Fan Content Policy',
    url: 'https://company.wizards.com/en/legal/fancontentpolicy',
    note: 'Dualcaster Deals is unofficial Fan Content permitted under the Fan Content Policy. Not approved/endorsed by Wizards. Portions of the materials used are property of Wizards of the Coast. ©Wizards of the Coast LLC.',
  },
  {
    name: 'Scryfall',
    description: 'Card database, images, and pricing data',
    license: 'Scryfall API Terms',
    url: 'https://scryfall.com/',
    note: 'Card data and images provided by Scryfall. Scryfall is not affiliated with Dualcaster Deals.',
  },
  {
    name: 'TopDeck.gg',
    description: 'Tournament data and meta analysis',
    license: 'API Partnership',
    url: 'https://topdeck.gg/',
    note: 'Tournament results and standings data provided by TopDeck.gg.',
  },
  {
    name: 'game-icons.net',
    description: 'Custom MTG-themed icons',
    license: 'CC BY 3.0',
    url: 'https://game-icons.net/',
    note: 'Icons by various artists at game-icons.net, used under Creative Commons Attribution 3.0 license.',
  },
  {
    name: 'Lucide Icons',
    description: 'UI icons throughout the application',
    license: 'ISC License',
    url: 'https://lucide.dev/',
    note: 'Beautiful & consistent icons used throughout the interface.',
  },
  {
    name: 'shadcn/ui',
    description: 'Component library foundation',
    license: 'MIT License',
    url: 'https://ui.shadcn.com/',
    note: 'Beautifully designed components built with Radix UI and Tailwind CSS.',
  },
  {
    name: 'Cinzel & Inter',
    description: 'Typography',
    license: 'Open Font License',
    url: 'https://fonts.google.com/',
    note: 'Cinzel Decorative for display text, Inter for body text.',
  },
];

const openSourceLibraries = [
  { name: 'Next.js', description: 'React framework', url: 'https://nextjs.org/' },
  { name: 'React', description: 'UI library', url: 'https://react.dev/' },
  { name: 'Tailwind CSS', description: 'Utility-first CSS', url: 'https://tailwindcss.com/' },
  { name: 'Radix UI', description: 'Accessible components', url: 'https://www.radix-ui.com/' },
  { name: 'TanStack Query', description: 'Data fetching', url: 'https://tanstack.com/query' },
  { name: 'Recharts', description: 'Charting library', url: 'https://recharts.org/' },
  { name: 'FastAPI', description: 'Python API framework', url: 'https://fastapi.tiangolo.com/' },
  { name: 'SQLAlchemy', description: 'Database ORM', url: 'https://www.sqlalchemy.org/' },
];

export default function AttributionsPage() {
  return (
    <div className="container mx-auto px-4 py-8 space-y-8 max-w-4xl">
      <PageHeader
        title="Attributions"
        subtitle="Credits and licenses for content and tools we use"
      />

      {/* Thank You */}
      <Card className="glow-accent bg-gradient-to-br from-[rgb(var(--accent))]/10 to-[rgb(var(--magic-gold))]/5">
        <CardContent className="p-6 text-center">
          <Heart className="w-10 h-10 mx-auto text-[rgb(var(--destructive))] mb-3" />
          <p className="text-muted-foreground">
            Dualcaster Deals is made possible by the generous work of many creators,
            open source projects, and data providers. Thank you!
          </p>
        </CardContent>
      </Card>

      {/* Main Attributions */}
      <div className="space-y-4">
        <h2 className="font-display text-xl text-foreground">Content & Data Sources</h2>
        {attributions.map((attr) => (
          <Card key={attr.name} className="glow-accent">
            <CardContent className="p-6">
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    <h3 className="font-heading font-medium text-foreground">{attr.name}</h3>
                    <a
                      href={attr.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-[rgb(var(--accent))] hover:text-[rgb(var(--accent))]/80"
                    >
                      <ExternalLink className="w-4 h-4" />
                    </a>
                  </div>
                  <p className="text-sm text-muted-foreground mb-2">{attr.description}</p>
                  <p className="text-sm text-muted-foreground italic">{attr.note}</p>
                </div>
                <span className="text-xs bg-secondary px-2 py-1 rounded text-muted-foreground shrink-0">
                  {attr.license}
                </span>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Open Source Libraries */}
      <Card className="glow-accent">
        <CardHeader>
          <CardTitle>Open Source Libraries</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {openSourceLibraries.map((lib) => (
              <a
                key={lib.name}
                href={lib.url}
                target="_blank"
                rel="noopener noreferrer"
                className="p-3 rounded-lg bg-secondary/50 hover:bg-secondary transition-colors text-center"
              >
                <p className="font-medium text-foreground text-sm">{lib.name}</p>
                <p className="text-xs text-muted-foreground">{lib.description}</p>
              </a>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* WotC Fan Content Policy */}
      <Card className="border-[rgb(var(--warning))]/30 bg-[rgb(var(--warning))]/5">
        <CardContent className="p-6">
          <h3 className="font-heading font-medium text-foreground mb-3">
            Wizards of the Coast Fan Content Policy
          </h3>
          <p className="text-sm text-muted-foreground">
            Dualcaster Deals is unofficial Fan Content permitted under the Fan Content Policy.
            Not approved/endorsed by Wizards. Portions of the materials used are property of
            Wizards of the Coast. ©Wizards of the Coast LLC.
          </p>
          <p className="text-sm text-muted-foreground mt-3">
            Magic: The Gathering, the mana symbols, and all related characters and elements
            are trademarks of Wizards of the Coast LLC in the USA and other countries.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
