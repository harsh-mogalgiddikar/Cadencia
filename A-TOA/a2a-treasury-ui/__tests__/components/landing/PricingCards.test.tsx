import React from "react";
import { render, screen } from "@testing-library/react";
import PricingCards from "@/components/landing/PricingCards";

describe("PricingCards", () => {
  it("renders all three pricing tiers", () => {
    render(<PricingCards />);
    expect(screen.getByText("Starter")).toBeInTheDocument();
    expect(screen.getByText("Growth")).toBeInTheDocument();
    expect(screen.getByText("Enterprise")).toBeInTheDocument();
  });

  it("shows Most Popular badge on Growth tier", () => {
    render(<PricingCards />);
    expect(screen.getByText("Most Popular")).toBeInTheDocument();
  });

  it("shows Free for Starter tier", () => {
    render(<PricingCards />);
    expect(screen.getByText("Free")).toBeInTheDocument();
  });

  it("shows correct Growth price", () => {
    render(<PricingCards />);
    expect(screen.getByText("₹4,999")).toBeInTheDocument();
  });

  it("shows Custom for Enterprise tier", () => {
    render(<PricingCards />);
    expect(screen.getByText("Custom")).toBeInTheDocument();
  });

  it("renders section header", () => {
    render(<PricingCards />);
    expect(screen.getByText(/Simple, Transparent/)).toBeInTheDocument();
  });

  it("renders CTA buttons for each tier", () => {
    render(<PricingCards />);
    expect(screen.getByText("Get Started")).toBeInTheDocument();
    expect(screen.getByText("Start Free Trial")).toBeInTheDocument();
    expect(screen.getByText("Contact Sales")).toBeInTheDocument();
  });

  it("renders feature lists", () => {
    render(<PricingCards />);
    expect(screen.getByText("10 negotiation sessions/month")).toBeInTheDocument();
    expect(screen.getByText("500 negotiation sessions/month")).toBeInTheDocument();
    expect(screen.getByText("Unlimited sessions")).toBeInTheDocument();
  });

  it("renders tier descriptions", () => {
    render(<PricingCards />);
    expect(screen.getByText(/hackathon demos/)).toBeInTheDocument();
    expect(screen.getByText(/SMEs scaling/)).toBeInTheDocument();
    expect(screen.getByText(/custom requirements/)).toBeInTheDocument();
  });
});
