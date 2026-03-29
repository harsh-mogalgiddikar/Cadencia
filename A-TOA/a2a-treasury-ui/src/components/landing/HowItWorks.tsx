"use client";

import { motion } from "framer-motion";
import {
  UserPlus,
  Settings,
  Search,
  Handshake,
  Bot,
  Wallet,
  ShieldCheck,
} from "lucide-react";
import {
  fadeInUp,
  staggerContainer,
  viewportConfig,
} from "@/lib/animations";

const steps = [
  {
    number: 1,
    icon: UserPlus,
    title: "Register Enterprise",
    description:
      "Onboard with PAN, GST, wallet address. Get your Agent Card provisioned.",
  },
  {
    number: 2,
    icon: Settings,
    title: "Configure Policy",
    description:
      "Set budget ceilings, risk tolerance, concession curves, and compliance flags.",
  },
  {
    number: 3,
    icon: Search,
    title: "Agent Discovery",
    description:
      "Your agent queries the registry — finds sellers offering your commodity.",
  },
  {
    number: 4,
    icon: Handshake,
    title: "Capability Handshake",
    description:
      "Agents verify protocol compatibility (DANP-v1) before negotiating.",
  },
  {
    number: 5,
    icon: Bot,
    title: "Autonomous Negotiation",
    description:
      "DANP-v1 FSM runs. Buyer ₹85K → Seller ₹96K → Agreement in 2–3 rounds. Zero human input.",
  },
  {
    number: 6,
    icon: Wallet,
    title: "Escrow + x402 Payment",
    description:
      "Smart contract escrow deployed. Buyer agent signs PaymentTxn. Settled on-chain.",
  },
  {
    number: 7,
    icon: ShieldCheck,
    title: "Audit & Compliance",
    description:
      "SHA-256 chain verified. Merkle root anchored. FEMA record auto-generated.",
  },
];

export default function HowItWorks() {
  return (
    <section id="how-it-works" className="relative py-24">
      {/* Subtle background */}
      <div className="pointer-events-none absolute inset-0 bg-gradient-to-b from-transparent via-emerald-950/5 to-transparent" />

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
            From Requirement to Settlement in{" "}
            <span className="text-emerald-500">7 Steps</span>
          </motion.h2>
          <motion.p
            variants={fadeInUp}
            className="mx-auto max-w-2xl text-base text-zinc-400"
          >
            End-to-end autonomous trade flow — from enterprise registration to
            on-chain settlement and compliance generation.
          </motion.p>
        </motion.div>

        {/* Timeline */}
        <motion.div
          variants={staggerContainer}
          initial="hidden"
          whileInView="visible"
          viewport={viewportConfig}
          className="relative"
        >
          {/* Vertical line (desktop) */}
          <div className="absolute left-8 top-0 hidden h-full w-px border-l-2 border-dashed border-zinc-700 md:left-1/2 md:block" />

          {/* Steps */}
          <div className="space-y-8 md:space-y-12">
            {steps.map((step, index) => {
              const Icon = step.icon;
              const isLeft = index % 2 === 0;

              return (
                <motion.div
                  key={step.number}
                  variants={fadeInUp}
                  className="relative"
                >
                  {/* Mobile Layout */}
                  <div className="flex gap-4 md:hidden">
                    {/* Timeline dot + line */}
                    <div className="flex flex-col items-center">
                      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-emerald-500 text-sm font-bold text-black shadow-lg shadow-emerald-500/20">
                        {step.number}
                      </div>
                      {index < steps.length - 1 && (
                        <div className="mt-2 h-full w-px border-l-2 border-dashed border-zinc-700" />
                      )}
                    </div>
                    {/* Content */}
                    <div className="flex-1 pb-8">
                      <div className="rounded-xl border border-zinc-800 bg-zinc-900 p-5">
                        <div className="mb-3 flex items-center gap-3">
                          <div className="rounded-lg bg-emerald-500/10 p-2 text-emerald-500">
                            <Icon className="h-4 w-4" />
                          </div>
                          <h3 className="font-semibold text-zinc-50">
                            {step.title}
                          </h3>
                        </div>
                        <p className="text-sm leading-relaxed text-zinc-400">
                          {step.description}
                        </p>
                      </div>
                    </div>
                  </div>

                  {/* Desktop Layout */}
                  <div className="hidden md:grid md:grid-cols-2 md:gap-8">
                    {/* Left content */}
                    <div
                      className={`${
                        isLeft ? "pr-12 text-right" : "order-2 pl-12"
                      }`}
                    >
                      <div
                        className={`inline-block rounded-xl border border-zinc-800 bg-zinc-900 p-6 text-left transition-all duration-300 hover:border-emerald-500/20 hover:shadow-[0_0_20px_rgba(16,185,129,0.06)]`}
                      >
                        <div className="mb-3 flex items-center gap-3">
                          <div className="rounded-lg bg-emerald-500/10 p-2 text-emerald-500">
                            <Icon className="h-5 w-5" />
                          </div>
                          <h3 className="text-lg font-semibold text-zinc-50">
                            {step.title}
                          </h3>
                        </div>
                        <p className="text-sm leading-relaxed text-zinc-400">
                          {step.description}
                        </p>
                      </div>
                    </div>

                    {/* Center dot */}
                    <div
                      className={`absolute left-1/2 -translate-x-1/2 ${
                        isLeft ? "" : ""
                      }`}
                    >
                      <div className="flex h-10 w-10 items-center justify-center rounded-full bg-emerald-500 text-sm font-bold text-black shadow-lg shadow-emerald-500/20">
                        {step.number}
                      </div>
                    </div>

                    {/* Right spacer */}
                    <div className={`${isLeft ? "order-2" : ""}`} />
                  </div>
                </motion.div>
              );
            })}
          </div>
        </motion.div>
      </div>
    </section>
  );
}
