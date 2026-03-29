"use client";

import { useState } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import { Plus, ArrowUpRight, GitBranch } from "lucide-react";
import { useSessions } from "@/hooks/useApi";
import { fadeInUp, staggerContainer } from "@/lib/animations";
import { formatINR, timeAgo } from "@/lib/utils";
import StatusBadge from "@/components/ui/StatusBadge";
import CopyButton from "@/components/ui/CopyButton";
import ApiError from "@/components/ui/ApiError";
import EmptyState from "@/components/ui/EmptyState";
import { TableSkeleton } from "@/components/ui/Skeleton";
import NewSessionModal from "@/components/dashboard/NewSessionModal";
import type { SessionStatus } from "@/types/api";

type Tab = "all" | "active" | "agreed" | "failed";

const ACTIVE_STATES = ["INIT", "BUYER_ANCHOR", "SELLER_RESPONSE", "ROUND_LOOP"];
const FAILED_STATES = ["WALKAWAY", "TIMEOUT", "STALLED", "POLICY_BREACH", "ROUND_LIMIT"];

export default function SessionsPage() {
  const [tab, setTab] = useState<Tab>("all");
  const [modalOpen, setModalOpen] = useState(false);
  const { data, error, isLoading, mutate } = useSessions();

  const items = (data as { items?: SessionStatus[] })?.items ?? [];

  const filtered = items.filter((s) => {
    if (tab === "active") return ACTIVE_STATES.includes(s.status);
    if (tab === "agreed") return s.status === "AGREED";
    if (tab === "failed") return FAILED_STATES.includes(s.status);
    return true;
  });

  const tabs: { key: Tab; label: string; count: number }[] = [
    { key: "all", label: "All", count: items.length },
    { key: "active", label: "Active", count: items.filter((s) => ACTIVE_STATES.includes(s.status)).length },
    { key: "agreed", label: "Completed", count: items.filter((s) => s.status === "AGREED").length },
    { key: "failed", label: "Failed", count: items.filter((s) => FAILED_STATES.includes(s.status)).length },
  ];

  return (
    <div className="mx-auto max-w-6xl">
      <motion.div
        variants={staggerContainer}
        initial="hidden"
        animate="visible"
        className="space-y-6"
      >
        {/* Header */}
        <motion.div variants={fadeInUp} className="flex items-center justify-between">
          <div>
            <h2 className="text-2xl font-bold text-zinc-50">Negotiation Sessions</h2>
            <p className="mt-1 text-sm text-zinc-400">
              Manage autonomous trade negotiations
            </p>
          </div>
          <button
            onClick={() => setModalOpen(true)}
            className="flex items-center gap-2 rounded-lg bg-emerald-500 px-4 py-2.5 text-sm font-semibold text-black transition-colors hover:bg-emerald-600"
          >
            <Plus className="h-4 w-4" />
            New Session
          </button>
        </motion.div>

        {/* Tabs */}
        <motion.div variants={fadeInUp}>
          <div className="flex gap-1 border-b border-zinc-800">
            {tabs.map((t) => (
              <button
                key={t.key}
                onClick={() => setTab(t.key)}
                className={`flex items-center gap-2 border-b-2 px-4 py-2.5 text-sm font-medium transition-colors ${
                  tab === t.key
                    ? "border-emerald-500 text-emerald-500"
                    : "border-transparent text-zinc-400 hover:text-zinc-300"
                }`}
              >
                {t.label}
                <span
                  className={`rounded-full px-2 py-0.5 text-xs ${
                    tab === t.key
                      ? "bg-emerald-500/10 text-emerald-400"
                      : "bg-zinc-800 text-zinc-500"
                  }`}
                >
                  {t.count}
                </span>
              </button>
            ))}
          </div>
        </motion.div>

        {/* Table */}
        <motion.div variants={fadeInUp}>
          {isLoading ? (
            <TableSkeleton rows={8} cols={6} />
          ) : error ? (
            <ApiError error={error} onRetry={() => mutate()} />
          ) : filtered.length === 0 ? (
            <EmptyState
              icon={GitBranch}
              title={tab === "all" ? "No sessions yet" : `No ${tab} sessions`}
              description="Start an autonomous negotiation to see sessions here."
              ctaLabel="New Session"
              onCtaClick={() => setModalOpen(true)}
            />
          ) : (
            <div className="overflow-hidden rounded-xl border border-zinc-800 bg-zinc-900">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-zinc-800 bg-zinc-800/50 text-xs uppercase tracking-wider text-zinc-400">
                    <th className="px-4 py-3 font-medium">Session ID</th>
                    <th className="px-4 py-3 font-medium">Status</th>
                    <th className="hidden px-4 py-3 font-medium md:table-cell">Round</th>
                    <th className="hidden px-4 py-3 font-medium lg:table-cell">Agreed Value</th>
                    <th className="hidden px-4 py-3 font-medium sm:table-cell">Timeout</th>
                    <th className="px-4 py-3 font-medium">Action</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((s) => (
                    <tr
                      key={s.session_id}
                      className="border-t border-zinc-800 transition-colors hover:bg-zinc-800/30"
                    >
                      <td className="px-4 py-3">
                        <CopyButton text={s.session_id} truncate={16} />
                      </td>
                      <td className="px-4 py-3">
                        <StatusBadge status={s.status} />
                      </td>
                      <td className="hidden px-4 py-3 text-zinc-400 md:table-cell">
                        {s.current_round} / {s.max_rounds}
                      </td>
                      <td className="hidden px-4 py-3 lg:table-cell">
                        {s.final_agreed_value ? (
                          <span className="font-medium text-emerald-400">
                            {formatINR(s.final_agreed_value)}
                          </span>
                        ) : (
                          <span className="text-zinc-500">—</span>
                        )}
                      </td>
                      <td className="hidden px-4 py-3 text-zinc-500 sm:table-cell">
                        {timeAgo(s.timeout_at)}
                      </td>
                      <td className="px-4 py-3">
                        <Link
                          href={`/dashboard/sessions/${s.session_id}`}
                          className="flex items-center gap-1 text-sm font-medium text-emerald-500 hover:text-emerald-400"
                        >
                          View
                          <ArrowUpRight className="h-3.5 w-3.5" />
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </motion.div>
      </motion.div>

      <NewSessionModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        onCreated={() => {
          setModalOpen(false);
          mutate();
        }}
      />
    </div>
  );
}
