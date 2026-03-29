"use client";

import { motion } from "framer-motion";
import {
  GitBranch,
  Activity,
  Wallet,
  ShieldCheck,
  ArrowRight,
  ArrowUpRight,
  ExternalLink,
  RefreshCw,
  Loader2,
  Check,
  X,
  Zap,
} from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { useAuth } from "@/lib/auth-context";
import { fadeInUp, staggerContainer } from "@/lib/animations";
import { formatINR, timeAgo } from "@/lib/utils";
import {
  usePlatformSummary,
  useEnterpriseSummary,
  useSessions,
  useFxRate,
  apiPost,
} from "@/hooks/useApi";
import { CardSkeleton, TableSkeleton } from "@/components/ui/Skeleton";
import ApiError from "@/components/ui/ApiError";
import EmptyState from "@/components/ui/EmptyState";
import StatusBadge from "@/components/ui/StatusBadge";
import CopyButton from "@/components/ui/CopyButton";
import type { PlatformSummary, FxQuote, SessionStatus } from "@/types/api";

export default function DashboardOverview() {
  const { enterprise } = useAuth();
  const { data: platform, error: platErr, isLoading: platLoading, mutate: mutatePlat } = usePlatformSummary();
  const { data: entSummary } = useEnterpriseSummary(enterprise?.enterprise_id);
  const { data: sessionsData, error: sessErr, isLoading: sessLoading, mutate: mutateSess } = useSessions();
  const { data: fxData } = useFxRate();
  const [verifying, setVerifying] = useState(false);
  const [verifyResult, setVerifyResult] = useState<{ valid: boolean } | null>(null);

  const plat = platform as PlatformSummary | undefined;
  const fx = fxData as FxQuote | undefined;
  const sessions = (sessionsData as { items?: SessionStatus[] })?.items?.slice(0, 5) ?? [];

  const greeting = (() => {
    const h = new Date().getHours();
    if (h < 12) return "Good morning";
    if (h < 17) return "Good afternoon";
    return "Good evening";
  })();

  const handleVerifyChain = async () => {
    setVerifying(true);
    setVerifyResult(null);
    try {
      const res = await apiPost("/audit/verify-chain");
      setVerifyResult(res as { valid: boolean });
    } catch {
      setVerifyResult({ valid: false });
    } finally {
      setVerifying(false);
    }
  };

  const statCards = [
    {
      label: "Total Sessions",
      icon: GitBranch,
      value: plat?.total_sessions ?? 0,
      fmt: (v: number) => String(v),
    },
    {
      label: "Active Sessions",
      icon: Activity,
      value: plat?.active_sessions ?? 0,
      fmt: (v: number) => String(v),
    },
    {
      label: "Total Escrow Value",
      icon: Wallet,
      value: plat?.total_escrow_value_inr ?? 0,
      fmt: (v: number) => formatINR(v),
    },
    {
      label: "Compliance Rate",
      icon: ShieldCheck,
      value: plat?.compliance_rate ?? 0,
      fmt: (v: number) => `${(v * 100).toFixed(0)}%`,
    },
  ];

  return (
    <div className="mx-auto max-w-6xl">
      <motion.div
        variants={staggerContainer}
        initial="hidden"
        animate="visible"
        className="space-y-6"
      >
        {/* Greeting */}
        <motion.div variants={fadeInUp}>
          <h2 className="text-2xl font-bold text-zinc-50">
            {greeting}, {enterprise?.legal_name ?? "Enterprise"} 👋
          </h2>
          <p className="mt-1 text-sm text-zinc-400">
            Treasury overview for your enterprise
          </p>
        </motion.div>

        {/* Demo Banner — when no sessions exist */}
        {plat && (plat.total_sessions ?? 0) === 0 && (
          <motion.div variants={fadeInUp}>
            <div className="relative overflow-hidden rounded-xl border border-blue-500/20 bg-gradient-to-r from-blue-500/10 via-indigo-500/10 to-purple-500/10 p-6">
              <div className="absolute -right-8 -top-8 h-32 w-32 rounded-full bg-blue-500/5 blur-2xl" />
              <div className="relative flex flex-col items-start gap-4 sm:flex-row sm:items-center sm:justify-between">
                <div className="flex items-start gap-3">
                  <div className="rounded-lg bg-blue-500/20 p-2.5">
                    <Zap className="h-5 w-5 text-blue-400" />
                  </div>
                  <div>
                    <p className="font-semibold text-white">
                      See the full A2A Treasury flow in action
                    </p>
                    <p className="mt-0.5 text-sm text-zinc-400">
                      Watch AI agents negotiate, deploy Algorand escrow, settle via x402 — one click.
                    </p>
                  </div>
                </div>
                <Link
                  href="/demo"
                  className="inline-flex shrink-0 items-center gap-2 rounded-lg bg-blue-500 px-5 py-2.5 text-sm font-semibold text-white shadow-lg shadow-blue-500/20 transition-all hover:bg-blue-400 hover:shadow-blue-500/30"
                >
                  <Zap className="h-4 w-4" />
                  Run Live Demo
                </Link>
              </div>
            </div>
          </motion.div>
        )}

        {/* Stat Cards */}
        <motion.div variants={fadeInUp}>
          {platLoading ? (
            <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
              {[1, 2, 3, 4].map((i) => (
                <CardSkeleton key={i} />
              ))}
            </div>
          ) : platErr ? (
            <ApiError error={platErr} onRetry={() => mutatePlat()} />
          ) : (
            <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
              {statCards.map(({ label, icon: Icon, value, fmt }) => (
                <div
                  key={label}
                  className="rounded-xl border border-zinc-800 bg-zinc-900 p-6 transition-colors hover:border-zinc-700"
                >
                  <div className="mb-3 flex items-center gap-2">
                    <div className="rounded-lg bg-emerald-500/10 p-2">
                      <Icon className="h-4 w-4 text-emerald-500" />
                    </div>
                  </div>
                  <p className="text-3xl font-bold text-zinc-50">{fmt(value)}</p>
                  <p className="mt-1 text-xs text-zinc-500">{label}</p>
                </div>
              ))}
            </div>
          )}
        </motion.div>

        {/* FX Rate Ticker */}
        {fx && (
          <motion.div variants={fadeInUp}>
            <div className="flex items-center gap-4 rounded-lg border border-zinc-800 bg-zinc-900 px-4 py-2.5 font-mono text-sm text-zinc-400">
              <span>
                1 USD = ₹{fx.mid_rate?.toFixed(2)}
              </span>
              <span className="text-zinc-600">·</span>
              <span>
                Spread: {fx.spread_bps}bps
              </span>
              <span className="text-zinc-600">·</span>
              <span className="text-zinc-500">
                Source: {fx.source} · Updated {fx.fetched_at ? timeAgo(fx.fetched_at) : "—"}
              </span>
            </div>
          </motion.div>
        )}

        {/* Recent Sessions */}
        <motion.div variants={fadeInUp}>
          <div className="mb-3 flex items-center justify-between">
            <h3 className="text-lg font-semibold text-zinc-50">
              Recent Sessions
            </h3>
            <Link
              href="/dashboard/sessions"
              className="flex items-center gap-1 text-sm text-emerald-500 transition-colors hover:text-emerald-400"
            >
              View all
              <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          </div>

          {sessLoading ? (
            <TableSkeleton rows={5} cols={4} />
          ) : sessErr ? (
            <ApiError error={sessErr} onRetry={() => mutateSess()} />
          ) : sessions.length === 0 ? (
            <EmptyState
              icon={GitBranch}
              title="No sessions yet"
              description="Start your first autonomous negotiation to see activity here."
              ctaLabel="Start Negotiation"
              ctaHref="/dashboard/sessions"
            />
          ) : (
            <div className="overflow-hidden rounded-xl border border-zinc-800 bg-zinc-900">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-zinc-800 bg-zinc-800/50 text-xs uppercase tracking-wider text-zinc-400">
                    <th className="px-4 py-3 font-medium">Session</th>
                    <th className="px-4 py-3 font-medium">Status</th>
                    <th className="hidden px-4 py-3 font-medium sm:table-cell">
                      Round
                    </th>
                    <th className="hidden px-4 py-3 font-medium md:table-cell">
                      Agreed Value
                    </th>
                    <th className="px-4 py-3 font-medium">Action</th>
                  </tr>
                </thead>
                <tbody>
                  {sessions.map((s: SessionStatus) => (
                    <tr
                      key={s.session_id}
                      className="border-t border-zinc-800 transition-colors hover:bg-zinc-800/30"
                    >
                      <td className="px-4 py-3">
                        <CopyButton
                          text={s.session_id}
                          truncate={16}
                        />
                      </td>
                      <td className="px-4 py-3">
                        <StatusBadge status={s.status} />
                      </td>
                      <td className="hidden px-4 py-3 text-zinc-400 sm:table-cell">
                        {s.current_round} / {s.max_rounds}
                      </td>
                      <td className="hidden px-4 py-3 md:table-cell">
                        {s.final_agreed_value ? (
                          <span className="font-medium text-emerald-400">
                            {formatINR(s.final_agreed_value)}
                          </span>
                        ) : (
                          <span className="text-zinc-500">—</span>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        <Link
                          href={`/dashboard/sessions/${s.session_id}`}
                          className="flex items-center gap-1 text-sm text-emerald-500 hover:text-emerald-400"
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

        {/* Quick Actions */}
        <motion.div variants={fadeInUp} className="grid gap-4 sm:grid-cols-2">
          <Link
            href="/dashboard/sessions"
            className="group flex items-center justify-between rounded-xl border border-zinc-800 bg-zinc-900 p-6 transition-all hover:border-emerald-500/30 hover:bg-emerald-500/5"
          >
            <div>
              <p className="font-semibold text-zinc-50">Start New Negotiation</p>
              <p className="mt-1 text-sm text-zinc-400">
                Launch an autonomous buyer↔seller session
              </p>
            </div>
            <ArrowRight className="h-5 w-5 text-emerald-500 transition-transform group-hover:translate-x-1" />
          </Link>

          <button
            onClick={handleVerifyChain}
            disabled={verifying}
            className="group flex items-center justify-between rounded-xl border border-zinc-800 bg-zinc-900 p-6 text-left transition-all hover:border-cyan-400/30 hover:bg-cyan-400/5"
          >
            <div>
              <p className="font-semibold text-zinc-50">Verify Audit Chain</p>
              <p className="mt-1 text-sm text-zinc-400">
                {verifyResult
                  ? verifyResult.valid
                    ? "✅ SHA-256 chain verified — all entries authentic"
                    : "❌ Chain integrity broken — investigate immediately"
                  : "Check SHA-256 hash chain integrity"}
              </p>
            </div>
            {verifying ? (
              <Loader2 className="h-5 w-5 animate-spin text-cyan-400" />
            ) : verifyResult ? (
              verifyResult.valid ? (
                <Check className="h-5 w-5 text-emerald-500" />
              ) : (
                <X className="h-5 w-5 text-red-400" />
              )
            ) : (
              <RefreshCw className="h-5 w-5 text-cyan-400 transition-transform group-hover:rotate-45" />
            )}
          </button>
        </motion.div>
      </motion.div>
    </div>
  );
}
