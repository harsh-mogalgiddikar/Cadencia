"use client";

import { motion, useInView } from "framer-motion";
import { useRef, useEffect, useState } from "react";
import { fadeInUp, staggerContainer, viewportConfig } from "@/lib/animations";

const stats = [
  { value: "2–3", label: "Negotiation Rounds Average", isText: true },
  { value: "< 30s", label: "Full Settlement Time", isText: true },
  { value: "19+", label: "Audit Entries Per Session", isText: true },
  { value: "100%", label: "On-Chain Verifiable", isText: true },
];

function AnimatedStat({
  value,
  label,
}: {
  value: string;
  label: string;
  isText: boolean;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const isInView = useInView(ref, { once: true, margin: "-50px" });
  const [isVisible, setIsVisible] = useState(false);

  useEffect(() => {
    if (isInView) {
      const timer = setTimeout(() => setIsVisible(true), 200);
      return () => clearTimeout(timer);
    }
  }, [isInView]);

  return (
    <div ref={ref} className="text-center">
      <motion.div
        initial={{ scale: 0.5, opacity: 0 }}
        animate={isVisible ? { scale: 1, opacity: 1 } : {}}
        transition={{ duration: 0.5, ease: "easeOut" }}
      >
        <span className="text-4xl font-bold text-emerald-500 md:text-5xl">
          {isVisible ? value : "—"}
        </span>
      </motion.div>
      <p className="mt-2 text-sm text-zinc-400">{label}</p>
    </div>
  );
}

export default function StatsSection() {
  return (
    <section className="relative overflow-hidden py-24">
      {/* Background gradient */}
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_center,rgba(16,185,129,0.06)_0%,transparent_70%)]" />

      <div className="mx-auto max-w-7xl px-6">
        <motion.div
          variants={staggerContainer}
          initial="hidden"
          whileInView="visible"
          viewport={viewportConfig}
          className="rounded-2xl border border-zinc-800 bg-zinc-900/50 px-6 py-16 backdrop-blur-sm md:px-12"
        >
          <motion.div
            variants={fadeInUp}
            className="mb-12 text-center"
          >
            <h2 className="text-3xl font-semibold text-zinc-50">
              Built for <span className="text-emerald-500">Scale</span>
            </h2>
          </motion.div>

          <div className="grid grid-cols-2 gap-8 md:grid-cols-4">
            {stats.map((stat) => (
              <AnimatedStat
                key={stat.label}
                value={stat.value}
                label={stat.label}
                isText={stat.isText}
              />
            ))}
          </div>
        </motion.div>
      </div>
    </section>
  );
}
