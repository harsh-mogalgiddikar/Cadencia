"use client";

import type { AgentCard as AgentCardType } from "@/lib/types";
import { formatINR } from "@/lib/utils";
import StatusBadge from "./StatusBadge";
import { Bot, Shield, Landmark, FileCheck } from "lucide-react";

interface AgentCardProps {
    card: AgentCardType;
    legalName: string;
}

export default function AgentCard({ card, legalName }: AgentCardProps) {
    return (
        <div className="rounded-xl border border-[#2a2a3d] bg-[#1a1a28] p-6">
            {/* Header */}
            <div className="mb-5 flex items-start justify-between">
                <div className="flex items-center gap-3">
                    <div className="flex h-11 w-11 items-center justify-center rounded-lg bg-indigo-500/20">
                        <Bot className="h-6 w-6 text-indigo-400" />
                    </div>
                    <div>
                        <h3 className="text-lg font-semibold text-white">Your AI Agent</h3>
                        <p className="text-sm text-gray-400">{legalName} Agent</p>
                    </div>
                </div>
                <StatusBadge status={card.role} size="md" pulse={false} />
            </div>

            {/* Protocol & Settlement */}
            <div className="mb-5 space-y-3">
                <InfoRow
                    icon={<FileCheck className="h-4 w-4 text-indigo-400" />}
                    label="Protocol"
                    value={card.protocols?.[0]?.id || "DANP-v1"}
                />
                <InfoRow
                    icon={<Landmark className="h-4 w-4 text-emerald-400" />}
                    label="Settlement"
                    value={card.settlement_networks?.[0] || "x402-algorand-testnet"}
                />
                <InfoRow
                    icon={<Shield className="h-4 w-4 text-amber-400" />}
                    label="Payment"
                    value={card.payment_methods?.[0] || "x402"}
                />
            </div>

            {/* Divider */}
            <div className="mb-5 border-t border-[#2a2a3d]" />

            {/* Policy Constraints */}
            <div className="mb-4">
                <h4 className="mb-3 text-sm font-semibold uppercase tracking-wider text-gray-400">
                    Policy Constraints
                </h4>
                <div className="space-y-2">
                    {card.policy_constraints?.max_transaction_inr && (
                        <div className="flex items-center justify-between text-sm">
                            <span className="text-gray-400">Budget Ceiling</span>
                            <span className="font-mono font-medium text-white">
                                {formatINR(card.policy_constraints.max_transaction_inr)}
                            </span>
                        </div>
                    )}
                    <div className="flex items-center justify-between text-sm">
                        <span className="text-gray-400">Requires Escrow</span>
                        <span className="font-medium text-emerald-400">
                            {card.policy_constraints?.requires_escrow ? "✓ Yes" : "✗ No"}
                        </span>
                    </div>
                    {card.policy_constraints?.compliance_frameworks?.length > 0 && (
                        <div className="flex items-center justify-between text-sm">
                            <span className="text-gray-400">Compliance</span>
                            <span className="font-medium text-white">
                                {card.policy_constraints.compliance_frameworks.join(" · ")}
                            </span>
                        </div>
                    )}
                </div>
            </div>

            {/* Framework */}
            <div className="rounded-lg bg-[#12121a] px-4 py-3">
                <div className="flex items-center justify-between text-sm">
                    <span className="text-gray-400">Framework</span>
                    <span className="font-medium text-white">
                        {card.framework?.name || "ACF"} {card.framework?.version || "v1.0.0"}
                    </span>
                </div>
            </div>
        </div>
    );
}

function InfoRow({
    icon,
    label,
    value,
}: {
    icon: React.ReactNode;
    label: string;
    value: string;
}) {
    return (
        <div className="flex items-center gap-3 text-sm">
            {icon}
            <span className="text-gray-400">{label}:</span>
            <span className="font-mono font-medium text-white">{value}</span>
        </div>
    );
}
