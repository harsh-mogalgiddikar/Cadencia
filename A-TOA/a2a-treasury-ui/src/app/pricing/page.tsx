import type { Metadata } from "next";
import LandingNavbar from "@/components/layout/Navbar";
import Footer from "@/components/layout/Footer";
import PricingCards from "@/components/landing/PricingCards";
import CTABanner from "@/components/landing/CTABanner";

export const metadata: Metadata = {
  title: "Pricing — A2A Treasury Network",
  description:
    "Simple, transparent pricing for autonomous B2B trade. Start free, scale as you grow with AI-powered negotiation and blockchain settlement.",
};

export default function PricingPage() {
  return (
    <>
      <LandingNavbar />
      <main>
        <PricingCards />
        <CTABanner />
      </main>
      <Footer />
    </>
  );
}
