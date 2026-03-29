"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { motion } from "framer-motion";
import Navbar from "@/components/Navbar";
import NegotiationFeed from "@/components/NegotiationFeed";
import StatusBadge from "@/components/StatusBadge";
import { useSession } from "@/hooks/useSession";
import { formatINR, truncateHash } from "@/lib/utils";
import type { AuthState } from "@/lib/types";
import {
    ArrowRight,
    Loader2,
    PartyPopper,
    Clock,
    Layers,
} from "lucide-react";

export default function NegotiationPage() {
    const params = useParams();
    const router = useRouter();
    const sessionId = params.sessionId as string;

    const [auth, setAuth] = useState<AuthState | null>(null);

    const { session, rounds, isLoading, isTerminal } = useSession(sessionId);

    useEffect(() => {
        const raw = localStorage.getItem("acf_auth");
        if (!raw) {
            router.push("/register");
            return;
        }
        setAuth(JSON.parse(raw));
    }, [router]);

    if (!auth) return null;

    const isAgreed = session?.status === "AGREED";
    const isBreach = session?.status === "POLICY_BREACH";
    const isStalled = session?.status === "STALLED";
    const isActive = session?.status === "ACTIVE" || session?.status === "IN_PROGRESS";

    return (
        <div className="min-h-screen">
            <Navbar />

            <div className="mx-auto max-w-7xl px-6 py-8">
                {/* Top bar */}
                <motion.div
                    initial={{ opacity: 0, y: -10 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="mb-8 rounded-xl border border-[#2a2a3d] bg-[#1a1a28] p-6"
                >
                    <div className="flex flex-wrap items-center justify-between gap-4">
                        <div>
                            <h1 className="text-2xl font-bold text-white">
                                🤝 Negotiation Room
                            </h1>
                            <p className="mt-1 text-sm text-gray-400">
                                Session:{" "}
                                <span className="font-mono text-gray-300">
                                    {truncateHash(sessionId, 10)}
                                </span>
                                {" "}· Protocol:{" "}
                                <span className="text-indigo-400">DANP-v1</span>
                            </p>
                        </div>
                        {session && (
                            <StatusBadge
                                status={session.status}
                                size="md"
                                pulse={isActive}
                            />
                        )}
                    </div>
                </motion.div>

                <div className="grid grid-cols-1 gap-6 lg:grid-cols-4">
                    {/* Main feed */}
                    <div className="lg:col-span-3">
                        {/* Loading */}
                        {isLoading && rounds.length === 0 && (
                            <div className="flex flex-col items-center justify-center py-20">
                                <Loader2 className="mb-4 h-8 w-8 animate-spin text-indigo-400" />
                                <p className="text-gray-400">Waiting for negotiation data...</p>
                            </div>
                        )}

                        {/* Rounds Feed */}
                        {rounds.length > 0 && <NegotiationFeed rounds={rounds} />}

                        {/* Thinking indicator */}
                        {isActive && !isLoading && (
                            <motion.div
                                initial={{ opacity: 0 }}
                                animate={{ opacity: 1 }}
                                className="mt-6 flex items-center gap-3 rounded-xl border border-indigo-500/20 bg-indigo-500/5 px-5 py-4"
                            >
                                <div className="flex gap-1">
                                    <span className="inline-block h-2 w-2 animate-bounce rounded-full bg-indigo-400 [animation-delay:0s]" />
                                    <span className="inline-block h-2 w-2 animate-bounce rounded-full bg-indigo-400 [animation-delay:0.15s]" />
                                    <span className="inline-block h-2 w-2 animate-bounce rounded-full bg-indigo-400 [animation-delay:0.3s]" />
                                </div>
                                <span className="text-sm text-indigo-300">
                                    🤖 Agent thinking...
                                </span>
                            </motion.div>
                        )}

                        {/* ── AGREED ─────────────────────────────────────────── */}
                        {isAgreed && (
                            <motion.div
                                initial={{ opacity: 0, scale: 0.95 }}
                                animate={{ opacity: 1, scale: 1 }}
                                transition={{ duration: 0.5 }}
                                className="mt-8 rounded-xl border border-emerald-500/30 bg-gradient-to-br from-emerald-500/10 to-emerald-500/5 p-8 text-center"
                            >
                                <PartyPopper className="mx-auto mb-4 h-12 w-12 text-emerald-400" />
                                <h2 className="mb-2 text-3xl font-bold text-white">
                                    🎉 DEAL AGREED
                                </h2>
                                <div className="mx-auto mt-6 max-w-sm space-y-3 text-left">
                                    <AgreedRow
                                        label="Final Price"
                                        value={
                                            session?.final_agreed_value
                                                ? formatINR(session.final_agreed_value)
                                                : "—"
                                        }
                                        highlight
                                    />
                                    <AgreedRow
                                        label="Rounds"
                                        value={String(session?.current_round || rounds.length)}
                                    />
                                    <AgreedRow label="Protocol" value="DANP-v1" />
                                    <AgreedRow label="Human input" value="ZERO" />
                                </div>
                                <button
                                    onClick={() =>
                                        router.push(`/settlement/${sessionId}`)
                                    }
                                    className="mt-8 inline-flex items-center gap-2 rounded-lg bg-indigo-500 px-8 py-3 font-semibold text-white shadow-lg shadow-indigo-500/20 transition-all hover:bg-indigo-400"
                                >
                                    Proceed to Settlement
                                    <ArrowRight className="h-4 w-4" />
                                </button>
                            </motion.div>
                        )}

                        {/* ── BREACH / STALLED ───────────────────────────────── */}
                        {(isBreach || isStalled) && (
                            <motion.div
                                initial={{ opacity: 0 }}
                                animate={{ opacity: 1 }}
                                className={`mt-8 rounded-xl border p-8 text-center ${isBreach
                                        ? "border-red-500/30 bg-red-500/10"
                                        : "border-gray-500/30 bg-gray-500/10"
                                    }`}
                            >
                                <h2 className="text-2xl font-bold text-white">
                                    {isBreach
                                        ? "⚠️ Policy Breach Detected"
                                        : "⏸️ Negotiation Stalled"}
                                </h2>
                                <p className="mt-2 text-gray-400">
                                    {isBreach
                                        ? "The negotiation violated policy constraints and was terminated."
                                        : "Agents could not reach agreement within the maximum rounds."}
                                </p>
                            </motion.div>
                        )}
                    </div>

                    {/* Sidebar */}
                    <motion.div
                        initial={{ opacity: 0, x: 20 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ delay: 0.2 }}
                        className="space-y-5"
                    >
                        {/* Session Info */}
                        <div className="rounded-xl border border-[#2a2a3d] bg-[#1a1a28] p-5">
                            <h3 className="mb-4 text-sm font-semibold uppercase tracking-wider text-gray-400">
                                Session Info
                            </h3>
                            <div className="space-y-3 text-sm">
                                <SidebarRow
                                    icon={<Layers className="h-4 w-4 text-gray-500" />}
                                    label="ID"
                                    value={truncateHash(sessionId, 8)}
                                    mono
                                />
                                <SidebarRow
                                    icon={<Clock className="h-4 w-4 text-gray-500" />}
                                    label="Timeout"
                                    value={
                                        session?.timeout_at
                                            ? new Date(session.timeout_at).toLocaleTimeString()
                                            : "—"
                                    }
                                />
                                <SidebarRow
                                    label="Round"
                                    value={`${session?.current_round || 0} / ${session?.max_rounds || 8}`}
                                />
                                <SidebarRow
                                    label="Status"
                                    value={session?.status || "LOADING"}
                                />
                                <SidebarRow
                                    label="Terminal"
                                    value={session?.is_terminal ? "Yes" : "No"}
                                />
                            </div>
                        </div>

                        {/* Framework */}
                        <div className="rounded-xl border border-[#2a2a3d] bg-[#1a1a28] p-5">
                            <h3 className="mb-4 text-sm font-semibold uppercase tracking-wider text-gray-400">
                                Framework
                            </h3>
                            <div className="space-y-3 text-sm">
                                <SidebarRow label="Protocol" value="DANP-v1" />
                                <SidebarRow label="Settlement" value="x402-algorand" />
                                <SidebarRow label="Escrow" value="Required ✓" />
                            </div>
                        </div>

                        {/* Settlement CTA (when agreed) */}
                        {isTerminal && isAgreed && (
                            <button
                                onClick={() =>
                                    router.push(`/settlement/${sessionId}`)
                                }
                                className="flex w-full items-center justify-center gap-2 rounded-xl bg-indigo-500 px-4 py-3 text-sm font-semibold text-white transition-all hover:bg-indigo-400"
                            >
                                Settlement
                                <ArrowRight className="h-4 w-4" />
                            </button>
                        )}
                    </motion.div>
                </div>
            </div>
        </div>
    );
}

function AgreedRow({
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
            <span className="text-sm text-gray-400">{label}</span>
            <span
                className={`font-semibold ${highlight ? "text-xl text-emerald-400" : "text-white"
                    }`}
            >
                {value}
            </span>
        </div>
    );
}

function SidebarRow({
    icon,
    label,
    value,
    mono,
}: {
    icon?: React.ReactNode;
    label: string;
    value: string;
    mono?: boolean;
}) {
    return (
        <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-gray-400">
                {icon}
                <span>{label}</span>
            </div>
            <span
                className={`text-gray-200 ${mono ? "font-mono text-xs" : ""}`}
            >
                {value}
            </span>
        </div>
    );
}
