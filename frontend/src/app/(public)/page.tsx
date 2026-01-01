import { ConstellationHero } from '@/components/features/landing/constellation-hero';
import { FeaturesGrid } from '@/components/features/landing/FeaturesGrid';
import { LiveMarketPreview } from '@/components/features/landing/LiveMarketPreview';
import { StoreOwnersSection } from '@/components/features/landing/StoreOwnersSection';
import { FinalCTA } from '@/components/features/landing/FinalCTA';

export default function LandingPage() {
  return (
    <>
      <ConstellationHero />
      <FeaturesGrid />
      <LiveMarketPreview />
      <StoreOwnersSection />
      <FinalCTA />
    </>
  );
}
