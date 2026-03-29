"use client";

import { motion } from "framer-motion";
import { Terminal, ExternalLink } from "lucide-react";
import { fadeInUp, staggerContainer, viewportConfig } from "@/lib/animations";

const demoOutputLines = [
  { text: "$ a2a-cli negotiate --buyer Tata --seller Reliance --commodity steel-coils", color: "text-emerald-400" },
  { text: "", color: "" },
  { text: "📡 Discovering agents on registry...", color: "text-zinc-400" },
  { text: "✓ Found: Reliance Steel Agent (DANP-v1 compatible)", color: "text-zinc-300" },
  { text: "🤝 Handshake complete. Starting negotiation...", color: "text-zinc-400" },
  { text: "", color: "" },
  { text: "  Round 1 │ Buyer: ₹85,000  → Seller: ₹95,918", color: "text-zinc-300" },
  { text: "  Round 2 │ Buyer: ₹90,270  → Seller: ₹90,270 ✅", color: "text-emerald-400" },
  { text: "", color: "" },
  { text: "🔐 Deploying escrow contract... TX-7f3a2b1c", color: "text-cyan-400" },
  { text: "💳 x402 payment submitted... TX-9b2c4e8d  CONFIRMED", color: "text-cyan-400" },
  { text: "⛓  Merkle root: 0x8a3f...c291 → Algorand Block #41293872", color: "text-cyan-400" },
  { text: "", color: "" },
  { text: "✅ Trade settled successfully in 28.4s", color: "text-emerald-500" },
];

export default function LiveDemoSection() {
  return (
    <section className="relative py-24">
      <div className="pointer-events-none absolute inset-0 bg-gradient-to-b from-transparent via-zinc-950 to-transparent" />

      <div className="mx-auto max-w-7xl px-6">
        <motion.div
          variants={staggerContainer}
          initial="hidden"
          whileInView="visible"
          viewport={viewportConfig}
        >
          {/* Header */}
          <motion.div variants={fadeInUp} className="mb-12 text-center">
            <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-cyan-400/30 bg-cyan-400/10 px-4 py-1.5 text-sm font-medium text-cyan-400">
              <Terminal className="h-4 w-4" />
              Live Demo Preview
            </div>
            <h2 className="mb-4 text-3xl font-semibold text-zinc-50 md:text-4xl">
              See It in <span className="text-emerald-500">Action</span>
            </h2>
            <p className="mx-auto max-w-2xl text-base text-zinc-400">
              Watch a complete negotiation → settlement flow in under 30
              seconds.
            </p>
          </motion.div>

          {/* Terminal output */}
          <motion.div
            variants={fadeInUp}
            className="mx-auto max-w-4xl"
          >
            <div className="overflow-hidden rounded-xl border border-zinc-700 bg-zinc-900 shadow-2xl">
              {/* Terminal Header */}
              <div className="flex items-center justify-between border-b border-zinc-800 px-4 py-3">
                <div className="flex items-center gap-2">
                  <div className="h-3 w-3 rounded-full bg-red-500/80" />
                  <div className="h-3 w-3 rounded-full bg-yellow-500/80" />
                  <div className="h-3 w-3 rounded-full bg-green-500/80" />
                  <span className="ml-3 text-xs text-zinc-500">
                    a2a-treasury-cli
                  </span>
                </div>
                <button className="flex items-center gap-1.5 rounded-md border border-zinc-700 px-2.5 py-1 text-xs text-zinc-400 transition-colors hover:border-zinc-600 hover:text-zinc-300">
                  <ExternalLink className="h-3 w-3" />
                  Open in terminal
                </button>
              </div>

              {/* Terminal Body */}
              <div className="overflow-x-auto p-5 font-mono text-sm leading-relaxed">
                {demoOutputLines.map((line, i) => (
                  <div key={i} className={`${line.color} whitespace-pre`}>
                    {line.text || "\u00A0"}
                  </div>
                ))}
              </div>
            </div>
          </motion.div>
        </motion.div>
      </div>
    </section>
  );
}
