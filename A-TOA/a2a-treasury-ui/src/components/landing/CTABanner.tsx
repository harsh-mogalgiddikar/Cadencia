"use client";

import { motion } from "framer-motion";
import { ArrowRight, BookOpen } from "lucide-react";
import Link from "next/link";
import { fadeInUp, staggerContainer, viewportConfig } from "@/lib/animations";

export default function CTABanner() {
  return (
    <section className="relative overflow-hidden py-24">
      {/* Gradient background */}
      <div className="pointer-events-none absolute inset-0 bg-gradient-to-r from-emerald-950/40 via-zinc-900 to-cyan-950/40" />
      <div className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-zinc-700 to-transparent" />
      <div className="pointer-events-none absolute inset-x-0 bottom-0 h-px bg-gradient-to-r from-transparent via-zinc-700 to-transparent" />

      <div className="relative mx-auto max-w-4xl px-6 text-center">
        <motion.div
          variants={staggerContainer}
          initial="hidden"
          whileInView="visible"
          viewport={viewportConfig}
        >
          <motion.h2
            variants={fadeInUp}
            className="mb-4 text-3xl font-bold text-zinc-50 md:text-4xl"
          >
            Ready to Automate Your{" "}
            <span className="text-emerald-500">B2B Trade</span>?
          </motion.h2>

          <motion.p
            variants={fadeInUp}
            className="mb-10 text-base text-zinc-400 md:text-lg"
          >
            Join Indian enterprises already settling deals trustlessly on
            Algorand.
          </motion.p>

          <motion.div
            variants={fadeInUp}
            className="flex flex-wrap items-center justify-center gap-4"
          >
            <Link
              href="#"
              className="group flex items-center gap-2 rounded-xl bg-emerald-500 px-8 py-4 text-base font-bold text-black transition-all hover:scale-105 hover:bg-emerald-400 hover:shadow-lg hover:shadow-emerald-500/25"
            >
              Register Your Enterprise
              <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" />
            </Link>
            <Link
              href="#"
              className="flex items-center gap-2 rounded-xl border border-zinc-700 bg-transparent px-8 py-4 text-base font-medium text-zinc-300 transition-all hover:border-zinc-600 hover:text-white"
            >
              <BookOpen className="h-4 w-4" />
              Read the Docs
            </Link>
          </motion.div>
        </motion.div>
      </div>
    </section>
  );
}
