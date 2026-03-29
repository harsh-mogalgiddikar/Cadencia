"use client";

import { motion } from "framer-motion";
import type { NegotiationRound } from "@/lib/types";
import { formatINR } from "@/lib/utils";

interface NegotiationFeedProps {
    rounds: NegotiationRound[];
}

export default function NegotiationFeed({ rounds }: NegotiationFeedProps) {
    // Group rounds by round_number
    const grouped = rounds.reduce<Record<number, NegotiationRound[]>>(
        (acc, r) => {
            if (!acc[r.round_number]) acc[r.round_number] = [];
            acc[r.round_number].push(r);
            return acc;
        },
        {}
    );

    const roundNumbers = Object.keys(grouped)
        .map(Number)
        .sort((a, b) => a - b);

    return (
        <div className="space-y-6">
            {roundNumbers.map((num) => (
                <div key={num}>
                    <div className="mb-3 flex items-center gap-2">
                        <span className="flex h-6 w-6 items-center justify-center rounded-full bg-white/10 text-xs font-bold text-white">
                            {num}
                        </span>
                        <span className="text-sm font-medium text-gray-400">
                            Round {num}
                        </span>
                    </div>
                    <div className="space-y-3">
                        {grouped[num].map((round, i) => (
                            <RoundCard key={`${num}-${i}`} round={round} />
                        ))}
                    </div>
                </div>
            ))}
        </div>
    );
}

function RoundCard({ round }: { round: NegotiationRound }) {
    const isBuyer = round.actor === "buyer";
    const isAccept = round.action === "ACCEPT";

    return (
        <motion.div
            initial={{ opacity: 0, x: isBuyer ? -20 : 20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.3, ease: "easeOut" }}
            className={`rounded-xl border p-4 ${isAccept
                    ? "border-emerald-500/30 bg-emerald-500/10"
                    : isBuyer
                        ? "border-blue-500/30 bg-blue-500/10"
                        : "border-purple-500/30 bg-purple-500/10"
                }`}
        >
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                    <span
                        className={`flex h-8 w-8 items-center justify-center rounded-full text-sm font-bold ${isBuyer
                                ? "bg-blue-500/20 text-blue-400"
                                : "bg-purple-500/20 text-purple-400"
                            }`}
                    >
                        {isBuyer ? "B" : "S"}
                    </span>
                    <div>
                        <span
                            className={`text-sm font-semibold uppercase ${isBuyer ? "text-blue-400" : "text-purple-400"
                                }`}
                        >
                            {round.actor}
                        </span>
                        {round.offer_amount > 0 && (
                            <p className="text-lg font-bold text-white">
                                {formatINR(round.offer_amount)}
                            </p>
                        )}
                    </div>
                </div>
                <span
                    className={`rounded-lg px-3 py-1 text-xs font-bold uppercase ${isAccept
                            ? "bg-emerald-500/20 text-emerald-400"
                            : "bg-white/10 text-gray-300"
                        }`}
                >
                    {isAccept ? "ACCEPTS ✓" : round.action}
                </span>
            </div>
            {round.timestamp && (
                <p className="mt-2 text-xs text-gray-500">
                    {new Date(round.timestamp).toLocaleTimeString()}
                </p>
            )}
        </motion.div>
    );
}
