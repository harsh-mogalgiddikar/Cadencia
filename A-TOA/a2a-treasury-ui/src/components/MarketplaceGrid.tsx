"use client";

import { motion } from "framer-motion";
import type { RegistryAgent, AuthState } from "@/lib/types";
import StatusBadge from "./StatusBadge";
import { timeAgo } from "@/lib/utils";
import { Building2, ArrowRight } from "lucide-react";

interface MarketplaceGridProps {
    agents: RegistryAgent[];
    currentAuth: AuthState | null;
    onStartNegotiation: (agent: RegistryAgent) => void;
}

export default function MarketplaceGrid({
    agents,
    currentAuth,
    onStartNegotiation,
}: MarketplaceGridProps) {
    // Filter out current user's own enterprise
    const filtered = agents.filter(
        (a) => a.enterprise_id !== currentAuth?.enterprise_id
    );

    if (filtered.length === 0) {
        return (
            <div className="flex flex-col items-center justify-center rounded-xl border border-[#2a2a3d] bg-[#1a1a28] p-16 text-center">
                <Building2 className="mb-4 h-12 w-12 text-gray-600" />
                <h3 className="text-lg font-semibold text-gray-300">
                    No agents found
                </h3>
                <p className="mt-2 text-sm text-gray-500">
                    Register more enterprises to see them appear here.
                </p>
            </div>
        );
    }

    return (
        <div className="grid grid-cols-1 gap-5 md:grid-cols-2 lg:grid-cols-3">
            {filtered.map((agent, i) => (
                <motion.div
                    key={agent.enterprise_id}
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: i * 0.08, duration: 0.3 }}
                    className="group rounded-xl border border-[#2a2a3d] bg-[#1a1a28] p-6 transition-all hover:border-indigo-500/40 hover:shadow-lg hover:shadow-indigo-500/5"
                >
                    {/* Header */}
                    <div className="mb-4 flex items-start justify-between">
                        <div className="flex items-center gap-3">
                            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-indigo-500/20">
                                <Building2 className="h-5 w-5 text-indigo-400" />
                            </div>
                            <h3 className="text-base font-semibold text-white">
                                {agent.legal_name}
                            </h3>
                        </div>
                        <StatusBadge status={agent.availability || "active"} />
                    </div>

                    {/* Tags */}
                    <div className="mb-4 flex flex-wrap gap-1.5">
                        {agent.service_tags?.map((tag) => (
                            <span
                                key={tag}
                                className="rounded-md bg-white/5 px-2 py-0.5 text-xs text-gray-400"
                            >
                                {tag}
                            </span>
                        ))}
                    </div>

                    {/* Details */}
                    <div className="mb-5 space-y-2 text-sm">
                        <Row label="Protocol" value={agent.protocol || "DANP-v1"} />
                        <Row
                            label="Network"
                            value={agent.settlement_network || "algorand-testnet"}
                        />
                        <Row label="Payment" value={agent.payment_method || "x402"} />
                        {agent.registered_at && (
                            <Row label="Registered" value={timeAgo(agent.registered_at)} />
                        )}
                    </div>

                    {/* CTA */}
                    <button
                        onClick={() => onStartNegotiation(agent)}
                        className="flex w-full items-center justify-center gap-2 rounded-lg bg-indigo-500 px-4 py-2.5 text-sm font-semibold text-white transition-all hover:bg-indigo-400 active:scale-[0.98]"
                    >
                        {currentAuth?.role === "seller"
                            ? "Accept Negotiation"
                            : "Start Negotiation"}
                        <ArrowRight className="h-4 w-4" />
                    </button>
                </motion.div>
            ))}
        </div>
    );
}

function Row({ label, value }: { label: string; value: string }) {
    return (
        <div className="flex items-center justify-between">
            <span className="text-gray-500">{label}</span>
            <span className="font-mono text-xs text-gray-300">{value}</span>
        </div>
    );
}
