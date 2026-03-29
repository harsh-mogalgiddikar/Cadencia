import LandingNavbar from "@/components/layout/Navbar";
import Footer from "@/components/layout/Footer";
import HeroSection from "@/components/landing/HeroSection";
import LogoStrip from "@/components/landing/LogoStrip";
import FeaturesGrid from "@/components/landing/FeaturesGrid";
import HowItWorks from "@/components/landing/HowItWorks";
import LiveDemoSection from "@/components/landing/LiveDemoSection";
import StatsSection from "@/components/landing/StatsSection";
import PricingTeaser from "@/components/landing/PricingTeaser";
import CTABanner from "@/components/landing/CTABanner";

export default function LandingPage() {
  return (
    <>
      <LandingNavbar />
      <main>
        <HeroSection />
        <LogoStrip />
        <FeaturesGrid />
        <HowItWorks />
        <LiveDemoSection />
        <StatsSection />
        <PricingTeaser />
        <CTABanner />
      </main>
      <Footer />
    </>
  );
}
