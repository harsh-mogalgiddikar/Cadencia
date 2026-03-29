"use client";

import { useState, useEffect, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { motion } from "framer-motion";
import { toast } from "sonner";
import {
    registerEnterprise,
    verifyEmail,
    activateEnterprise,
    configureAgent,
    setTreasuryPolicy,
    registerInRegistry,
    loginEnterprise,
} from "@/lib/api";
import { extractApiError } from "@/lib/utils";
import StatusBadge from "@/components/StatusBadge";
import {
    Zap,
    Building2,
    Mail,
    CheckCircle2,
    Settings,
    ArrowRight,
    Loader2,
} from "lucide-react";

function RegisterContent() {
    const router = useRouter();
    const searchParams = useSearchParams();
    const roleParam = searchParams.get("role") || "buyer";

    const [step, setStep] = useState(1);
    const [loading, setLoading] = useState(false);

    // Form data — using backend field names: pan, gst (no role in registration)
    const [legalName, setLegalName] = useState(
        roleParam === "buyer" ? "Bharat Tech Imports Pvt Ltd" : "Delhi Exports Pvt Ltd"
    );
    const [email, setEmail] = useState(
        roleParam === "buyer" ? "buyer@acfdemo.in" : "seller@acfdemo.in"
    );
    const [password, setPassword] = useState("SecurePass123!");
    const [pan, setPan] = useState(
        roleParam === "buyer" ? "AABCT1234E" : "BBBCS5678F"
    );
    const [gst, setGst] = useState(
        roleParam === "buyer" ? "27AABCT1234E1ZV" : "07BBBCS5678F1ZW"
    );
    const [wallet, setWallet] = useState("");

    // Registration response data
    const [enterpriseId, setEnterpriseId] = useState("");
    const [verificationToken, setVerificationToken] = useState("");
    const [authToken, setAuthToken] = useState("");

    // Agent config — matching backend AgentConfigRequest schema
    const [intrinsicValue, setIntrinsicValue] = useState(
        roleParam === "buyer" ? 85000 : 91350
    );
    const [riskFactor, setRiskFactor] = useState(
        roleParam === "buyer" ? 0.35 : 0.25
    );
    const [negotiationMargin, setNegotiationMargin] = useState(0.08);
    const [budgetCeiling, setBudgetCeiling] = useState(
        roleParam === "buyer" ? 96000 : 0
    );
    const [maxRounds, setMaxRounds] = useState(8);
    const [serviceTags, setServiceTags] = useState("cotton, textiles, export");

    const role = roleParam as "buyer" | "seller";

    // Step labels
    const steps = [
        { num: 1, label: "Register", icon: Building2 },
        { num: 2, label: "Verify", icon: Mail },
        { num: 3, label: "Activate", icon: CheckCircle2 },
        { num: 4, label: "Configure", icon: Settings },
    ];

    // ── Step 1: Register ─────────────────────────────────────────────────
    const handleRegister = async () => {
        setLoading(true);
        try {
            const res = await registerEnterprise({
                legal_name: legalName,
                email,
                password,
                pan,
                gst,
                wallet_address: wallet || undefined,
            });
            const data = res.data;
            setEnterpriseId(data.enterprise_id);
            setVerificationToken(data.verification_token || "");
            toast.success("Enterprise registered! Check your email.");
            setStep(2);
        } catch (err: unknown) {
            const msg = extractApiError(err, "Registration failed");
            // If email already registered, try to login directly
            if (msg.includes("already registered")) {
                toast.info("Email already registered — logging you in...");
                try {
                    const loginRes = await loginEnterprise(email, password);
                    const token = loginRes.data?.access_token || "";
                    localStorage.setItem(
                        "acf_auth",
                        JSON.stringify({
                            enterprise_id: "existing",
                            legal_name: legalName,
                            token,
                            role,
                        })
                    );
                    toast.success("Logged in! Redirecting to dashboard...");
                    router.push("/dashboard");
                    return;
                } catch {
                    toast.error("Login failed — check your password");
                }
            } else {
                toast.error(msg);
            }
        } finally {
            setLoading(false);
        }
    };

    // ── Step 2: Verify Email ──────────────────────────────────────────────
    const handleVerify = async () => {
        setLoading(true);
        try {
            await verifyEmail(enterpriseId, verificationToken);
            toast.success("Email verified!");
            setStep(3);
        } catch (err: unknown) {
            toast.error(extractApiError(err, "Verification failed"));
        } finally {
            setLoading(false);
        }
    };

    // ── Step 3: Activate ──────────────────────────────────────────────────
    // Activation requires admin auth, so we must login first
    useEffect(() => {
        if (step !== 3) return;
        let cancelled = false;

        const doActivate = async () => {
            setLoading(true);
            try {
                // Step 3a: Login to get JWT (required for admin-protected endpoints)
                const loginRes = await loginEnterprise(email, password);
                const token = loginRes.data?.access_token || loginRes.data?.token || "";
                setAuthToken(token);

                // Store auth so the axios interceptor picks up the JWT
                localStorage.setItem(
                    "acf_auth",
                    JSON.stringify({
                        enterprise_id: enterpriseId,
                        legal_name: legalName,
                        token,
                        role,
                    })
                );

                // Step 3b: Activate enterprise (requires admin JWT)
                await activateEnterprise(enterpriseId);

                if (!cancelled) {
                    toast.success("Agent Card provisioned ✓");
                    setLoading(false);
                    setTimeout(() => {
                        if (!cancelled) setStep(4);
                    }, 1500);
                }
            } catch (err: unknown) {
                toast.error(extractApiError(err, "Activation failed"));
                setLoading(false);
            }
        };

        doActivate();
        return () => {
            cancelled = true;
        };
    }, [step, enterpriseId, email, password, legalName, role]);

    // ── Step 4: Configure Agent ───────────────────────────────────────────
    const handleConfigure = async () => {
        setLoading(true);
        try {
            // Backend AgentConfigRequest schema:
            // agent_role, intrinsic_value, risk_factor, negotiation_margin,
            // concession_curve (dict), budget_ceiling, max_exposure, strategy_default,
            // max_rounds, timeout_seconds
            await configureAgent(enterpriseId, {
                agent_role: role,
                intrinsic_value: intrinsicValue,
                risk_factor: riskFactor,
                negotiation_margin: negotiationMargin,
                concession_curve: { linear: 0.5, time_pressure: 0.3, reciprocity: 0.2 },
                budget_ceiling: role === "buyer" ? budgetCeiling : undefined,
                max_exposure: 100000,
                strategy_default: "balanced",
                max_rounds: maxRounds,
                timeout_seconds: 3600,
            });

            // Set treasury policy (required for session creation)
            await setTreasuryPolicy(enterpriseId, {
                buffer_threshold: 0.15,
                risk_tolerance: "balanced",
                yield_strategy: "none",
            });

            // Register in agent registry
            const tags = serviceTags
                .split(",")
                .map((t) => t.trim())
                .filter(Boolean);
            try {
                await registerInRegistry(tags);
            } catch {
                // Registry registration may fail if already registered — non-critical
            }

            // Persist final auth state
            localStorage.setItem(
                "acf_auth",
                JSON.stringify({
                    enterprise_id: enterpriseId,
                    legal_name: legalName,
                    token: authToken,
                    role,
                })
            );

            toast.success("Agent configured! Redirecting to dashboard...");
            router.push("/dashboard");
        } catch (err: unknown) {
            toast.error(extractApiError(err, "Configuration failed"));
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="min-h-screen px-6 py-12">
            <div className="mx-auto max-w-2xl">
                {/* Header */}
                <div className="mb-10 flex items-center gap-3">
                    <Zap className="h-6 w-6 text-indigo-400" />
                    <span className="text-xl font-bold text-white">ACF</span>
                    <span className="text-gray-500">·</span>
                    <span className="text-sm text-gray-400">Enterprise Registration</span>
                </div>

                {/* Progress stepper */}
                <div className="mb-12 flex items-center justify-between">
                    {steps.map(({ num, label, icon: Icon }, i) => (
                        <div key={num} className="flex items-center">
                            <div className="flex flex-col items-center">
                                <div
                                    className={`flex h-10 w-10 items-center justify-center rounded-full border-2 transition-all ${step >= num
                                        ? "border-indigo-500 bg-indigo-500/20 text-indigo-400"
                                        : "border-[#2a2a3d] bg-[#1a1a28] text-gray-600"
                                        }`}
                                >
                                    {step > num ? (
                                        <CheckCircle2 className="h-5 w-5 text-emerald-400" />
                                    ) : (
                                        <Icon className="h-5 w-5" />
                                    )}
                                </div>
                                <span
                                    className={`mt-2 text-xs font-medium ${step >= num ? "text-white" : "text-gray-600"
                                        }`}
                                >
                                    {label}
                                </span>
                            </div>
                            {i < steps.length - 1 && (
                                <div
                                    className={`mx-4 h-0.5 w-16 md:w-24 ${step > num ? "bg-indigo-500" : "bg-[#2a2a3d]"
                                        }`}
                                />
                            )}
                        </div>
                    ))}
                </div>

                {/* Step Content */}
                <motion.div
                    key={step}
                    initial={{ opacity: 0, x: 20 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ duration: 0.3 }}
                    className="rounded-xl border border-[#2a2a3d] bg-[#1a1a28] p-8"
                >
                    {/* ── STEP 1 ─────────────────────────────────────────────── */}
                    {step === 1 && (
                        <div>
                            <h2 className="mb-1 text-2xl font-bold text-white">
                                Enterprise Registration
                            </h2>
                            <p className="mb-8 text-sm text-gray-400">
                                Register your enterprise to provision an AI trading agent.
                            </p>

                            <div className="mb-4">
                                <StatusBadge status={role} size="md" pulse={false} />
                            </div>

                            <div className="space-y-5">
                                <Field label="Legal Name" value={legalName} onChange={setLegalName} />
                                <Field label="Email" type="email" value={email} onChange={setEmail} />
                                <Field label="Password" type="password" value={password} onChange={setPassword} />
                                <Field
                                    label="PAN Number"
                                    value={pan}
                                    onChange={setPan}
                                    placeholder="AAAAA9999A"
                                />
                                <Field label="GST" value={gst} onChange={setGst} />
                                <Field
                                    label="Algorand Wallet Address"
                                    value={wallet}
                                    onChange={setWallet}
                                    placeholder="Paste your Algorand address (optional)"
                                    mono
                                />
                            </div>

                            <button
                                onClick={handleRegister}
                                disabled={loading}
                                className="mt-8 flex w-full items-center justify-center gap-2 rounded-lg bg-indigo-500 px-6 py-3 font-semibold text-white transition-all hover:bg-indigo-400 disabled:opacity-50"
                            >
                                {loading ? (
                                    <Loader2 className="h-5 w-5 animate-spin" />
                                ) : (
                                    <>
                                        Register Enterprise
                                        <ArrowRight className="h-4 w-4" />
                                    </>
                                )}
                            </button>
                        </div>
                    )}

                    {/* ── STEP 2 ─────────────────────────────────────────────── */}
                    {step === 2 && (
                        <div>
                            <h2 className="mb-1 text-2xl font-bold text-white">
                                📧 Verify Your Email
                            </h2>
                            <p className="mb-6 text-sm text-gray-400">
                                We sent a verification code to{" "}
                                <span className="text-white">{email}</span>
                            </p>

                            {/* Demo hint */}
                            <div className="mb-6 rounded-lg border border-amber-500/30 bg-amber-500/10 p-4 text-sm text-amber-300">
                                <p className="mb-1 font-semibold">💡 Demo Mode</p>
                                <p className="text-amber-400/80">
                                    The verification token is returned directly in the registration
                                    response. It has been pre-filled below.
                                </p>
                            </div>

                            <Field
                                label="Verification Token"
                                value={verificationToken}
                                onChange={setVerificationToken}
                                mono
                            />

                            <button
                                onClick={handleVerify}
                                disabled={loading || !verificationToken}
                                className="mt-6 flex w-full items-center justify-center gap-2 rounded-lg bg-indigo-500 px-6 py-3 font-semibold text-white transition-all hover:bg-indigo-400 disabled:opacity-50"
                            >
                                {loading ? (
                                    <Loader2 className="h-5 w-5 animate-spin" />
                                ) : (
                                    <>
                                        Verify Email
                                        <ArrowRight className="h-4 w-4" />
                                    </>
                                )}
                            </button>
                        </div>
                    )}

                    {/* ── STEP 3 ─────────────────────────────────────────────── */}
                    {step === 3 && (
                        <div className="flex flex-col items-center py-8 text-center">
                            <CheckCircle2 className="mb-4 h-12 w-12 text-emerald-400" />
                            <h2 className="mb-2 text-2xl font-bold text-white">
                                ✓ Email Verified
                            </h2>
                            <p className="mb-6 text-gray-400">
                                Logging in and activating your enterprise...
                            </p>
                            <Loader2 className="h-8 w-8 animate-spin text-indigo-400" />
                            <p className="mt-4 text-xs text-gray-500">
                                Provisioning AI Agent Card on Algorand
                            </p>
                        </div>
                    )}

                    {/* ── STEP 4 ─────────────────────────────────────────────── */}
                    {step === 4 && (
                        <div>
                            <h2 className="mb-1 text-2xl font-bold text-white">
                                ⚙️ Agent Configuration
                            </h2>
                            <p className="mb-8 text-sm text-gray-400">
                                Configure your AI agent&apos;s trading parameters.
                            </p>

                            <div className="space-y-5">
                                <NumberField
                                    label="Intrinsic Value (₹) — Your target price"
                                    value={intrinsicValue}
                                    onChange={setIntrinsicValue}
                                />
                                <NumberField
                                    label="Risk Factor (0 = conservative, 1 = aggressive)"
                                    value={riskFactor}
                                    onChange={setRiskFactor}
                                    step={0.05}
                                />
                                <NumberField
                                    label="Negotiation Margin (% concession allowed)"
                                    value={negotiationMargin}
                                    onChange={setNegotiationMargin}
                                    step={0.01}
                                />
                                {role === "buyer" && (
                                    <NumberField
                                        label="Budget Ceiling (₹)"
                                        value={budgetCeiling}
                                        onChange={setBudgetCeiling}
                                    />
                                )}
                                <NumberField
                                    label="Max Rounds"
                                    value={maxRounds}
                                    onChange={setMaxRounds}
                                    step={1}
                                />
                                <Field
                                    label="Service Tags (comma-separated)"
                                    value={serviceTags}
                                    onChange={setServiceTags}
                                />
                            </div>

                            <button
                                onClick={handleConfigure}
                                disabled={loading}
                                className="mt-8 flex w-full items-center justify-center gap-2 rounded-lg bg-indigo-500 px-6 py-3 font-semibold text-white transition-all hover:bg-indigo-400 disabled:opacity-50"
                            >
                                {loading ? (
                                    <Loader2 className="h-5 w-5 animate-spin" />
                                ) : (
                                    <>
                                        Save & Go to Dashboard
                                        <ArrowRight className="h-4 w-4" />
                                    </>
                                )}
                            </button>
                        </div>
                    )}
                </motion.div>
            </div>
        </div>
    );
}

// ── Field Components ──────────────────────────────────────────────────

function Field({
    label,
    value,
    onChange,
    type = "text",
    placeholder,
    mono,
}: {
    label: string;
    value: string;
    onChange: (v: string) => void;
    type?: string;
    placeholder?: string;
    mono?: boolean;
}) {
    return (
        <div>
            <label className="mb-1.5 block text-sm font-medium text-gray-300">
                {label}
            </label>
            <input
                type={type}
                value={value}
                onChange={(e) => onChange(e.target.value)}
                placeholder={placeholder}
                className={`w-full rounded-lg border border-[#2a2a3d] bg-[#12121a] px-4 py-2.5 text-sm text-white placeholder-gray-600 outline-none transition-colors focus:border-indigo-500 ${mono ? "font-mono" : ""
                    }`}
            />
        </div>
    );
}

function NumberField({
    label,
    value,
    onChange,
    step = 1,
}: {
    label: string;
    value: number;
    onChange: (v: number) => void;
    step?: number;
}) {
    return (
        <div>
            <label className="mb-1.5 block text-sm font-medium text-gray-300">
                {label}
            </label>
            <input
                type="number"
                value={value}
                onChange={(e) => onChange(parseFloat(e.target.value) || 0)}
                step={step}
                className="w-full rounded-lg border border-[#2a2a3d] bg-[#12121a] px-4 py-2.5 font-mono text-sm text-white outline-none transition-colors focus:border-indigo-500"
            />
        </div>
    );
}

export default function RegisterPage() {
    return (
        <Suspense
            fallback={
                <div className="flex min-h-screen items-center justify-center">
                    <Loader2 className="h-8 w-8 animate-spin text-indigo-400" />
                </div>
            }
        >
            <RegisterContent />
        </Suspense>
    );
}
