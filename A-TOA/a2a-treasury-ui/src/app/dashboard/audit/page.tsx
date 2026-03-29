"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import {
  FileSearch,
  ShieldCheck,
  AlertTriangle,
  ChevronRight,
  Loader2,
  Hash,
  Clock,
} from "lucide-react";
import { useAuth } from "@/lib/auth-context";
import { useAuditLog } from "@/hooks/useApi";
import { fadeInUp, staggerContainer } from "@/lib/animations";
import { timeAgo } from "@/lib/utils";
import CopyButton from "@/components/ui/CopyButton";
import { CardSkeleton, TableSkeleton } from "@/components/ui/Skeleton";

interface AuditItem {
  log_id: string;
  entity_type: string;
  action: string;
  actor_id: string;
  timestamp: string;
  payload?: Record<string, unknown>;
}

interface AuditLogResponse {
  items: AuditItem[];
  total: number;
  page: number;
  page_size: number;
}

// Action badge colour mapping
function actionColor(action: string): string {
  if (action.includes("REGISTERED") || action.includes("CREATED"))
    return "border-cyan-500/30 bg-cyan-500/10 text-cyan-400";
  if (action.includes("AGREED") || action.includes("ACTIVATED") || action.includes("VERIFIED"))
    return "border-emerald-500/30 bg-emerald-500/10 text-emerald-400";
  if (action.includes("REJECTED") || action.includes("FAILED") || action.includes("BROKEN"))
    return "border-red-500/30 bg-red-500/10 text-red-400";
  if (action.includes("LLM") || action.includes("ADVISORY"))
    return "border-purple-500/30 bg-purple-500/10 text-purple-400";
  if (action.includes("OFFER") || action.includes("COUNTER"))
    return "border-amber-500/30 bg-amber-500/10 text-amber-400";
  return "border-zinc-700 bg-zinc-800 text-zinc-400";
}

