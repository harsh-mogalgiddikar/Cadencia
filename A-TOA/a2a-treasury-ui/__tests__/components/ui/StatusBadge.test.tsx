import React from "react";
import { render, screen } from "@testing-library/react";
import StatusBadge from "@/components/ui/StatusBadge";

describe("StatusBadge (ui)", () => {
  describe("Negotiation statuses", () => {
    const negotiationCases = [
      { status: "AGREED", label: "✅ Agreed" },
      { status: "WALKAWAY", label: "❌ Walkaway" },
      { status: "ROUND_LOOP", label: "Negotiating" },
      { status: "TIMEOUT", label: "⏰ Timeout" },
      { status: "POLICY_BREACH", label: "🚨 Policy Breach" },
      { status: "INIT", label: "Initializing" },
      { status: "BUYER_ANCHOR", label: "Buyer Anchored" },
      { status: "SELLER_RESPONSE", label: "Seller Responding" },
      { status: "STALLED", label: "Stalled" },
      { status: "ROUND_LIMIT", label: "Round Limit" },
    ];

    negotiationCases.forEach(({ status, label }) => {
      it(`renders correct label for ${status}`, () => {
        render(<StatusBadge status={status} />);
        expect(screen.getByText(label)).toBeInTheDocument();
      });
    });
  });

  describe("Escrow statuses", () => {
    const escrowCases = [
      { status: "PENDING", label: "Pending" },
      { status: "DEPLOYED", label: "Deployed" },
      { status: "FUNDED", label: "Funded" },
      { status: "RELEASED", label: "Released" },
      { status: "REFUNDED", label: "Refunded" },
    ];

    escrowCases.forEach(({ status, label }) => {
      it(`renders correct label for escrow ${status}`, () => {
        render(<StatusBadge status={status} kind="escrow" />);
        expect(screen.getByText(label)).toBeInTheDocument();
      });
    });
  });

  describe("Compliance statuses", () => {
    const complianceCases = [
      { status: "APPROVED", label: "Approved" },
      { status: "COMPLIANT", label: "Compliant" },
      { status: "BLOCKED", label: "Blocked" },
      { status: "WARNING", label: "Warning" },
    ];

    complianceCases.forEach(({ status, label }) => {
      it(`renders correct label for compliance ${status}`, () => {
        render(<StatusBadge status={status} kind="compliance" />);
        expect(screen.getByText(label)).toBeInTheDocument();
      });
    });
  });

  it("applies emerald color classes for AGREED status", () => {
    const { container } = render(<StatusBadge status="AGREED" />);
    const badge = container.firstChild as HTMLElement;
    expect(badge.className).toContain("border-emerald-500/30");
    expect(badge.className).toContain("text-emerald-400");
  });

  it("applies red color classes for WALKAWAY status", () => {
    const { container } = render(<StatusBadge status="WALKAWAY" />);
    const badge = container.firstChild as HTMLElement;
    expect(badge.className).toContain("border-red-500/30");
    expect(badge.className).toContain("text-red-400");
  });

  it("applies amber color classes for ROUND_LOOP status", () => {
    const { container } = render(<StatusBadge status="ROUND_LOOP" />);
    const badge = container.firstChild as HTMLElement;
    expect(badge.className).toContain("border-amber-500/30");
  });

  it("shows pulse animation for ROUND_LOOP", () => {
    const { container } = render(<StatusBadge status="ROUND_LOOP" />);
    // The pulse dot has animate-ping class
    expect(container.querySelector(".animate-ping")).toBeInTheDocument();
  });

  it("does not show pulse for AGREED by default", () => {
    const { container } = render(<StatusBadge status="AGREED" />);
    expect(container.querySelector(".animate-ping")).not.toBeInTheDocument();
  });

  it("shows pulse when forced via prop", () => {
    const { container } = render(<StatusBadge status="AGREED" pulse />);
    expect(container.querySelector(".animate-ping")).toBeInTheDocument();
  });

  it("falls back to raw status string for unknown status", () => {
    render(<StatusBadge status="CUSTOM_STATUS" />);
    expect(screen.getByText("CUSTOM_STATUS")).toBeInTheDocument();
  });
});
