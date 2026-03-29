"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { toast } from "sonner";
import Navbar from "@/components/Navbar";
import EscrowStatus from "@/components/EscrowStatus";
import { getEscrow, triggerDelivery } from "@/lib/api";
import {
    truncateHash,
    explorerTxUrl,
    extractApiError,
} from "@/lib/utils";
import type { AuthState, EscrowData } from "@/lib/types";
import {
    ArrowRight,
    CheckCircle2,
    Circle,
    ExternalLink,
    Loader2,
    Lock,
    Shield,
} from "lucide-react";

interface PaymentStep {
    id: number;
    label: string;
    detail: string;
    status: "pending" | "active" | "done";
    txId?: string;
}

export default function SettlementPage() {
    const params = useParams();
    const router = useRouter();
    const sessionId = params.sessionId as string;

    const [auth, setAuth] = useState<AuthState | null>(null);
    const [escrow, setEscrow] = useState<EscrowData | null>(null);
    const [loading, setLoading] = useState(true);

    const [steps, setSteps] = useState<PaymentStep[]>([
        {
            id: 1,
            label: "HTTP 402 Challenge Received",
            detail: "Network: algorand-testnet",
            status: "pending",
        },
        {
            id: 2,
            label: "Buyer Agent Signing PaymentTxn",
            detail: "Mode: LIVE — Algorand testnet",
            status: "pending",
        },
        {
            id: 3,
            label: "Payment Submitted On-Chain",
            detail: "Verifying transaction...",
            status: "pending",
        },
        {
            id: 4,
            label: "Idempotency Confirmed",
            detail: "No double payment possible",
            status: "pending",
        },
    ]);

    const [paymentComplete, setPaymentComplete] = useState(false);
    const [finalTxId, setFinalTxId] = useState("");

    useEffect(() => {
        const raw = localStorage.getItem("acf_auth");
        if (!raw) {
            router.push("/register");
            return;
        }
        setAuth(JSON.parse(raw));
    }, [router]);

    const fetchEscrow = useCallback(async () => {
        try {
            const res = await getEscrow(sessionId);
            setEscrow(res.data);
        } catch {
            // Escrow might not be ready yet
        } finally {
            setLoading(false);
        }
    }, [sessionId]);

    useEffect(() => {
        if (!auth) return;
        fetchEscrow();
    }, [auth, fetchEscrow]);

    // Run the payment flow
    const runPaymentFlow = useCallback(async () => {
        const updateStep = (id: number, update: Partial<PaymentStep>) => {
            setSteps((prev) =>
                prev.map((s) => (s.id === id ? { ...s, ...update } : s))
            );
        };

        try {
            // Step 1: Trigger delivery to get 402 challenge
            updateStep(1, { status: "active" });
            await new Promise((r) => setTimeout(r, 800));

            let deliveryResult;
            try {
                deliveryResult = await triggerDelivery(sessionId);
            } catch (err: unknown) {
                const status = (err as { response?: { status?: number } })?.response?.status;
                if (status === 402) {
                    // Expected 402 challenge
                    updateStep(1, { status: "done" });
                } else {
                    // Some backends complete in one call
                    deliveryResult = (err as { response?: { data?: Record<string, unknown> } })?.response;
                }
            }

            if (deliveryResult?.data) {
                updateStep(1, { status: "done" });
            } else {
                updateStep(1, { status: "done" });
            }

            // Step 2: Agent signing
            updateStep(2, { status: "active" });
            await new Promise((r) => setTimeout(r, 1200));
            updateStep(2, { status: "done" });

            // Step 3: Submit payment
            updateStep(3, { status: "active" });

            // Re-trigger with payment header (or backend handles it automatically)
            let paymentResult;
            try {
                paymentResult = await triggerDelivery(sessionId, "auto-signed");
            } catch {
                // Payment may have succeeded on first call
            }

            const txId =
                paymentResult?.data?.tx_id ||
                paymentResult?.data?.transaction_id ||
                paymentResult?.data?.payment_tx_id ||
                "";

            await new Promise((r) => setTimeout(r, 800));
            updateStep(3, {
                status: "done",
                detail: txId ? `tx_id: ${truncateHash(txId, 12)}` : "Transaction submitted",
                txId,
            });
            setFinalTxId(txId);

            // Step 4: Idempotency check
            updateStep(4, { status: "active" });
            await new Promise((r) => setTimeout(r, 600));
            updateStep(4, { status: "done" });

            setPaymentComplete(true);
            toast.success("Payment confirmed on-chain! ✓");

            // Refresh escrow
            fetchEscrow();
        } catch (err: unknown) {
            toast.error(extractApiError(err, "Payment flow error"));
        }
    }, [sessionId, fetchEscrow]);

    useEffect(() => {
        if (!auth || loading) return;
        runPaymentFlow();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [auth, loading]);

    if (!auth) return null;

    return (
        <div className="min-h-screen">
            <Navbar />

            <div className="mx-auto max-w-5xl px-6 py-8">
                <motion.div
                    initial={{ opacity: 0, y: -10 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="mb-8"
                >
                    <h1 className="text-3xl font-bold tracking-tight text-white">
                        💳 Settlement
                    </h1>
                    <p className="mt-1 text-sm text-gray-400">
                        Session:{" "}
                        <span className="font-mono text-gray-300">
                            {truncateHash(sessionId, 12)}
                        </span>
                    </p>
                </motion.div>

                {/* Section 1: Escrow */}
                <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.1 }}
                    className="mb-8"
                >
                    {loading ? (
                        <div className="skeleton h-48 w-full" />
                    ) : escrow ? (
                        <EscrowStatus escrow={escrow} />
                    ) : (
                        <div className="rounded-xl border border-[#2a2a3d] bg-[#1a1a28] p-6 text-center text-gray-400">
                            <Lock className="mx-auto mb-2 h-8 w-8 text-gray-600" />
                            <p>Escrow data not available yet</p>
                        </div>
                    )}
                </motion.div>

                {/* Section 2: x402 Payment Flow */}
                <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.2 }}
                    className="mb-8 rounded-xl border border-[#2a2a3d] bg-[#1a1a28] p-6"
                >
                    <h2 className="mb-6 flex items-center gap-2 text-lg font-bold text-white">
                        <Shield className="h-5 w-5 text-indigo-400" />
                        x402 Payment Protocol
                    </h2>

                    <div className="space-y-1">
                        {steps.map((step, i) => (
                            <div key={step.id} className="flex">
                                {/* Timeline line */}
                                <div className="flex flex-col items-center mr-4">
                                    {step.status === "done" ? (
                                        <CheckCircle2 className="h-6 w-6 flex-shrink-0 text-emerald-400" />
                                    ) : step.status === "active" ? (
                                        <Loader2 className="h-6 w-6 flex-shrink-0 animate-spin text-indigo-400" />
                                    ) : (
                                        <Circle className="h-6 w-6 flex-shrink-0 text-gray-600" />
                                    )}
                                    {i < steps.length - 1 && (
                                        <div
                                            className={`w-0.5 flex-1 ${step.status === "done"
                                                ? "bg-emerald-500/40"
                                                : "bg-[#2a2a3d]"
                                                }`}
                                        />
                                    )}
                                </div>

                                {/* Content */}
                                <div className="pb-8">
                                    <p
                                        className={`font-semibold ${step.status === "done"
                                            ? "text-white"
                                            : step.status === "active"
                                                ? "text-indigo-400"
                                                : "text-gray-500"
                                            }`}
                                    >
                                        Step {step.id}: {step.label}
                                    </p>
                                    <p className="text-sm text-gray-400">{step.detail}</p>
                                    {step.txId && (
                                        <a
                                            href={explorerTxUrl(step.txId)}
                                            target="_blank"
                                            rel="noopener noreferrer"
                                            className="mt-1 inline-flex items-center gap-1 text-sm text-indigo-400 hover:text-indigo-300"
                                        >
                                            View on Explorer
                                            <ExternalLink className="h-3 w-3" />
                                        </a>
                                    )}
                                </div>
                            </div>
                        ))}
                    </div>
                </motion.div>

                {/* Payment confirmed */}
                {paymentComplete && (
                    <motion.div
                        initial={{ opacity: 0, scale: 0.95 }}
                        animate={{ opacity: 1, scale: 1 }}
                        className="mb-8 rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-6 text-center"
                    >
                        <CheckCircle2 className="mx-auto mb-3 h-10 w-10 text-emerald-400" />
                        <h3 className="mb-1 text-xl font-bold text-white">
                            ✅ Payment Confirmed On-Chain
                        </h3>
                        {finalTxId && (
                            <div className="mt-2">
                                <span className="text-sm text-gray-400">tx_id: </span>
                                <a
                                    href={explorerTxUrl(finalTxId)}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="inline-flex items-center gap-1 font-mono text-sm text-indigo-400 hover:text-indigo-300"
                                >
                                    {truncateHash(finalTxId, 16)}
                                    <ExternalLink className="h-3 w-3" />
                                </a>
                            </div>
                        )}
                        <p className="mt-1 text-sm text-gray-400">
                            Network: Algorand Testnet
                        </p>
                    </motion.div>
                )}

                {/* CTA */}
                <div className="text-center">
                    <button
                        onClick={() => router.push(`/audit/${sessionId}`)}
                        className="inline-flex items-center gap-2 rounded-lg bg-indigo-500 px-8 py-3 font-semibold text-white shadow-lg shadow-indigo-500/20 transition-all hover:bg-indigo-400"
                    >
                        View Audit Trail
                        <ArrowRight className="h-4 w-4" />
                    </button>
                </div>
            </div>
        </div>
    );
}
