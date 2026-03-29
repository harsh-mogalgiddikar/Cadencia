"use client";

import { motion } from "framer-motion";
import { ArrowRight } from "lucide-react";
import Link from "next/link";
import { fadeInUp, staggerContainer, viewportConfig } from "@/lib/animations";

export default function PricingTeaser() {
  return (
    <section className="relative py-24">
      <div className="mx-auto max-w-7xl px-6">
        <motion.div
          variants={staggerContainer}
          initial="hidden"
          whileInView="visible"
          viewport={viewportConfig}
          className="rounded-2xl border border-zinc-800 bg-zinc-900/50 p-8 md:p-12"
        >
          <div className="grid items-center gap-8 md:grid-cols-2">
            <motion.div variants={fadeInUp}>
              <h2 className="mb-3 text-2xl font-semibold text-zinc-50 md:text-3xl">
                Pricing that{" "}
                <span className="text-emerald-500">scales with you</span>
              </h2>
              <p className="text-base text-zinc-400">
                From free hackathon demos to enterprise-grade deployments.
                Start trading autonomously today.
              </p>
            </motion.div>

            <motion.div
              variants={fadeInUp}
              className="flex flex-wrap items-center gap-4 md:justify-end"
            >
              <div className="flex items-center gap-2 rounded-full border border-zinc-700 bg-zinc-900 px-5 py-2.5">
                <span className="text-sm font-semibold text-zinc-50">
                  Free
                </span>
                <span className="text-xs text-zinc-400">
                  to get started
                </span>
              </div>
              <Link
                href="/pricing"
                className="group flex items-center gap-2 rounded-full bg-emerald-500 px-6 py-2.5 text-sm font-semibold text-black transition-all hover:bg-emerald-400"
              >
                View Pricing
                <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" />
              </Link>
            </motion.div>
          </div>
        </motion.div>
      </div>
    </section>
  );
}
