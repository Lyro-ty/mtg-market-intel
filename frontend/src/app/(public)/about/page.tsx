import {
  Sparkles,
  Target,
  TrendingUp,
  Shield,
  Users,
  Zap,
  BarChart3,
  Bell,
  Database,
} from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { PageHeader } from '@/components/ornate/page-header';
import { cn } from '@/lib/utils';

const features = [
  {
    icon: BarChart3,
    title: 'Real-Time Market Data',
    description: 'Track prices across multiple marketplaces with updates every 30 minutes.',
    color: 'accent',
  },
  {
    icon: TrendingUp,
    title: 'AI-Powered Recommendations',
    description: 'Get intelligent buy, sell, and hold signals based on market trends and your portfolio.',
    color: 'success',
  },
  {
    icon: Bell,
    title: 'Price Alerts',
    description: 'Set target prices and get notified when cards hit your thresholds.',
    color: 'magic-gold',
  },
  {
    icon: Target,
    title: 'Portfolio Tracking',
    description: 'Monitor your collection value, profit/loss, and performance over time.',
    color: 'mythic-orange',
  },
  {
    icon: Database,
    title: 'Comprehensive Card Data',
    description: 'Access detailed information on 90,000+ cards powered by Scryfall.',
    color: 'magic-blue',
  },
  {
    icon: Zap,
    title: 'Tournament Insights',
    description: 'See which cards are winning tournaments with data from TopDeck.gg.',
    color: 'magic-purple',
  },
];

const values = [
  {
    title: 'Data-Driven Decisions',
    description: 'We believe every collector and trader deserves access to professional-grade market intelligence.',
  },
  {
    title: 'Community First',
    description: 'Built by MTG players, for MTG players. We understand what matters to collectors.',
  },
  {
    title: 'Transparency',
    description: 'Our recommendations show their reasoning. No black boxes, just clear analysis.',
  },
];

export default function AboutPage() {
  return (
    <div className="container mx-auto px-4 py-8 space-y-12">
      <PageHeader
        title="About Dualcaster Deals"
        subtitle="Your MTG market intelligence platform"
      />

      {/* Mission Statement */}
      <Card className="glow-accent bg-gradient-to-br from-[rgb(var(--accent))]/10 to-[rgb(var(--magic-gold))]/5">
        <CardContent className="p-8 text-center">
          <Sparkles className="w-12 h-12 mx-auto text-[rgb(var(--magic-gold))] mb-4" />
          <h2 className="font-display text-2xl text-foreground mb-4">Our Mission</h2>
          <p className="text-lg text-muted-foreground max-w-2xl mx-auto">
            Dualcaster Deals empowers Magic: The Gathering collectors and traders with
            real-time market intelligence, helping you make informed decisions about your
            collection. Whether you&apos;re a casual collector or a serious trader, we provide
            the tools you need to maximize value.
          </p>
        </CardContent>
      </Card>

      {/* Features Grid */}
      <section>
        <h2 className="font-display text-2xl text-foreground text-center mb-8">
          What We Offer
        </h2>
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
          {features.map((feature) => {
            const Icon = feature.icon;
            return (
              <Card key={feature.title} className="glow-accent hover:border-[rgb(var(--accent))]/30 transition-colors">
                <CardContent className="p-6">
                  <div className={cn(
                    'w-12 h-12 rounded-lg flex items-center justify-center mb-4',
                    `bg-[rgb(var(--${feature.color}))]/10`
                  )}>
                    <Icon className={`w-6 h-6 text-[rgb(var(--${feature.color}))]`} />
                  </div>
                  <h3 className="font-heading text-lg font-medium text-foreground mb-2">
                    {feature.title}
                  </h3>
                  <p className="text-muted-foreground">{feature.description}</p>
                </CardContent>
              </Card>
            );
          })}
        </div>
      </section>

      {/* Values */}
      <section>
        <h2 className="font-display text-2xl text-foreground text-center mb-8">
          Our Values
        </h2>
        <div className="grid md:grid-cols-3 gap-6">
          {values.map((value, i) => (
            <Card key={value.title} className="glow-accent">
              <CardContent className="p-6 text-center">
                <div className="w-10 h-10 rounded-full bg-[rgb(var(--accent))]/20 flex items-center justify-center mx-auto mb-4">
                  <span className="font-display text-lg text-[rgb(var(--accent))]">{i + 1}</span>
                </div>
                <h3 className="font-heading text-lg font-medium text-foreground mb-2">
                  {value.title}
                </h3>
                <p className="text-muted-foreground">{value.description}</p>
              </CardContent>
            </Card>
          ))}
        </div>
      </section>

      {/* Data Sources */}
      <section>
        <Card className="glow-accent">
          <CardContent className="p-8">
            <h2 className="font-display text-2xl text-foreground text-center mb-6">
              Powered By
            </h2>
            <div className="grid md:grid-cols-3 gap-8 text-center">
              <div>
                <h3 className="font-heading font-medium text-foreground mb-2">Scryfall</h3>
                <p className="text-sm text-muted-foreground">
                  Comprehensive card database with high-quality images and metadata.
                </p>
              </div>
              <div>
                <h3 className="font-heading font-medium text-foreground mb-2">TopDeck.gg</h3>
                <p className="text-sm text-muted-foreground">
                  Tournament data and meta analysis to track competitive trends.
                </p>
              </div>
              <div>
                <h3 className="font-heading font-medium text-foreground mb-2">TCGPlayer</h3>
                <p className="text-sm text-muted-foreground">
                  Real-time pricing data from the largest MTG marketplace.
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      </section>

      {/* Team */}
      <section className="text-center">
        <Users className="w-10 h-10 mx-auto text-[rgb(var(--accent))] mb-4" />
        <h2 className="font-display text-2xl text-foreground mb-4">
          Built by Collectors, for Collectors
        </h2>
        <p className="text-muted-foreground max-w-2xl mx-auto">
          Dualcaster Deals was created by a team of passionate MTG players who wanted
          better tools for managing their collections. We&apos;ve been playing Magic for
          years and understand the challenges of navigating the secondary market.
        </p>
      </section>

      {/* Legal Disclaimer */}
      <Card className="border-border bg-secondary/30">
        <CardContent className="p-6 text-center text-sm text-muted-foreground">
          <p className="mb-2">
            <strong>Fan Content Policy</strong>
          </p>
          <p>
            Dualcaster Deals is unofficial Fan Content permitted under the Fan Content Policy.
            Not approved/endorsed by Wizards. Portions of the materials used are property of
            Wizards of the Coast. &copy;Wizards of the Coast LLC.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
