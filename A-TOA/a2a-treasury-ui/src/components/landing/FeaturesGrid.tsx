"use client";

import { motion } from "framer-motion";
import {
  Bot,
  Shield,
  Link as LinkIcon,
  Zap,
  FileCheck,
  Lock,
} from "lucide-react";
import {
  fadeInUp,
  staggerContainer,
  viewportConfig,
} from "@/lib/animations";

const features = [
  {
    icon: Bot,
    title: "AI Agent Negotiation",
    description:
      "DANP-v1 protocol — 4-layer FSM with LLM advisory. Deals close in 2–3 rounds autonomously.",
    color: "emerald" as const,
  },
  {
    icon: Shield,
    title: "Guardrail Enforcement",
    description:
      "Budget ceilings, reservation prices, and policy breach detection. Agents never overpay.",
    color: "emerald" as const,
  },
  {
    icon: LinkIcon,
    title: "Algorand Smart Contract Escrow",
    description:
      "Trustless 2-of-3 multisig escrow auto-deployed on agreement. Funds held on-chain.",
    color: "cyan" as const,
  },
  {
    icon: Zap,
    title: "x402 Payment Protocol",
    description:
      "HTTP-native autonomous payments. Buyer agent signs and submits Algorand txns without human input.",
    color: "cyan" as const,
  },
  {
    icon: FileCheck,
    title: "FEMA/RBI Compliance",
    description:
      "Auto-generated compliance records for every cross-border transaction. Purpose codes included.",
    color: "emerald" as const,
  },
  {
    icon: Lock,
    title: "Cryptographic Audit Trail",
    description:
      "SHA-256 hash chain + Merkle root anchored on Algorand. Every offer provable forever.",
    color: "cyan" as const,
  },
];

export default function FeaturesGrid() {
  return (
    <section id="features" className="relative py-24">
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
            Everything You Need for{" "}
            <span className="text-emerald-500">Autonomous Trade</span>
          </motion.h2>
          <motion.p
            variants={fadeInUp}
            className="mx-auto max-w-2xl text-base text-zinc-400"
          >
            One platform. AI negotiation, blockchain settlement, regulatory
            compliance.
          </motion.p>
        </motion.div>

        {/* Grid */}
        <motion.div
          variants={staggerContainer}
          initial="hidden"
          whileInView="visible"
          viewport={viewportConfig}
          className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3"
        >
          {features.map((feature) => {
            const Icon = feature.icon;
            const isEmerald = feature.color === "emerald";
            return (
              <motion.div
                key={feature.title}
                variants={fadeInUp}
                className={`group relative rounded-xl border border-zinc-800 bg-zinc-900 p-6 transition-all duration-300 hover:border-${feature.color === "emerald" ? "emerald" : "cyan"}-500/30 hover:shadow-[0_0_20px_rgba(${isEmerald ? "16,185,129" : "34,211,238"},0.08)]`}
              >
                {/* Icon */}
                <div
                  className={`mb-4 inline-flex rounded-lg p-2.5 ${
                    isEmerald
                      ? "bg-emerald-500/10 text-emerald-500"
                      : "bg-cyan-400/10 text-cyan-400"
                  }`}
                >
                  <Icon className="h-5 w-5" />
                </div>

                {/* Text */}
                <h3 className="mb-2 text-lg font-semibold text-zinc-50">
                  {feature.title}
                </h3>
                <p className="text-sm leading-relaxed text-zinc-400">
                  {feature.description}
                </p>

                {/* Hover glow */}
                <div
                  className={`pointer-events-none absolute inset-0 rounded-xl opacity-0 transition-opacity duration-300 group-hover:opacity-100 ${
                    isEmerald
                      ? "bg-gradient-to-br from-emerald-500/5 to-transparent"
                      : "bg-gradient-to-br from-cyan-400/5 to-transparent"
                  }`}
                />
              </motion.div>
            );
          })}
        </motion.div>
      </div>
    </section>
  );
}
