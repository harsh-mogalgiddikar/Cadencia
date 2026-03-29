"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import type { AuditEntry } from "@/lib/types";
import { truncateHash } from "@/lib/utils";
import { ChevronDown, ChevronRight } from "lucide-react";

interface AuditTrailProps {
    entries: AuditEntry[];
    chainValid: boolean | null;
}

const actionIcons: Record<string, string> = {
    SESSION_CREATED: "🚀",
    CAPABILITY_HANDSHAKE: "🤝",
    OFFER_SUBMITTED: "💬",
    SESSION_AGREED: "✅",
    ESCROW_DEPLOYED: "🔒",
    ESCROW_FUNDED: "💳",
    X402_PAYMENT_VERIFIED: "💰",
    X402_CHALLENGE_ISSUED: "🔑",
    DELIVERY_CONFIRMED: "📦",
    MERKLE_ROOT_COMPUTED: "🌳",
    AUDIT_ANCHORED_ON_CHAIN: "⛓️",
};

export default function AuditTrail({ entries, chainValid }: AuditTrailProps) {
    return (
        <div>
            {/* Header */}
            <div className="mb-6 flex items-center gap-3">
                {chainValid !== null && (
                    <span
                        className={`rounded-lg px-3 py-1 text-sm font-medium ${chainValid
                                ? "bg-emerald-500/20 text-emerald-400"
                                : "bg-red-500/20 text-red-400"
                            }`}
                    >
                        {chainValid ? "✓ Audit Chain Verified" : "✗ Chain Invalid"}
                    </span>
                )}
                <span className="text-sm text-gray-400">
                    {entries.length} entries · SHA-256 · Tamper-evident
                </span>
            </div>

            {/* Entries */}
            <div className="space-y-3">
                {entries.map((entry, i) => (
                    <AuditEntryCard key={entry.sequence ?? i} entry={entry} index={i} />
                ))}
            </div>
        </div>
    );
}

function AuditEntryCard({
    entry,
    index,
}: {
    entry: AuditEntry;
    index: number;
}) {
    const [expanded, setExpanded] = useState(false);
    const icon = actionIcons[entry.action] || "📋";

    return (
        <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: index * 0.03, duration: 0.2 }}
            className="rounded-xl border border-[#2a2a3d] bg-[#1a1a28] p-4"
        >
            <button
                onClick={() => setExpanded(!expanded)}
                className="flex w-full items-center justify-between text-left"
            >
                <div className="flex items-center gap-3">
                    <span className="text-lg">{icon}</span>
                    <div>
                        <div className="flex items-center gap-2">
                            <span className="text-xs font-bold text-gray-500">
                                #{entry.sequence}
                            </span>
                            <span className="text-sm font-semibold text-white">
                                {entry.action}
                            </span>
                        </div>
                        <div className="flex items-center gap-2 text-xs text-gray-500">
                            <span>{entry.actor_id}</span>
                            <span>·</span>
                            <span>
                                {entry.timestamp
                                    ? new Date(entry.timestamp).toLocaleTimeString()
                                    : ""}
                            </span>
                        </div>
                    </div>
                </div>
                <div className="flex items-center gap-3">
                    <span className="font-mono text-xs text-gray-500">
                        {truncateHash(entry.this_hash, 8)}
                    </span>
                    {expanded ? (
                        <ChevronDown className="h-4 w-4 text-gray-500" />
                    ) : (
                        <ChevronRight className="h-4 w-4 text-gray-500" />
                    )}
                </div>
            </button>

            {expanded && (
                <motion.div
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: "auto", opacity: 1 }}
                    className="mt-3 overflow-hidden"
                >
                    <div className="rounded-lg bg-[#12121a] p-4">
                        <pre className="overflow-x-auto whitespace-pre-wrap text-xs text-gray-400">
                            {JSON.stringify(entry.payload, null, 2)}
                        </pre>
                        <div className="mt-3 space-y-1 border-t border-[#2a2a3d] pt-3 text-xs text-gray-500">
                            <div>
                                <span className="text-gray-400">This hash: </span>
                                <span className="font-mono">{entry.this_hash}</span>
                            </div>
                            <div>
                                <span className="text-gray-400">Prev hash: </span>
                                <span className="font-mono">{entry.prev_hash}</span>
                            </div>
                        </div>
                    </div>
                </motion.div>
            )}
        </motion.div>
    );
}