export default function AuditListPage() {
  const { enterprise } = useAuth();
  const { data, isLoading, error } = useAuditLog(enterprise?.enterprise_id);
  const auditData = data as AuditLogResponse | undefined;

  // Chain verification
  const [chainResult, setChainResult] = useState<{
    valid: boolean;
    total_entries: number;
  } | null>(null);
  const [chainLoading, setChainLoading] = useState(true);

  useEffect(() => {
    fetch("/api/v1/audit/verify-chain", { credentials: "include" })
      .then((r) => r.json())
      .then((d) => setChainResult(d))
      .catch(() => setChainResult({ valid: false, total_entries: 0 }))
      .finally(() => setChainLoading(false));
  }, []);

  // Collect unique session IDs from audit entries for quick nav
  const sessionIds = Array.from(
    new Set(
      (auditData?.items || [])
        .filter((e) => e.entity_type === "negotiation")
        .map((e) => {
          const payload = e.payload || {};
          return (payload.session_id as string) || e.log_id;
        }),
    ),
  );

  return (
    <div className="mx-auto max-w-6xl">
      <motion.div
        variants={staggerContainer}
        initial="hidden"
        animate="visible"
        className="space-y-6"
      >
        {/* Header */}
        <motion.div variants={fadeInUp}>
          <h2 className="text-2xl font-bold text-zinc-50">Audit Trail</h2>
          <p className="mt-1 text-sm text-zinc-400">
            SHA-256 hash-chained, tamper-proof audit log for your enterprise
          </p>
        </motion.div>

        {/* Chain Verification Banner */}
        <motion.div variants={fadeInUp}>
          {chainLoading ? (
            <CardSkeleton />
          ) : chainResult?.valid ? (
            <div className="flex items-center gap-3 rounded-xl border border-emerald-500/30 bg-emerald-500/10 px-5 py-4">
              <ShieldCheck className="h-5 w-5 text-emerald-400" />
              <div>
                <p className="text-sm font-medium text-emerald-400">
                  ✅ Global Hash Chain Verified
                </p>
                <p className="text-xs text-emerald-400/70">
                  {chainResult.total_entries} entries · All hashes valid
                </p>
              </div>
            </div>
          ) : (
            <div className="flex items-center gap-3 rounded-xl border border-red-500/30 bg-red-500/10 px-5 py-4">
              <AlertTriangle className="h-5 w-5 text-red-400" />
              <div>
                <p className="text-sm font-medium text-red-400">
                  ❌ Hash chain integrity issue detected
                </p>
                <p className="text-xs text-red-400/70">
                  Some entries may have been tampered with
                </p>
              </div>
            </div>
          )}
        </motion.div>

        {/* Stats */}
        <motion.div variants={fadeInUp}>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <div className="rounded-xl border border-zinc-800 bg-zinc-900 p-4">
              <div className="flex items-center gap-2 text-zinc-500">
                <Hash className="h-4 w-4" />
                <span className="text-xs uppercase tracking-wider">
                  Total Entries
                </span>
              </div>
              <p className="mt-2 text-2xl font-bold text-zinc-50">
                {isLoading ? "—" : auditData?.total ?? 0}
              </p>
            </div>
            <div className="rounded-xl border border-zinc-800 bg-zinc-900 p-4">
              <div className="flex items-center gap-2 text-zinc-500">
                <ShieldCheck className="h-4 w-4" />
                <span className="text-xs uppercase tracking-wider">
                  Chain Status
                </span>
              </div>
              <p className="mt-2 text-2xl font-bold">
                {chainLoading ? (
                  <span className="text-zinc-500">...</span>
                ) : chainResult?.valid ? (
                  <span className="text-emerald-400">Valid</span>
                ) : (
                  <span className="text-red-400">Broken</span>
                )}
              </p>
            </div>
            <div className="rounded-xl border border-zinc-800 bg-zinc-900 p-4">
              <div className="flex items-center gap-2 text-zinc-500">
                <Clock className="h-4 w-4" />
                <span className="text-xs uppercase tracking-wider">
                  Latest Entry
                </span>
              </div>
              <p className="mt-2 text-sm font-medium text-zinc-50">
                {isLoading
                  ? "—"
                  : auditData?.items?.[0]?.timestamp
                  ? timeAgo(auditData.items[0].timestamp)
                  : "No entries yet"}
              </p>
            </div>
          </div>
        </motion.div>

        {/* Audit Entries Table */}
        <motion.div variants={fadeInUp}>
          <h3 className="mb-3 text-lg font-semibold text-zinc-50">
            Recent Activity
          </h3>
          {isLoading ? (
            <TableSkeleton rows={8} cols={5} />
          ) : error ? (
            <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-8 text-center text-red-400">
              Failed to load audit log
            </div>
          ) : !auditData?.items?.length ? (
            <div className="rounded-xl border border-zinc-800 bg-zinc-900 p-12 text-center">
              <FileSearch className="mx-auto mb-3 h-10 w-10 text-zinc-600" />
              <p className="font-medium text-zinc-400">No audit entries yet</p>
              <p className="mt-1 text-sm text-zinc-500">
                Entries will appear as you register, negotiate, and settle
                transactions.
              </p>
            </div>
          ) : (
            <div className="overflow-hidden rounded-xl border border-zinc-800 bg-zinc-900">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-zinc-800 bg-zinc-800/50 text-xs uppercase tracking-wider text-zinc-400">
                    <th className="px-4 py-3 font-medium">#</th>
                    <th className="px-4 py-3 font-medium">Action</th>
                    <th className="px-4 py-3 font-medium">Type</th>
                    <th className="hidden px-4 py-3 font-medium md:table-cell">
                      Actor
                    </th>
                    <th className="px-4 py-3 font-medium">Time</th>
                    <th className="px-4 py-3 font-medium" />
                  </tr>
                </thead>
                <tbody>
                  {auditData.items.map((e, idx) => (
                    <tr
                      key={e.log_id}
                      className="border-t border-zinc-800 transition-colors hover:bg-zinc-800/30"
                    >
                      <td className="px-4 py-3 text-zinc-500">
                        {(auditData.page - 1) * auditData.page_size + idx + 1}
                      </td>
                      <td className="px-4 py-3">
                        <span
                          className={`inline-block rounded-full border px-2.5 py-0.5 text-[11px] font-medium ${actionColor(
                            e.action,
                          )}`}
                        >
                          {e.action}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-xs text-zinc-400">
                        {e.entity_type}
                      </td>
                      <td className="hidden px-4 py-3 md:table-cell">
                        <span className="font-mono text-xs text-zinc-500">
                          {e.actor_id === "system"
                            ? "system"
                            : e.actor_id?.slice(0, 12) + "…"}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-xs text-zinc-500">
                        {e.timestamp ? timeAgo(e.timestamp) : "—"}
                      </td>
                      <td className="px-4 py-3">
                        {e.entity_type === "negotiation" && (
                          <Link
                            href={`/dashboard/audit/${e.log_id}`}
                            className="text-zinc-500 hover:text-emerald-400"
                          >
                            <ChevronRight className="h-4 w-4" />
                          </Link>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </motion.div>
      </motion.div>
    </div>
  );
}
