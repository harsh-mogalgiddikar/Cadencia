import React from "react";
import { render, screen } from "@testing-library/react";
import LandingNavbar from "@/components/layout/Navbar";

describe("LandingNavbar", () => {
  it("renders logo text", () => {
    render(<LandingNavbar />);
    expect(screen.getByText("A2A Treasury")).toBeInTheDocument();
  });

  it("renders all nav links", () => {
    render(<LandingNavbar />);
    expect(screen.getByText("Features")).toBeInTheDocument();
    expect(screen.getByText("How It Works")).toBeInTheDocument();
    expect(screen.getByText("Pricing")).toBeInTheDocument();
    expect(screen.getByText("Docs")).toBeInTheDocument();
  });

  it("renders Sign In and Get Started buttons", () => {
    render(<LandingNavbar />);
    // Both desktop and mobile versions exist — use getAllByText
    const signIns = screen.getAllByText("Sign In");
    const getStarteds = screen.getAllByText("Get Started");
    expect(signIns.length).toBeGreaterThanOrEqual(1);
    expect(getStarteds.length).toBeGreaterThanOrEqual(1);
  });

  it("Sign In links to /auth/login", () => {
    render(<LandingNavbar />);
    const signIn = screen.getAllByText("Sign In")[0].closest("a");
    expect(signIn).toHaveAttribute("href", "/auth/login");
  });

  it("Get Started links to /auth/register", () => {
    render(<LandingNavbar />);
    const getStarted = screen.getAllByText("Get Started")[0].closest("a");
    expect(getStarted).toHaveAttribute("href", "/auth/register");
  });

  it("has mobile menu toggle button", () => {
    render(<LandingNavbar />);
    const toggleBtn = screen.getByLabelText("Toggle menu");
    expect(toggleBtn).toBeInTheDocument();
  });

  it("logo links to /", () => {
    render(<LandingNavbar />);
    const logoLink = screen.getByText("A2A Treasury").closest("a");
    expect(logoLink).toHaveAttribute("href", "/");
  });
});
