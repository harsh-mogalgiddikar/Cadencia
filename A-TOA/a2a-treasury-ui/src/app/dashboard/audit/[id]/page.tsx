"use client";

import { useParams } from "next/navigation";
import { useState, useEffect } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import {
  ArrowLeft,
  ShieldCheck,
  AlertTriangle,
  Check,
  X,
  Search,
  ExternalLink,
  Hash,
  Loader2,
} from "lucide-react";
import { useMerkleRoot, apiPost } from "@/hooks/useApi";
import { fadeInUp, staggerContainer } from "@/lib/animations";
import { timeAgo } from "@/lib/utils";
import CopyButton from "@/components/ui/CopyButton";
import ApiError from "@/components/ui/ApiError";
import { CardSkeleton, TableSkeleton } from "@/components/ui/Skeleton";
import type { MerkleInfo, AuditEntry } from "@/types/api";

export default function AuditDetailPage() {
  const params = useParams();
  const sessionId = params.id as string;

  const { data: merkleData } = useMerkleRoot(sessionId);
  const merkle = merkleData as MerkleInfo | undefined;

  // Chain verification
  const [chainResult, setChainResult] = useState<{
    valid: boolean;
    entries_checked: number;
  } | null>(null);
  const [chainLoading, setChainLoading] = useState(true);

  // Audit entries
  const [entries, setEntries] = useState<AuditEntry[]>([]);
  const [entriesLoading, setEntriesLoading] = useState(true);

  // Leaf verification
  const [leafHash, setLeafHash] = useState("");
  const [leafResult, setLeafResult] = useState<{
    verified: boolean;
  } | null>(null);
  const [leafLoading, setLeafLoading] = useState(false);

  useEffect(() => {
    // Verify chain
    fetch(`/api/v1/audit/verify-chain?session_id=${sessionId}`, {
      credentials: "include",
    })
      .then((r) => r.json())
      .then((d) => setChainResult(d))
      .catch(() => setChainResult({ valid: false, entries_checked: 0 }))
      .finally(() => setChainLoading(false));

    // Load transcript (has audit entries)
    fetch(`/api/v1/sessions/${sessionId}/transcript`, {
      credentials: "include",
    })
      .then((r) => r.json())
      .then((d) => {
        setEntries(d.entries || d.audit_entries || []);
      })
      .catch(() => {})
      .finally(() => setEntriesLoading(false));
  }, [sessionId]);

  const handleVerifyLeaf = async () => {
    if (!leafHash.trim()) return;
    setLeafLoading(true);
    setLeafResult(null);
    try {
      const res = await apiPost(`/audit/${sessionId}/verify-leaf`, {
        leaf_hash: leafHash.trim(),
      });
      setLeafResult(res as { verified: boolean });
    } catch {
      setLeafResult({ verified: false });
    } finally {
      setLeafLoading(false);
    }
  };

  return (
    <div className="mx-auto max-w-6xl">
      <motion.div
        variants={staggerContainer}
        initial="hidden"
        animate="visible"
        className="space-y-6"
      >
        {/* Header */}
        <motion.div variants={fadeInUp} className="flex items-center gap-4">
          <Link
            href={`/dashboard/sessions/${sessionId}`}
            className="flex items-center gap-1 text-sm text-zinc-400 hover:text-zinc-300"
          >
            <ArrowLeft className="h-4 w-4" />
            Session
          </Link>
          <CopyButton text={sessionId} truncate={16} />
          <span className="text-lg font-bold text-zinc-50">Audit Trail</span>
        </motion.div>

        {/* Chain Verification Banner */}
        <motion.div variants={fadeInUp}>
          {chainLoading ? (
            <CardSkeleton />
          ) : chainResult?.valid ? (
            <div className="flex items-center gap-3 rounded-xl border border-emerald-500/30 bg-emerald-500/10 px-4 py-3">
              <ShieldCheck className="h-5 w-5 text-emerald-400" />
              <p className="text-sm font-medium text-emerald-400">
                ✅ SHA-256 Hash Chain VALID ·{" "}
                {chainResult.entries_checked} entries · Integrity confirmed
              </p>
            </div>
          ) : (
            <div className="flex items-center gap-3 rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3">
              <AlertTriangle className="h-5 w-5 text-red-400" />
              <p className="text-sm font-medium text-red-400">
                ❌ Hash chain integrity could not be verified
              </p>
            </div>
          )}
        </motion.div>

        {/* Merkle Root */}
        {merkle && (
          <motion.div variants={fadeInUp}>
            <div className="rounded-xl border border-zinc-800 bg-zinc-900 p-6">
              <h3 className="mb-4 flex items-center gap-2 font-semibold text-zinc-50">
                <Hash className="h-4 w-4 text-cyan-400" />
                Merkle Root
              </h3>
              <div className="space-y-3">
                <div>
                  <span className="text-xs text-zinc-500">Root Hash</span>
                  <p className="mt-1 break-all font-mono text-sm text-cyan-400">
                    {merkle.merkle_root}
                  </p>
                </div>
                <div className="flex flex-wrap gap-4 text-sm">
                  <div>
                    <span className="text-zinc-500">Leaf Count: </span>
                    <span className="text-zinc-50">{merkle.leaf_count}</span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <span className="text-zinc-500">On-Chain: </span>
                    {merkle.anchored_on_chain ? (
                      <Check className="h-4 w-4 text-emerald-400" />
                    ) : (
                      <X className="h-4 w-4 text-red-400" />
                    )}
                  </div>
                </div>
                {merkle.anchor_tx_id && merkle.verification_url && (
                  <a
                    href={merkle.verification_url}
                    target="_blank"
                    rel="noreferrer"
                    className="flex items-center gap-1.5 text-sm text-cyan-400 hover:text-cyan-300"
                  >
                    View Anchor TX on Explorer
                    <ExternalLink className="h-3.5 w-3.5" />
                  </a>
                )}
              </div>
            </div>
          </motion.div>
        )}

        {/* Leaf Verification */}
        <motion.div variants={fadeInUp}>
          <div className="rounded-xl border border-zinc-800 bg-zinc-900 p-6">
            <h3 className="mb-3 font-semibold text-zinc-50">
              Verify Leaf Hash
            </h3>
            <div className="flex gap-2">
              <input
                type="text"
                placeholder="Enter a SHA-256 hash to verify..."
                value={leafHash}
                onChange={(e) => setLeafHash(e.target.value)}
                className="h-10 flex-1 rounded-lg border border-zinc-700 bg-zinc-800 px-3 font-mono text-xs text-zinc-50 placeholder:text-zinc-500 focus:border-emerald-500 focus:outline-none"
              />
              <button
                onClick={handleVerifyLeaf}
                disabled={leafLoading || !leafHash.trim()}
                className="flex h-10 items-center gap-2 rounded-lg bg-emerald-500 px-4 text-sm font-semibold text-black hover:bg-emerald-600 disabled:opacity-50"
              >
                {leafLoading ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Search className="h-4 w-4" />
                )}
                Verify
              </button>
            </div>
            {leafResult && (
              <div
                className={`mt-3 rounded-lg border px-3 py-2 text-sm ${
                  leafResult.verified
                    ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-400"
                    : "border-red-500/30 bg-red-500/10 text-red-400"
                }`}
              >
                {leafResult.verified
                  ? "✅ Leaf is authentic — exists in Merkle tree"
                  : "❌ Hash not found in tree"}
              </div>
            )}
          </div>
        </motion.div>

        {/* Hash Chain Table */}
        <motion.div variants={fadeInUp}>
          <h3 className="mb-3 text-lg font-semibold text-zinc-50">
            Hash Chain
          </h3>
          {entriesLoading ? (
            <TableSkeleton rows={8} cols={5} />
          ) : entries.length === 0 ? (
            <div className="rounded-xl border border-zinc-800 bg-zinc-900 p-8 text-center text-zinc-500">
              No audit entries found for this session
            </div>
          ) : (
            <div className="overflow-hidden rounded-xl border border-zinc-800 bg-zinc-900">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-zinc-800 bg-zinc-800/50 text-xs uppercase tracking-wider text-zinc-400">
                    <th className="px-4 py-3 font-medium">#</th>
                    <th className="px-4 py-3 font-medium">Action</th>
                    <th className="px-4 py-3 font-medium">Actor</th>
                    <th className="hidden px-4 py-3 font-medium md:table-cell">
                      This Hash
                    </th>
                    <th className="hidden px-4 py-3 font-medium lg:table-cell">
                      Prev Hash
                    </th>
                    <th className="px-4 py-3 font-medium">Time</th>
                  </tr>
                </thead>
                <tbody>
                  {entries.map((e: AuditEntry, idx: number) => (
                    <tr
                      key={e.log_id || idx}
                      className="border-t border-zinc-800 transition-colors hover:bg-zinc-800/30"
                    >
                      <td className="px-4 py-3 text-zinc-500">
                        {idx + 1}
                      </td>
                      <td className="px-4 py-3">
                        <span className="font-mono text-xs text-emerald-400">
                          {e.action}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-zinc-400">
                        {e.actor_id === "system"
                          ? "system"
                          : e.actor_id?.slice(0, 8) + "..."}
                      </td>
                      <td className="hidden px-4 py-3 md:table-cell">
                        <CopyButton
                          text={e.this_hash || ""}
                          truncate={16}
                        />
                      </td>
                      <td className="hidden px-4 py-3 lg:table-cell">
                        <span className="font-mono text-xs text-zinc-500">
                          {e.prev_hash
                            ? `${e.prev_hash.slice(0, 8)}...`
                            : "—"}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-zinc-500">
                        {e.timestamp ? timeAgo(e.timestamp) : "—"}
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
