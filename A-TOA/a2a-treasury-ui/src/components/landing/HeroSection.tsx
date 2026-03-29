"use client";

import { motion, AnimatePresence } from "framer-motion";
import { ArrowRight, Play } from "lucide-react";
import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import {
  fadeInUp,
  staggerContainer,
  slideInRight,
  viewportConfig,
} from "@/lib/animations";

const terminalLines = [
  { prefix: "🤖", text: "Buyer Agent          ", status: "● NEGOTIATING", statusColor: "text-emerald-400", delay: 0 },
  { prefix: "→", text: "Buyer:   ₹85,000  ", tag: "ANCHOR", tagColor: "text-zinc-400", delay: 800 },
  { prefix: "←", text: "Seller:  ₹95,918  ", tag: "COUNTER", tagColor: "text-zinc-400", delay: 1600 },
  { prefix: "→", text: "Buyer:   ₹90,270  ", tag: "COUNTER", tagColor: "text-zinc-400", delay: 2400 },
  { prefix: "←", text: "Seller:  ✅ ACCEPTED  ₹90,270", tag: null, tagColor: "", delay: 3200 },
  { prefix: "🔐", text: "Escrow deployed: ALGO-ESC-7f3a...", tag: null, tagColor: "", delay: 4200, isCyan: true },
  { prefix: "💳", text: "x402 Payment: TX-9b2c...  ✓ CONFIRMED", tag: null, tagColor: "", delay: 5200, isCyan: true },
  { prefix: "⛓", text: " Merkle root anchored on-chain", tag: null, tagColor: "", delay: 6200, isCyan: true },
];

const microStats = [
  { value: "2–3 Rounds", label: "Avg. negotiation" },
  { value: "< 30s", label: "Full settlement" },
  { value: "100%", label: "Audit verifiable" },
];

function NegotiationTerminal() {
  const [visibleLines, setVisibleLines] = useState(0);
  const [cycle, setCycle] = useState(0);

  const resetAnimation = useCallback(() => {
    setVisibleLines(0);
    setCycle((c) => c + 1);
  }, []);

  useEffect(() => {
    const timers: NodeJS.Timeout[] = [];

    terminalLines.forEach((line, index) => {
      const timer = setTimeout(() => {
        setVisibleLines(index + 1);
      }, line.delay);
      timers.push(timer);
    });

    // Reset animation after all lines + pause
    const resetTimer = setTimeout(resetAnimation, 10200);
    timers.push(resetTimer);

    return () => timers.forEach(clearTimeout);
  }, [cycle, resetAnimation]);

  return (
    <div className="relative w-full max-w-lg">
      {/* Glow behind terminal */}
      <div className="absolute -inset-4 rounded-2xl bg-emerald-500/5 blur-2xl" />

      <div className="relative overflow-hidden rounded-xl border border-zinc-700 bg-zinc-900 font-mono text-sm shadow-2xl">
        {/* Terminal Header */}
        <div className="flex items-center gap-2 border-b border-zinc-800 px-4 py-3">
          <div className="h-3 w-3 rounded-full bg-red-500/80" />
          <div className="h-3 w-3 rounded-full bg-yellow-500/80" />
          <div className="h-3 w-3 rounded-full bg-green-500/80" />
          <span className="ml-3 text-xs text-zinc-500">
            a2a-negotiation-session
          </span>
        </div>

        {/* Terminal Body */}
        <div className="min-h-[280px] p-4 md:min-h-[320px]">
          <AnimatePresence mode="wait">
            <motion.div key={cycle} className="space-y-2">
              {terminalLines.slice(0, visibleLines).map((line, i) => (
                <motion.div
                  key={`${cycle}-${i}`}
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ duration: 0.3 }}
                  className={`flex items-start gap-2 ${
                    line.isCyan ? "text-cyan-400" : "text-zinc-300"
                  }`}
                >
                  <span className="shrink-0">{line.prefix}</span>
                  <span className="flex-1">
                    {i === 0 ? (
                      <span className="flex items-center gap-3">
                        <span className="text-zinc-300">{line.text}</span>
                        <span className="flex items-center gap-1.5">
                          <span className="inline-block h-2 w-2 rounded-full bg-emerald-400 live-dot" />
                          <span className="text-emerald-400 text-xs font-semibold">
                            NEGOTIATING
                          </span>
                        </span>
                      </span>
                    ) : (
                      <span>
                        {line.text}
                        {line.tag && (
                          <span className="ml-2 rounded border border-zinc-700 px-1.5 py-0.5 text-xs text-zinc-500">
                            {line.tag}
                          </span>
                        )}
                      </span>
                    )}
                  </span>
                </motion.div>
              ))}
              {visibleLines > 0 && visibleLines < terminalLines.length && (
                <motion.span
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="terminal-cursor inline-block text-emerald-400"
                />
              )}
            </motion.div>
          </AnimatePresence>
        </div>
      </div>
    </div>
  );
}

