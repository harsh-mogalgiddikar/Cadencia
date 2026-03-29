"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ArrowRight, Menu, X, Zap } from "lucide-react";

const navLinks = [
  { href: "/#features", label: "Features" },
  { href: "/#how-it-works", label: "How It Works" },
  { href: "/pricing", label: "Pricing" },
  { href: "#", label: "Docs" },
];

export default function LandingNavbar() {
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <nav className="sticky top-0 z-50 border-b border-zinc-800 bg-zinc-950/80 backdrop-blur-md">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-6">
        {/* Left: Logo */}
        <Link
          href="/"
          className="flex items-center gap-2.5 text-lg font-bold tracking-tight text-white transition-colors hover:text-emerald-400"
        >
          <div className="flex h-8 w-8 items-center justify-center rounded-md bg-emerald-500">
            <span className="text-sm font-black text-black">A2</span>
          </div>
          <span>A2A Treasury</span>
        </Link>

        {/* Center: Desktop Links */}
        <div className="hidden items-center gap-1 md:flex">
          {navLinks.map(({ href, label }) => {
            const isActive =
              pathname === href ||
              (href.startsWith("/#") && pathname === "/");
            return (
              <Link
                key={label}
                href={href}
                className={`rounded-lg px-4 py-2 text-sm font-medium transition-colors ${
                  isActive && href === "/pricing"
                    ? "text-emerald-500"
                    : "text-zinc-400 hover:text-zinc-50"
                }`}
              >
                {label}
              </Link>
            );
          })}
        </div>

        {/* Right: CTA Buttons */}
        <div className="hidden items-center gap-3 md:flex">
          <Link
            href="/demo"
            className="inline-flex items-center gap-1.5 rounded-lg
              bg-blue-500/10 border border-blue-500/30 px-4 py-1.5
              text-sm font-medium text-blue-300
              hover:bg-blue-500/20 hover:text-blue-200
              transition-colors duration-150"
          >
            <Zap className="h-3.5 w-3.5" />
            Live Demo
          </Link>
          <Link
            href="/auth/login"
            className="rounded-lg px-4 py-2 text-sm font-medium text-zinc-300 transition-colors hover:text-white"
          >
            Sign In
          </Link>
          <Link
            href="/auth/register"
            className="flex items-center gap-2 rounded-lg bg-emerald-500 px-5 py-2.5 text-sm font-semibold text-black transition-all hover:bg-emerald-600 hover:shadow-lg hover:shadow-emerald-500/20"
          >
            Get Started
            <ArrowRight className="h-4 w-4" />
          </Link>
        </div>

        {/* Mobile Menu Button */}
        <button
          onClick={() => setMobileOpen(!mobileOpen)}
          className="rounded-lg p-2 text-zinc-400 transition-colors hover:text-white md:hidden"
          aria-label="Toggle menu"
        >
          {mobileOpen ? (
            <X className="h-5 w-5" />
          ) : (
            <Menu className="h-5 w-5" />
          )}
        </button>
      </div>

      {/* Mobile Menu */}
      <AnimatePresence>
        {mobileOpen && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.2, ease: "easeInOut" }}
            className="overflow-hidden border-t border-zinc-800 bg-zinc-950 md:hidden"
          >
            <div className="flex flex-col gap-1 px-6 py-4">
              {navLinks.map(({ href, label }) => (
                <Link
                  key={label}
                  href={href}
                  onClick={() => setMobileOpen(false)}
                  className="rounded-lg px-4 py-3 text-sm font-medium text-zinc-400 transition-colors hover:bg-zinc-900 hover:text-zinc-50"
                >
                  {label}
                </Link>
              ))}
              <div className="mt-3 flex flex-col gap-2 border-t border-zinc-800 pt-4">
                <Link
                  href="/demo"
                  onClick={() => setMobileOpen(false)}
                  className="flex items-center gap-2 rounded-lg px-4 py-3 text-sm font-medium text-blue-300 transition-colors hover:bg-blue-500/10"
                >
                  <Zap className="h-3.5 w-3.5" />
                  Live Demo
                </Link>
                <Link
                  href="/auth/login"
                  className="rounded-lg px-4 py-3 text-sm font-medium text-zinc-300 transition-colors hover:text-white"
                >
                  Sign In
                </Link>
                <Link
                  href="/auth/register"
                  className="flex items-center justify-center gap-2 rounded-lg bg-emerald-500 px-5 py-3 text-sm font-semibold text-black transition-all hover:bg-emerald-600"
                >
                  Get Started
                  <ArrowRight className="h-4 w-4" />
                </Link>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </nav>
  );
}
