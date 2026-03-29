"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { toast } from "sonner";
import Navbar from "@/components/Navbar";
import MarketplaceGrid from "@/components/MarketplaceGrid";
import {
    queryRegistry,
    performHandshake,
    createSession,
    runNegotiation,
} from "@/lib/api";
import type { AuthState, RegistryAgent } from "@/lib/types";
import { formatINR, extractApiError } from "@/lib/utils";
import { Search, Loader2, X, AlertTriangle, Zap } from "lucide-react";

export default function MarketplacePage() {
    const router = useRouter();
    const [auth, setAuth] = useState<AuthState | null>(null);
    const [agents, setAgents] = useState<RegistryAgent[]>([]);
    const [loading, setLoading] = useState(true);
    const [modalAgent, setModalAgent] = useState<RegistryAgent | null>(null);
    const [negotiating, setNegotiating] = useState(false);

    // Filters
    const [service, setService] = useState("cotton");
    const [protocol, setProtocol] = useState("DANP-v1");
    const [network, setNetwork] = useState("algorand-testnet");

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
        fetchAgents();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [auth]);

    const fetchAgents = async () => {
        setLoading(true);
        try {
            const res = await queryRegistry({
                service: service || undefined,
                protocol: protocol || undefined,
                network: network || undefined,
                availability: "active",
            });
            const data = res.data?.agents || res.data || [];
            setAgents(Array.isArray(data) ? data : []);
        } catch {
            toast.error("Failed to fetch agents");
        } finally {
            setLoading(false);
        }
    };

    const handleStartNegotiation = async () => {
        if (!auth || !modalAgent) return;
        setNegotiating(true);

        try {
            // Backend always derives buyer from JWT (the logged-in user).
            // seller_enterprise_id must be the OTHER party.
            const sellerIdForSession = modalAgent.enterprise_id;

            // Step 1: Handshake
            toast.info("🤝 Performing capability handshake...");
            try {
                await performHandshake(auth.enterprise_id, sellerIdForSession);
            } catch {
                // Handshake may fail if not implemented — non-blocking
                toast.info("Handshake skipped (not required for demo)");
            }

            // Step 2: Create session
            // Backend: buyer = JWT holder, seller = body.seller_enterprise_id
            toast.info("📝 Creating negotiation session...");
            const sessionRes = await createSession({
                seller_enterprise_id: sellerIdForSession,
                initial_offer_value: 85000,
                max_rounds: 8,
                timeout_seconds: 3600,
            });
            const sessionId =
                sessionRes.data?.session_id || sessionRes.data?.id;

            // Step 3: Run negotiations
            toast.info("🤖 Starting autonomous negotiation...");
            await runNegotiation(sessionId);

            toast.success("Negotiation started! Redirecting...");
            router.push(`/negotiate/${sessionId}`);
        } catch (err: unknown) {
            toast.error(extractApiError(err, "Failed to start negotiation"));
        } finally {
            setNegotiating(false);
            setModalAgent(null);
        }
    };

    if (!auth) return null;

    return (
        <div className="min-h-screen">
            <Navbar />

            <div className="mx-auto max-w-7xl px-6 py-8">
                {/* Header */}
                <motion.div
                    initial={{ opacity: 0, y: -10 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="mb-8"
                >
                    <h1 className="text-3xl font-bold tracking-tight text-white">
                        🏪 ACF Marketplace
                    </h1>
                    <p className="mt-1 text-gray-400">
                        Active Trading Agents · Cotton & Textiles
                    </p>
                </motion.div>

                {/* Filters */}
                <div className="mb-8 flex flex-wrap items-center gap-3">
                    <FilterChip
                        icon={<Search className="h-3.5 w-3.5" />}
                        label="Service"
                        value={service}
                        onChange={setService}
                    />
                    <FilterChip label="Protocol" value={protocol} onChange={setProtocol} />
                    <FilterChip label="Network" value={network} onChange={setNetwork} />
                    <button
                        onClick={fetchAgents}
                        className="rounded-lg bg-indigo-500/20 px-4 py-2 text-sm font-medium text-indigo-400 transition-colors hover:bg-indigo-500/30"
                    >
                        Apply Filters
                    </button>
                </div>

                {/* Grid */}
                {loading ? (
                    <div className="grid grid-cols-1 gap-5 md:grid-cols-2 lg:grid-cols-3">
                        {[1, 2, 3].map((i) => (
                            <div key={i} className="skeleton h-80 w-full" />
                        ))}
                    </div>
                ) : (
                    <MarketplaceGrid
                        agents={agents}
                        currentAuth={auth}
                        onStartNegotiation={(agent) => setModalAgent(agent)}
                    />
                )}
            </div>

            {/* Confirmation Modal */}
            {modalAgent && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
                    <motion.div
                        initial={{ opacity: 0, scale: 0.95 }}
                        animate={{ opacity: 1, scale: 1 }}
                        className="mx-4 w-full max-w-lg rounded-2xl border border-[#2a2a3d] bg-[#12121a] p-8"
                    >
                        <div className="mb-6 flex items-start justify-between">
                            <h2 className="text-xl font-bold text-white">
                                Ready to negotiate?
                            </h2>
                            <button
                                onClick={() => setModalAgent(null)}
                                className="rounded-lg p-1 text-gray-500 hover:text-white"
                            >
                                <X className="h-5 w-5" />
                            </button>
                        </div>

                        <div className="mb-6 space-y-3">
                            <ModalRow label="Counterparty" value={modalAgent.legal_name} />
                            <ModalRow label="Commodity" value="Cotton" />
                            <ModalRow
                                label="Opening offer"
                                value={formatINR(85000)}
                            />
                            <ModalRow label="Protocol" value="DANP-v1 (autonomous)" />
                        </div>

                        <div className="mb-6 flex items-start gap-2.5 rounded-lg border border-amber-500/20 bg-amber-500/10 p-4">
                            <AlertTriangle className="mt-0.5 h-4 w-4 flex-shrink-0 text-amber-400" />
                            <p className="text-sm text-amber-300">
                                Once started, your AI agent will negotiate completely
                                autonomously. No human input required.
                            </p>
                        </div>

                        <div className="flex gap-3">
                            <button
                                onClick={() => setModalAgent(null)}
                                disabled={negotiating}
                                className="flex-1 rounded-lg border border-[#2a2a3d] bg-[#1a1a28] px-4 py-3 text-sm font-medium text-gray-300 transition-colors hover:bg-[#2a2a3d]"
                            >
                                Cancel
                            </button>
                            <button
                                onClick={handleStartNegotiation}
                                disabled={negotiating}
                                className="flex flex-1 items-center justify-center gap-2 rounded-lg bg-indigo-500 px-4 py-3 text-sm font-semibold text-white transition-all hover:bg-indigo-400 disabled:opacity-50"
                            >
                                {negotiating ? (
                                    <Loader2 className="h-4 w-4 animate-spin" />
                                ) : (
                                    <>
                                        <Zap className="h-4 w-4" />
                                        Start Autonomous Negotiation
                                    </>
                                )}
                            </button>
                        </div>
                    </motion.div>
                </div>
            )}
        </div>
    );
}

function FilterChip({
    icon,
    label,
    value,
    onChange,
}: {
    icon?: React.ReactNode;
    label: string;
    value: string;
    onChange: (v: string) => void;
}) {
    return (
        <div className="flex items-center gap-1.5 rounded-lg border border-[#2a2a3d] bg-[#1a1a28] px-3 py-1.5">
            {icon}
            <span className="text-xs text-gray-500">{label}:</span>
            <input
                type="text"
                value={value}
                onChange={(e) => onChange(e.target.value)}
                className="w-24 bg-transparent text-xs font-medium text-white outline-none placeholder-gray-600"
            />
        </div>
    );
}

function ModalRow({ label, value }: { label: string; value: string }) {
    return (
        <div className="flex items-center justify-between text-sm">
            <span className="text-gray-400">{label}</span>
            <span className="font-medium text-white">{value}</span>
        </div>
    );
}