export default function HeroSection() {
  return (
    <section className="relative overflow-hidden">
      {/* Background gradient orbs */}
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute -left-40 -top-40 h-80 w-80 rounded-full bg-emerald-500/8 blur-[120px]" />
        <div className="absolute -bottom-40 right-0 h-96 w-96 rounded-full bg-cyan-500/5 blur-[120px]" />
      </div>

      <div className="mx-auto max-w-7xl px-6 pb-20 pt-16 md:pb-32 md:pt-24">
        <motion.div
          variants={staggerContainer}
          initial="hidden"
          animate="visible"
          className="grid items-center gap-12 lg:grid-cols-2 lg:gap-16"
        >
          {/* Left Column: Text Content */}
          <div className="relative z-10">
            {/* Badge */}
            <motion.div variants={fadeInUp} className="mb-6">
              <span className="inline-flex items-center gap-2 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-4 py-1.5 text-sm font-medium text-emerald-400">
                🔗 Built on Algorand TestNet
              </span>
            </motion.div>

            {/* Headline */}
            <motion.h1
              variants={fadeInUp}
              className="mb-6 text-3xl font-bold tracking-tight text-zinc-50 md:text-5xl lg:text-5xl"
            >
              Autonomous B2B Trade.
              <br />
              <span className="text-emerald-500">
                Zero Human Intervention.
              </span>
            </motion.h1>

            {/* Subheadline */}
            <motion.p
              variants={fadeInUp}
              className="mb-8 max-w-lg text-base leading-relaxed text-zinc-400 md:text-lg"
            >
              AI agents discover, negotiate, and settle cross-border trade deals
              on Algorand — from first offer to on-chain payment, fully
              autonomous.
            </motion.p>

            {/* CTA Buttons */}
            <motion.div
              variants={fadeInUp}
              className="mb-10 flex flex-wrap items-center gap-4"
            >
              <Link
                href="#"
                className="group flex items-center gap-2 rounded-xl bg-emerald-500 px-7 py-3.5 text-base font-bold text-black transition-all hover:scale-105 hover:bg-emerald-400 hover:shadow-lg hover:shadow-emerald-500/25"
              >
                Start Trading
                <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" />
              </Link>
              <Link
                href="/demo"
                className="flex items-center gap-2 rounded-xl border border-zinc-700 bg-transparent px-7 py-3.5 text-base font-medium text-zinc-300 transition-all hover:border-zinc-600 hover:text-white"
              >
                <Play className="h-4 w-4" />
                Watch Live Demo
              </Link>
            </motion.div>

            {/* Micro Stats */}
            <motion.div
              variants={fadeInUp}
              className="flex flex-wrap gap-3"
            >
              {microStats.map((stat) => (
                <div
                  key={stat.label}
                  className="flex items-center gap-3 rounded-lg border border-zinc-800 bg-zinc-900/50 px-4 py-3"
                >
                  <div className="h-8 w-0.5 rounded-full bg-emerald-500" />
                  <div>
                    <p className="text-sm font-bold text-zinc-50">
                      {stat.value}
                    </p>
                    <p className="text-xs text-zinc-500">{stat.label}</p>
                  </div>
                </div>
              ))}
            </motion.div>
          </div>

          {/* Right Column: Animated Terminal */}
          <motion.div
            variants={slideInRight}
            className="relative flex items-center justify-center lg:justify-end"
          >
            <NegotiationTerminal />
          </motion.div>
        </motion.div>
      </div>
    </section>
  );
}
