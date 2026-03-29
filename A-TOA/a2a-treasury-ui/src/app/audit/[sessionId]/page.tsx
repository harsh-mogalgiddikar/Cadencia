"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { motion } from "framer-motion";
import Navbar from "@/components/Navbar";
import AuditTrail from "@/components/AuditTrail";
import { useAudit } from "@/hooks/useAudit";
import { getSessionStatus } from "@/lib/api";
import {
    truncateHash,
    explorerTxUrl,
    formatINR,
} from "@/lib/utils";
import type { AuthState, NegotiationSession } from "@/lib/types";
import {
    ExternalLink,
    GitBranch,
    Loader2,
    ShieldCheck,
    BarChart3,
} from "lucide-react";

export default function AuditPage() {
    const params = useParams();
    const router = useRouter();
    const sessionId = params.sessionId as string;

    const [auth, setAuth] = useState<AuthState | null>(null);
    const [session, setSession] = useState<NegotiationSession | null>(null);

    const { entries, merkle, chainValid, isLoading } = useAudit(sessionId);

    useEffect(() => {
        const raw = localStorage.getItem("acf_auth");
        if (!raw) {
            router.push("/register");
            return;
        }
        setAuth(JSON.parse(raw));
    }, [router]);

    useEffect(() => {
        if (!auth) return;
        getSessionStatus(sessionId)
            .then((res) => setSession(res.data))
            .catch(() => { });
    }, [auth, sessionId]);

    if (!auth) return null;

    return (
        <div className="min-h-screen">
            <Navbar />

            <div className="mx-auto max-w-7xl px-6 py-8">
                <motion.div
                    initial={{ opacity: 0, y: -10 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="mb-8"
                >
                    <h1 className="text-3xl font-bold tracking-tight text-white">
                        📋 Audit Trail
                    </h1>
                    <p className="mt-1 text-sm text-gray-400">
                        Session:{" "}
                        <span className="font-mono text-gray-300">
                            {truncateHash(sessionId, 12)}
                        </span>{" "}
                        · Cryptographic verification
                    </p>
                </motion.div>

                <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
                    {/* Left — Audit Entries */}
                    <div className="lg:col-span-2">
                        {isLoading ? (
                            <div className="space-y-3">
                                {[1, 2, 3, 4, 5].map((i) => (
                                    <div key={i} className="skeleton h-20 w-full" />
                                ))}
                            </div>
                        ) : (
                            <AuditTrail entries={entries} chainValid={chainValid} />
                        )}
                    </div>

                    {/* Right — Verification Panel */}
                    <motion.div
                        initial={{ opacity: 0, x: 20 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ delay: 0.2 }}
                        className="space-y-5"
                    >
                        {/* Merkle Root */}
                        <div className="rounded-xl border border-[#2a2a3d] bg-[#1a1a28] p-6">
                            <div className="mb-4 flex items-center gap-2">
                                <GitBranch className="h-5 w-5 text-emerald-400" />
                                <h3 className="font-semibold text-white">🌳 Merkle Root</h3>
                            </div>

                            {merkle ? (
                                <div className="space-y-3 text-sm">
                                    <div>
                                        <span className="text-gray-400">Root:</span>
                                        <p className="mt-0.5 break-all font-mono text-xs text-gray-300">
                                            {truncateHash(merkle.merkle_root, 20)}
                                        </p>
                                    </div>
                                    <div className="flex items-center justify-between">
                                        <span className="text-gray-400">Leaves</span>
                                        <span className="text-gray-200">{merkle.leaf_count}</span>
                                    </div>

                                    {/* On-Chain Anchor */}
                                    <div className="mt-4 border-t border-[#2a2a3d] pt-4">
                                        <div className="mb-3 flex items-center gap-2">
                                            <ShieldCheck className="h-4 w-4 text-indigo-400" />
                                            <span className="text-sm font-semibold text-white">
                                                ⛓️ On-Chain Anchor
                                            </span>
                                        </div>

                                        {merkle.anchored_on_chain ? (
                                            <div className="space-y-2">
                                                {merkle.anchor_tx_id && (
                                                    <div>
                                                        <span className="text-xs text-gray-400">
                                                            tx_id:
                                                        </span>
                                                        <a
                                                            href={explorerTxUrl(merkle.anchor_tx_id)}
                                                            target="_blank"
                                                            rel="noopener noreferrer"
                                                            className="mt-0.5 flex items-center gap-1 font-mono text-xs text-indigo-400 hover:text-indigo-300"
                                                        >
                                                            {truncateHash(merkle.anchor_tx_id, 14)}
                                                            <ExternalLink className="h-3 w-3" />
                                                        </a>
                                                    </div>
                                                )}
                                                <div className="rounded-lg bg-emerald-500/10 px-3 py-2">
                                                    <span className="text-xs font-semibold text-emerald-400">
                                                        ✓ ANCHORED
                                                    </span>
                                                </div>
                                            </div>
                                        ) : (
                                            <div className="flex items-center gap-2 rounded-lg bg-amber-500/10 px-3 py-2">
                                                <Loader2 className="h-3 w-3 animate-spin text-amber-400" />
                                                <span className="text-xs text-amber-400">
                                                    Waiting for anchor...
                                                </span>
                                            </div>
                                        )}
                                    </div>

                                    <p className="mt-4 text-xs text-gray-500">
                                        This session&apos;s audit trail is permanently recorded on
                                        Algorand. Anyone can verify it.
                                    </p>
                                </div>
                            ) : isLoading ? (
                                <div className="skeleton h-32 w-full" />
                            ) : (
                                <p className="text-sm text-gray-500">
                                    Merkle data not available
                                </p>
                            )}
                        </div>

                        {/* Session Summary */}
                        <div className="rounded-xl border border-[#2a2a3d] bg-[#1a1a28] p-6">
                            <div className="mb-4 flex items-center gap-2">
                                <BarChart3 className="h-5 w-5 text-indigo-400" />
                                <h3 className="font-semibold text-white">
                                    📊 Session Summary
                                </h3>
                            </div>

                            {session ? (
                                <div className="space-y-3 text-sm">
                                    <SummaryRow
                                        label="Final Price"
                                        value={
                                            session.final_agreed_value
                                                ? formatINR(session.final_agreed_value)
                                                : "—"
                                        }
                                        highlight
                                    />
                                    <SummaryRow
                                        label="Rounds"
                                        value={String(session.current_round || 0)}
                                    />
                                    <SummaryRow label="Protocol" value="DANP-v1" />
                                    <SummaryRow label="Settlement" value="x402-algorand" />
                                    <SummaryRow label="Human input" value="ZERO" />
                                </div>
                            ) : (
                                <div className="skeleton h-32 w-full" />
                            )}
                        </div>
                    </motion.div>
                </div>
            </div>
        </div>
    );
}

function SummaryRow({
    label,
    value,
    highlight,
}: {
    label: string;
    value: string;
    highlight?: boolean;
}) {
    return (
        <div className="flex items-center justify-between">
            <span className="text-gray-400">{label}</span>
            <span
                className={`font-semibold ${highlight ? "text-emerald-400" : "text-white"
                    }`}
            >
                {value}
            </span>
        </div>
    );
}
