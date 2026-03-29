import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import CopyButton from "@/components/ui/CopyButton";

// Mock clipboard API
Object.assign(navigator, {
  clipboard: { writeText: jest.fn().mockResolvedValue(undefined) },
});

describe("CopyButton", () => {
  const fullValue = "a3f9b2c4d5e6f7a8b9c0d1e2f3a4b5c6";

  it("renders full text when no truncation specified", () => {
    render(<CopyButton text={fullValue} />);
    expect(screen.getByText(fullValue)).toBeInTheDocument();
  });

  it("renders truncated value with ellipsis when truncate prop is set", () => {
    render(<CopyButton text={fullValue} truncate={8} />);
    // truncate=8 means first 4 + "..." + last 4
    const display = `${fullValue.slice(0, 4)}...${fullValue.slice(-4)}`;
    expect(screen.getByText(display)).toBeInTheDocument();
  });

  it("copies full text to clipboard on click", async () => {
    render(<CopyButton text={fullValue} />);
    fireEvent.click(screen.getByRole("button"));
    expect(navigator.clipboard.writeText).toHaveBeenCalledWith(fullValue);
  });

  it("shows Check icon after copy", async () => {
    render(<CopyButton text={fullValue} />);
    fireEvent.click(screen.getByRole("button"));
    // After click, the Check icon should appear (lucide Check component renders an SVG)
    await waitFor(() => {
      // The copy icon is replaced by a check icon - we can check the svg class
      const svg = screen.getByRole("button").querySelector(".text-emerald-500");
      expect(svg).toBeInTheDocument();
    });
  });

  it("renders with mono font by default", () => {
    render(<CopyButton text="test-value" />);
    const textSpan = screen.getByText("test-value");
    expect(textSpan.className).toContain("font-mono");
  });

  it("disables mono font when mono=false", () => {
    render(<CopyButton text="test-value" mono={false} />);
    const textSpan = screen.getByText("test-value");
    expect(textSpan.className).not.toContain("font-mono");
  });

  it("shows full text as title attribute for tooltip", () => {
    render(<CopyButton text={fullValue} truncate={8} />);
    expect(screen.getByRole("button")).toHaveAttribute("title", fullValue);
  });
});
