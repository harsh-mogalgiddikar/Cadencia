import React from "react";
import { render, screen } from "@testing-library/react";
import FeaturesGrid from "@/components/landing/FeaturesGrid";

describe("FeaturesGrid", () => {
  it("renders all 6 feature cards", () => {
    render(<FeaturesGrid />);
    expect(screen.getByText("AI Agent Negotiation")).toBeInTheDocument();
    expect(screen.getByText("Guardrail Enforcement")).toBeInTheDocument();
    expect(screen.getByText("Algorand Smart Contract Escrow")).toBeInTheDocument();
    expect(screen.getByText("x402 Payment Protocol")).toBeInTheDocument();
    expect(screen.getByText("FEMA/RBI Compliance")).toBeInTheDocument();
    expect(screen.getByText("Cryptographic Audit Trail")).toBeInTheDocument();
  });

  it("renders section header", () => {
    render(<FeaturesGrid />);
    expect(screen.getByText(/Everything You Need/)).toBeInTheDocument();
  });

  it("renders sub-header text", () => {
    render(<FeaturesGrid />);
    expect(screen.getByText(/AI negotiation, blockchain settlement/)).toBeInTheDocument();
  });

  it("renders feature descriptions", () => {
    render(<FeaturesGrid />);
    expect(screen.getByText(/DANP-v1 protocol/)).toBeInTheDocument();
    expect(screen.getByText(/Trustless 2-of-3 multisig/)).toBeInTheDocument();
    expect(screen.getByText(/SHA-256 hash chain/)).toBeInTheDocument();
  });

  it("renders Autonomous Trade span in header", () => {
    render(<FeaturesGrid />);
    expect(screen.getByText("Autonomous Trade")).toBeInTheDocument();
  });
});
