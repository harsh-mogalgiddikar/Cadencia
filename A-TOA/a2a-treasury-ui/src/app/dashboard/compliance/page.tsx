"use client";

import { motion } from "framer-motion";
import { ShieldCheck, AlertTriangle, FileCheck } from "lucide-react";
import { useAuth } from "@/lib/auth-context";
import { useComplianceHistory } from "@/hooks/useApi";
import { fadeInUp, staggerContainer } from "@/lib/animations";
import { formatINR } from "@/lib/utils";
import StatusBadge from "@/components/ui/StatusBadge";
import CopyButton from "@/components/ui/CopyButton";
import EmptyState from "@/components/ui/EmptyState";
import ApiError from "@/components/ui/ApiError";
import { CardSkeleton, TableSkeleton } from "@/components/ui/Skeleton";
import Link from "next/link";

interface CompRecord {
  session_id: string;
  purpose_code: string;
  transaction_type: string;
  inr_amount: number;
  usdc_amount: number;
  limit_utilization_pct: number;
  status: string;
  warnings: string[];
  blocking_reasons: string[];
}

export default function CompliancePage() {
  const { enterprise } = useAuth();
  const { data, error, isLoading, mutate } = useComplianceHistory(
    enterprise?.enterprise_id,
  );

  const records: CompRecord[] =
    (data as { records?: CompRecord[] })?.records ?? [];

  const approved = records.filter(
    (r) => r.status === "APPROVED" || r.status === "COMPLIANT",
  ).length;
  const avgUtil =
    records.length > 0
      ? records.reduce((s, r) => s + (r.limit_utilization_pct || 0), 0) /
        records.length
      : 0;

  // Simulated ODI/FDI limits
  const odiUsed = records
    .filter((r) => r.transaction_type === "ODI")
    .reduce((s, r) => s + (r.usdc_amount || 0), 0);
  const fdiUsed = records
    .filter((r) => r.transaction_type === "FDI")
    .reduce((s, r) => s + (r.usdc_amount || 0), 0);
  const odiLimit = 250000;
  const fdiLimit = 500000;

  return (
    <div className="mx-auto max-w-6xl">
      <motion.div
        variants={staggerContainer}
        initial="hidden"
        animate="visible"
        className="space-y-6"
      >
        <motion.div variants={fadeInUp}>
          <h2 className="text-2xl font-bold text-zinc-50">
            Compliance Records
          </h2>
          <p className="mt-1 text-sm text-zinc-400">
            FEMA & RBI compliance tracking
          </p>
        </motion.div>

        {/* Summary cards */}
        <motion.div variants={fadeInUp} className="grid grid-cols-3 gap-4">
          {isLoading ? (
            <>
              <CardSkeleton />
              <CardSkeleton />
              <CardSkeleton />
            </>
          ) : (
            <>
              <div className="rounded-xl border border-zinc-800 bg-zinc-900 p-5">
                <div className="mb-2 w-fit rounded-lg bg-emerald-500/10 p-2">
                  <FileCheck className="h-4 w-4 text-emerald-500" />
                </div>
                <p className="text-2xl font-bold text-zinc-50">
                  {records.length}
                </p>
                <p className="text-xs text-zinc-500">Total Records</p>
              </div>
              <div className="rounded-xl border border-zinc-800 bg-zinc-900 p-5">
                <div className="mb-2 w-fit rounded-lg bg-emerald-500/10 p-2">
                  <ShieldCheck className="h-4 w-4 text-emerald-500" />
                </div>
                <p className="text-2xl font-bold text-zinc-50">{approved}</p>
                <p className="text-xs text-zinc-500">Approved</p>
              </div>
              <div className="rounded-xl border border-zinc-800 bg-zinc-900 p-5">
                <div className="mb-2 w-fit rounded-lg bg-amber-500/10 p-2">
                  <AlertTriangle className="h-4 w-4 text-amber-500" />
                </div>
                <p className="text-2xl font-bold text-zinc-50">
                  {avgUtil.toFixed(0)}%
                </p>
                <p className="text-xs text-zinc-500">Avg Utilization</p>
              </div>
            </>
          )}
        </motion.div>

        {/* FEMA Limit Tracker */}
        <motion.div variants={fadeInUp}>
          <div className="grid gap-4 sm:grid-cols-2">
            {[
              { label: "ODI Limit", used: odiUsed, limit: odiLimit },
              { label: "FDI Limit", used: fdiUsed, limit: fdiLimit },
            ].map(({ label, used, limit }) => {
              const pct = Math.min((used / limit) * 100, 100);
              const color =
                pct > 85 ? "bg-red-500" : pct > 60 ? "bg-amber-500" : "bg-emerald-500";
              return (
                <div
                  key={label}
                  className="rounded-xl border border-zinc-800 bg-zinc-900 p-5"
                >
                  <div className="mb-2 flex items-center justify-between text-sm">
                    <span className="text-zinc-300">{label}</span>
                    <span className="text-zinc-400">
                      ${used.toLocaleString()} / ${limit.toLocaleString()}
                    </span>
                  </div>
                  <div className="h-2 w-full rounded-full bg-zinc-800">
                    <div
                      className={`h-2 rounded-full transition-all ${color}`}
                      style={{ width: `${pct}%` }}
                    />
                  </div>
                  <p className="mt-1 text-right text-xs text-zinc-500">
                    {pct.toFixed(1)}% utilized
                  </p>
                </div>
              );
            })}
          </div>
        </motion.div>

        {/* Table */}
        <motion.div variants={fadeInUp}>
          {isLoading ? (
            <TableSkeleton rows={8} cols={6} />
          ) : error ? (
            <ApiError error={error} onRetry={() => mutate()} />
          ) : records.length === 0 ? (
            <EmptyState
              icon={ShieldCheck}
              title="No compliance records"
              description="Records are created when negotiations include cross-border transactions."
            />
          ) : (
            <div className="overflow-hidden rounded-xl border border-zinc-800 bg-zinc-900">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-zinc-800 bg-zinc-800/50 text-xs uppercase tracking-wider text-zinc-400">
                    <th className="px-4 py-3 font-medium">Session</th>
                    <th className="px-4 py-3 font-medium">Type</th>
                    <th className="hidden px-4 py-3 font-medium sm:table-cell">
                      Purpose
                    </th>
                    <th className="px-4 py-3 font-medium">INR</th>
                    <th className="hidden px-4 py-3 font-medium md:table-cell">
                      USDC
                    </th>
                    <th className="hidden px-4 py-3 font-medium lg:table-cell">
                      Util.
                    </th>
                    <th className="px-4 py-3 font-medium">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {records.map((r, idx) => {
                    const pct = r.limit_utilization_pct || 0;
                    const uColor =
                      pct > 85
                        ? "bg-red-500"
                        : pct > 60
                        ? "bg-amber-500"
                        : "bg-emerald-500";
                    return (
                      <tr
                        key={`${r.session_id}-${idx}`}
                        className="border-t border-zinc-800 transition-colors hover:bg-zinc-800/30"
                      >
                        <td className="px-4 py-3">
                          <Link
                            href={`/dashboard/sessions/${r.session_id}`}
                            className="text-cyan-400 hover:text-cyan-300"
                          >
                            <CopyButton
                              text={r.session_id}
                              truncate={12}
                            />
                          </Link>
                        </td>
                        <td className="px-4 py-3">
                          <span
                            className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                              r.transaction_type === "DOMESTIC"
                                ? "bg-zinc-700 text-zinc-300"
                                : r.transaction_type === "ODI"
                                ? "bg-blue-500/10 text-blue-400"
                                : "bg-purple-500/10 text-purple-400"
                            }`}
                          >
                            {r.transaction_type}
                          </span>
                        </td>
                        <td className="hidden px-4 py-3 sm:table-cell">
                          <span className="font-mono text-xs text-zinc-400">
                            {r.purpose_code}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-zinc-50">
                          {formatINR(r.inr_amount)}
                        </td>
                        <td className="hidden px-4 py-3 text-cyan-400 md:table-cell">
                          {r.usdc_amount?.toFixed(2)} USDC
                        </td>
                        <td className="hidden px-4 py-3 lg:table-cell">
                          <div className="flex items-center gap-2">
                            <div className="h-1.5 w-16 rounded-full bg-zinc-800">
                              <div
                                className={`h-1.5 rounded-full ${uColor}`}
                                style={{ width: `${Math.min(pct, 100)}%` }}
                              />
                            </div>
                            <span className="text-xs text-zinc-500">
                              {pct.toFixed(0)}%
                            </span>
                          </div>
                        </td>
                        <td className="px-4 py-3">
                          <StatusBadge
                            status={r.status}
                            kind="compliance"
                          />
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </motion.div>
      </motion.div>
    </div>
  );
}
