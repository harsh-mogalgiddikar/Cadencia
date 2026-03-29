"use client";

import type { EscrowData } from "@/lib/types";
import { formatINR, truncateHash, explorerAccountUrl } from "@/lib/utils";
import StatusBadge from "./StatusBadge";
import { Lock, ExternalLink } from "lucide-react";

interface EscrowStatusProps {
    escrow: EscrowData;
}

export default function EscrowStatus({ escrow }: EscrowStatusProps) {
    return (
        <div className="rounded-xl border border-[#2a2a3d] bg-[#1a1a28] p-6">
            <div className="mb-5 flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-amber-500/20">
                    <Lock className="h-5 w-5 text-amber-400" />
                </div>
                <div>
                    <h3 className="text-lg font-semibold text-white">Algorand Escrow</h3>
                    <p className="text-sm text-gray-400">{escrow.network || "Algorand Testnet"}</p>
                </div>
            </div>

            <div className="space-y-4">
                {/* Address */}
                <div className="flex items-center justify-between">
                    <span className="text-sm text-gray-400">Address</span>
                    <a
                        href={explorerAccountUrl(escrow.escrow_address)}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex items-center gap-1.5 font-mono text-sm text-indigo-400 hover:text-indigo-300"
                    >
                        {truncateHash(escrow.escrow_address, 10)}
                        <ExternalLink className="h-3 w-3" />
                    </a>
                </div>

                {/* Amount */}
                <div className="flex items-center justify-between">
                    <span className="text-sm text-gray-400">Amount</span>
                    <span className="text-lg font-bold text-white">
                        {formatINR(escrow.amount_inr)}
                    </span>
                </div>

                {/* Status */}
                <div className="flex items-center justify-between">
                    <span className="text-sm text-gray-400">Status</span>
                    <StatusBadge status={escrow.status} />
                </div>

                {/* Buyer */}
                <div className="flex items-center justify-between">
                    <span className="text-sm text-gray-400">Buyer</span>
                    <a
                        href={explorerAccountUrl(escrow.buyer_address)}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex items-center gap-1.5 font-mono text-xs text-gray-300 hover:text-indigo-400"
                    >
                        {truncateHash(escrow.buyer_address, 8)}
                        <ExternalLink className="h-3 w-3" />
                    </a>
                </div>

                {/* Seller */}
                <div className="flex items-center justify-between">
                    <span className="text-sm text-gray-400">Seller</span>
                    <a
                        href={explorerAccountUrl(escrow.seller_address)}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex items-center gap-1.5 font-mono text-xs text-gray-300 hover:text-indigo-400"
                    >
                        {truncateHash(escrow.seller_address, 8)}
                        <ExternalLink className="h-3 w-3" />
                    </a>
                </div>
            </div>
        </div>
    );
}
