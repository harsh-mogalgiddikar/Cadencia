"use client";

import { motion } from "framer-motion";
import { Check, ArrowRight } from "lucide-react";
import Link from "next/link";
import { fadeInUp, staggerContainer, viewportConfig } from "@/lib/animations";

const tiers = [
  {
    name: "Starter",
    price: "Free",
    period: "",
    description: "Perfect for hackathon demos and development testing.",
    cta: "Get Started",
    ctaVariant: "secondary" as const,
    highlighted: false,
    features: [
      "10 negotiation sessions/month",
      "TestNet only",
      "Basic audit trail",
      "Community support",
      "Single agent config",
    ],
  },
  {
    name: "Growth",
    price: "₹4,999",
    period: "/mo",
    description: "For SMEs scaling their autonomous trade operations.",
    cta: "Start Free Trial",
    ctaVariant: "primary" as const,
    highlighted: true,
    badge: "Most Popular",
    features: [
      "500 negotiation sessions/month",
      "MainNet deployment",
      "FEMA/RBI compliance records",
      "Priority support",
      "Advanced policy configuration",
      "Multi-commodity support",
      "Analytics dashboard",
    ],
  },
  {
    name: "Enterprise",
    price: "Custom",
    period: "",
    description: "For large enterprises with custom requirements.",
    cta: "Contact Sales",
    ctaVariant: "secondary" as const,
    highlighted: false,
    features: [
      "Unlimited sessions",
      "Multi-party auction support",
      "Custom SLA agreement",
      "Dedicated agent configuration",
      "On-premise deployment option",
      "24/7 dedicated support",
      "Custom integrations",
      "Regulatory consulting",
    ],
  },
];

export default function PricingCards() {
  return (
    <section id="pricing" className="relative py-24">
      <div className="mx-auto max-w-7xl px-6">
        {/* Section Header */}
        <motion.div
          variants={staggerContainer}
          initial="hidden"
          whileInView="visible"
          viewport={viewportConfig}
          className="mb-16 text-center"
        >
          <motion.h2
            variants={fadeInUp}
            className="mb-4 text-3xl font-semibold text-zinc-50 md:text-4xl"
          >
            Simple, Transparent{" "}
            <span className="text-emerald-500">Pricing</span>
          </motion.h2>
          <motion.p
            variants={fadeInUp}
            className="mx-auto max-w-2xl text-base text-zinc-400"
          >
            Start free, scale as you grow. All plans include AI-powered
            negotiation and blockchain settlement.
          </motion.p>
        </motion.div>

        {/* Cards */}
        <motion.div
          variants={staggerContainer}
          initial="hidden"
          whileInView="visible"
          viewport={viewportConfig}
          className="grid gap-6 md:grid-cols-3"
        >
          {tiers.map((tier) => (
            <motion.div
              key={tier.name}
              variants={fadeInUp}
              className={`relative flex flex-col rounded-xl border p-8 transition-all duration-300 ${
                tier.highlighted
                  ? "border-emerald-500 bg-zinc-900 shadow-[0_0_30px_rgba(16,185,129,0.2)]"
                  : "border-zinc-800 bg-zinc-900 hover:border-zinc-700"
              }`}
            >
              {/* Badge */}
              {tier.badge && (
                <div className="absolute -top-3 left-1/2 -translate-x-1/2">
                  <span className="rounded-full bg-emerald-500 px-4 py-1 text-xs font-bold text-black">
                    {tier.badge}
                  </span>
                </div>
              )}

              {/* Tier Info */}
              <div className="mb-6">
                <h3 className="mb-1 text-lg font-semibold text-zinc-50">
                  {tier.name}
                </h3>
                <p className="text-sm text-zinc-400">{tier.description}</p>
              </div>

              {/* Price */}
              <div className="mb-6">
                <span className="text-4xl font-bold text-zinc-50">
                  {tier.price}
                </span>
                {tier.period && (
                  <span className="text-sm text-zinc-400">{tier.period}</span>
                )}
              </div>

              {/* CTA */}
              <Link
                href="#"
                className={`group mb-8 flex items-center justify-center gap-2 rounded-lg px-6 py-3 text-sm font-semibold transition-all ${
                  tier.ctaVariant === "primary"
                    ? "bg-emerald-500 text-black hover:bg-emerald-400 hover:shadow-lg hover:shadow-emerald-500/25"
                    : "border border-zinc-700 text-zinc-300 hover:border-zinc-600 hover:text-white"
                }`}
              >
                {tier.cta}
                <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" />
              </Link>

              {/* Features */}
              <ul className="flex-1 space-y-3">
                {tier.features.map((feature) => (
                  <li
                    key={feature}
                    className="flex items-start gap-3 text-sm text-zinc-400"
                  >
                    <Check className="mt-0.5 h-4 w-4 shrink-0 text-emerald-500" />
                    {feature}
                  </li>
                ))}
              </ul>
            </motion.div>
          ))}
        </motion.div>
      </div>
    </section>
  );
}
