"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import { Shield, Wallet, ExternalLink, Lock, Unlock } from "lucide-react";
import { useAuth } from "@/lib/auth-context";
import { useAuditLog, apiPost } from "@/hooks/useApi";
import { fadeInUp, staggerContainer } from "@/lib/animations";
import { formatINR, timeAgo } from "@/lib/utils";
import StatusBadge from "@/components/ui/StatusBadge";
import CopyButton from "@/components/ui/CopyButton";
import EmptyState from "@/components/ui/EmptyState";
import { CardSkeleton, TableSkeleton } from "@/components/ui/Skeleton";
import ApiError from "@/components/ui/ApiError";
import type { EscrowContract } from "@/types/api";

export default function EscrowPage() {
  const { enterprise } = useAuth();
  const [escrows, setEscrows] = useState<EscrowContract[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);

  // Fetch escrows from audit log (there's no list-all-escrows endpoint, we'll derive from sessions)
  useEffect(() => {
    const fetchEscrows = async () => {
      try {
        const res = await fetch("/api/v1/sessions/?page_size=100", {
          credentials: "include",
        });
        if (!res.ok) throw await res.json();
        const data = await res.json();
        const items = data.items || [];

        // For each AGREED session, try to load escrow
        const results: EscrowContract[] = [];
        for (const s of items) {
          try {
            const eRes = await fetch(
              `/api/v1/escrow/session/${s.session_id}`,
              { credentials: "include" },
            );
            if (eRes.ok) {
              results.push(await eRes.json());
            }
          } catch {
            // skip
          }
        }
        setEscrows(results);
      } catch (err) {
        setError(err);
      } finally {
        setLoading(false);
      }
    };
    fetchEscrows();
  }, []);

  const handleAction = async (
    escrowId: string,
    action: "fund" | "release" | "refund",
  ) => {
    const confirmed = confirm(
      `Are you sure you want to ${action} this escrow? This action cannot be undone.`,
    );
    if (!confirmed) return;
    try {
      if (action === "release") {
        await apiPost(`/escrow/${escrowId}/release`, {
          milestone: "milestone-1",
        });
      } else if (action === "refund") {
        await apiPost(`/escrow/${escrowId}/refund`, {
          reason: "Dispute — refund",
        });
      } else {
        await apiPost(`/escrow/${escrowId}/fund`);
      }
      // Refresh
      window.location.reload();
    } catch {
      alert(`Failed to ${action} escrow`);
    }
  };

  const totalLocked = escrows
    .filter((e) => ["DEPLOYED", "FUNDED"].includes(e.status))
    .reduce((sum, e) => sum + (e.amount || 0), 0);

  const pendingRelease = escrows.filter(
    (e) => e.status === "FUNDED",
  ).length;

  const completed = escrows.filter(
    (e) => e.status === "RELEASED",
  ).length;

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
            Escrow Contracts
          </h2>
          <p className="mt-1 text-sm text-zinc-400">
            Manage x402 trustless escrow on Algorand
          </p>
        </motion.div>

        {/* Summary cards */}
        <motion.div variants={fadeInUp} className="grid grid-cols-3 gap-4">
          {[
            {
              label: "Total Locked",
              value: `${totalLocked.toFixed(2)} USDC`,
              icon: Lock,
            },
            {
              label: "Pending Release",
              value: String(pendingRelease),
              icon: Wallet,
            },
            {
              label: "Completed",
              value: String(completed),
              icon: Unlock,
            },
          ].map(({ label, value, icon: Icon }) => (
            <div
              key={label}
              className="rounded-xl border border-zinc-800 bg-zinc-900 p-5"
            >
              <div className="mb-2 rounded-lg bg-emerald-500/10 p-2 w-fit">
                <Icon className="h-4 w-4 text-emerald-500" />
              </div>
              <p className="text-2xl font-bold text-zinc-50">{value}</p>
              <p className="mt-0.5 text-xs text-zinc-500">{label}</p>
            </div>
          ))}
        </motion.div>

        {/* Table */}
        <motion.div variants={fadeInUp}>
          {loading ? (
            <TableSkeleton rows={5} cols={5} />
          ) : error ? (
            <ApiError error={error} />
          ) : escrows.length === 0 ? (
            <EmptyState
              icon={Shield}
              title="No escrow contracts"
              description="Escrow contracts are created automatically when negotiations reach agreement."
            />
          ) : (
            <div className="overflow-hidden rounded-xl border border-zinc-800 bg-zinc-900">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-zinc-800 bg-zinc-800/50 text-xs uppercase tracking-wider text-zinc-400">
                    <th className="px-4 py-3 font-medium">Contract</th>
                    <th className="px-4 py-3 font-medium">Session</th>
                    <th className="px-4 py-3 font-medium">Amount</th>
                    <th className="px-4 py-3 font-medium">Status</th>
                    <th className="px-4 py-3 font-medium">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {escrows.map((e) => (
                    <tr
                      key={e.escrow_id}
                      className="border-t border-zinc-800 transition-colors hover:bg-zinc-800/30"
                    >
                      <td className="px-4 py-3">
                        <CopyButton
                          text={e.contract_ref || e.escrow_id}
                          truncate={16}
                        />
                      </td>
                      <td className="px-4 py-3">
                        <Link
                          href={`/dashboard/sessions/${e.session_id}`}
                          className="text-cyan-400 hover:text-cyan-300"
                        >
                          <CopyButton text={e.session_id} truncate={12} />
                        </Link>
                      </td>
                      <td className="px-4 py-3 font-medium text-zinc-50">
                        {e.amount ? `${e.amount.toFixed(2)} USDC` : "—"}
                      </td>
                      <td className="px-4 py-3">
                        <StatusBadge
                          status={e.status}
                          kind="escrow"
                          pulse={e.status === "FUNDED"}
                        />
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex gap-2">
                          {e.status === "DEPLOYED" && (
                            <button
                              onClick={() =>
                                handleAction(e.escrow_id, "fund")
                              }
                              className="rounded bg-amber-500 px-2.5 py-1 text-xs font-semibold text-black hover:bg-amber-600"
                            >
                              Fund
                            </button>
                          )}
                          {e.status === "FUNDED" && (
                            <>
                              <button
                                onClick={() =>
                                  handleAction(e.escrow_id, "release")
                                }
                                className="rounded bg-emerald-500 px-2.5 py-1 text-xs font-semibold text-black hover:bg-emerald-600"
                              >
                                Release
                              </button>
                              <button
                                onClick={() =>
                                  handleAction(e.escrow_id, "refund")
                                }
                                className="rounded bg-red-500/80 px-2.5 py-1 text-xs font-semibold text-white hover:bg-red-500"
                              >
                                Refund
                              </button>
                            </>
                          )}
                          {e.tx_ref && (
                            <a
                              href={`https://lora.algokit.io/testnet/transaction/${e.tx_ref}`}
                              target="_blank"
                              rel="noreferrer"
                              className="flex items-center gap-1 rounded border border-zinc-700 px-2.5 py-1 text-xs text-zinc-400 hover:text-zinc-300"
                            >
                              <ExternalLink className="h-3 w-3" />
                              TX
                            </a>
                          )}
                        </div>
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
