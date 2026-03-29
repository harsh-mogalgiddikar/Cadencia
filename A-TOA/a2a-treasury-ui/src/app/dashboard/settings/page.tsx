"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { User, Bot, Wallet, ExternalLink, Check, Loader2 } from "lucide-react";
import { useAuth } from "@/lib/auth-context";
import { fadeInUp, staggerContainer } from "@/lib/animations";
import CopyButton from "@/components/ui/CopyButton";
import { CardSkeleton } from "@/components/ui/Skeleton";
import type { AgentConfig } from "@/types/api";
import { useAgentConfig } from "@/hooks/useApi";

type Tab = "profile" | "agent" | "wallet";

export default function SettingsPage() {
  const { enterprise, isLoading } = useAuth();
  const [tab, setTab] = useState<Tab>("profile");
  const { data: agentConfig, isLoading: configLoading } = useAgentConfig(
    enterprise?.enterprise_id,
  );

  const tabs: { key: Tab; label: string; icon: typeof User }[] = [
    { key: "profile", label: "Profile", icon: User },
    { key: "agent", label: "Agent Config", icon: Bot },
    { key: "wallet", label: "Wallet", icon: Wallet },
  ];

  if (isLoading) {
    return (
      <div className="mx-auto max-w-3xl space-y-6">
        <CardSkeleton />
        <CardSkeleton />
      </div>
    );
  }

  const kycColor =
    enterprise?.kyc_status === "ACTIVE"
      ? "emerald"
      : enterprise?.kyc_status === "PENDING"
      ? "amber"
      : "red";

  return (
    <div className="mx-auto max-w-3xl">
      <motion.div
        variants={staggerContainer}
        initial="hidden"
        animate="visible"
        className="space-y-6"
      >
        <motion.div variants={fadeInUp}>
          <h2 className="text-2xl font-bold text-zinc-50">
            Enterprise Settings
          </h2>
          <p className="mt-1 text-sm text-zinc-400">
            Manage your enterprise profile and agent configuration
          </p>
        </motion.div>

        {/* Tab bar */}
        <motion.div variants={fadeInUp}>
          <div className="flex gap-1 border-b border-zinc-800">
            {tabs.map((t) => (
              <button
                key={t.key}
                onClick={() => setTab(t.key)}
                className={`flex items-center gap-2 border-b-2 px-4 py-2.5 text-sm font-medium transition-colors ${
                  tab === t.key
                    ? "border-emerald-500 text-emerald-500"
                    : "border-transparent text-zinc-400 hover:text-zinc-300"
                }`}
              >
                <t.icon className="h-4 w-4" />
                {t.label}
              </button>
            ))}
          </div>
        </motion.div>

        {/* Profile Tab */}
        {tab === "profile" && (
          <motion.div variants={fadeInUp}>
            <div className="rounded-xl border border-zinc-800 bg-zinc-900 p-6">
              <div className="space-y-4">
                {[
                  { label: "Legal Name", value: enterprise?.legal_name },
                  { label: "Email", value: enterprise?.email || "—" },
                  { label: "PAN", value: enterprise?.pan, mono: true },
                  { label: "GST", value: enterprise?.gst, mono: true },
                  { label: "Enterprise ID", value: enterprise?.enterprise_id },
                  {
                    label: "Role",
                    value: enterprise?.role || "admin",
                  },
                ].map(({ label, value, mono }) => (
                  <div
                    key={label}
                    className="flex items-center justify-between border-b border-zinc-800 pb-3 last:border-0 last:pb-0"
                  >
                    <span className="text-sm text-zinc-500">{label}</span>
                    <span
                      className={`text-sm text-zinc-50 ${mono ? "font-mono tracking-wider" : ""}`}
                    >
                      {value || "—"}
                    </span>
                  </div>
                ))}
                <div className="flex items-center justify-between">
                  <span className="text-sm text-zinc-500">KYC Status</span>
                  <span
                    className={`rounded-full border px-2.5 py-1 text-xs font-medium ${
                      kycColor === "emerald"
                        ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-400"
                        : kycColor === "amber"
                        ? "border-amber-500/30 bg-amber-500/10 text-amber-400"
                        : "border-red-500/30 bg-red-500/10 text-red-400"
                    }`}
                  >
                    {enterprise?.kyc_status}
                  </span>
                </div>
              </div>
            </div>
          </motion.div>
        )}

        {/* Agent Config Tab */}
        {tab === "agent" && (
          <motion.div variants={fadeInUp}>
            <div className="rounded-xl border border-zinc-800 bg-zinc-900 p-6">
              {configLoading ? (
                <CardSkeleton />
              ) : (
                <AgentConfigForm
                  enterpriseId={enterprise?.enterprise_id}
                  existing={agentConfig ?? null}
                />
              )}
            </div>
          </motion.div>
        )}

        {/* Wallet Tab */}
        {tab === "wallet" && (
          <motion.div variants={fadeInUp}>
            <div className="rounded-xl border border-zinc-800 bg-zinc-900 p-6">
              <div className="space-y-4">
                <div>
                  <span className="text-sm text-zinc-500">
                    Wallet Address
                  </span>
                  <div className="mt-1">
                    {enterprise?.wallet_address ? (
                      <CopyButton
                        text={enterprise.wallet_address}
                        className="bg-zinc-800 px-3 py-2 rounded-lg"
                      />
                    ) : (
                      <p className="text-sm text-zinc-500">
                        No wallet address configured
                      </p>
                    )}
                  </div>
                </div>

                <div>
                  <span className="text-sm text-zinc-500">Network</span>
                  <p className="mt-1 text-sm text-zinc-50">
                    Algorand TestNet
                  </p>
                </div>

                <a
                  href="https://bank.testnet.algorand.network/"
                  target="_blank"
                  rel="noreferrer"
                  className="flex items-center gap-2 rounded-lg border border-zinc-700 px-4 py-2.5 text-sm text-zinc-300 transition-colors hover:border-zinc-600 hover:text-zinc-50"
                >
                  <ExternalLink className="h-4 w-4" />
                  Get Test ALGO from Faucet
                </a>
              </div>
            </div>
          </motion.div>
        )}
      </motion.div>
    </div>
  );
}

/* ── Agent Config Form ──────────────────────────────────────────────── */

const DEFAULTS: Omit<AgentConfig, "config_id" | "enterprise_id"> = {
  agent_role: "buyer",
  intrinsic_value: 100000,
  risk_factor: 0.12,
  negotiation_margin: 0.15,
  concession_curve: { type: "linear", steepness: 0.5 },
  budget_ceiling: 500000,
  max_exposure: 1000000,
  strategy_default: "balanced",
  max_rounds: 10,
  timeout_seconds: 300,
};

function AgentConfigForm({
  enterpriseId,
  existing,
}: {
  enterpriseId: string | undefined;
  existing: AgentConfig | null;
}) {
  const { mutate: mutateAgentConfig } = useAgentConfig(enterpriseId);

  const [form, setForm] = useState({
    agent_role:          existing?.agent_role          ?? DEFAULTS.agent_role,
    intrinsic_value:     existing?.intrinsic_value     ?? DEFAULTS.intrinsic_value,
    risk_factor:         existing?.risk_factor         ?? DEFAULTS.risk_factor,
    negotiation_margin:  existing?.negotiation_margin  ?? DEFAULTS.negotiation_margin,
    concession_curve:    JSON.stringify(
      existing?.concession_curve ?? DEFAULTS.concession_curve, null, 2,
    ),
    budget_ceiling:      existing?.budget_ceiling      ?? DEFAULTS.budget_ceiling,
    max_exposure:        existing?.max_exposure        ?? DEFAULTS.max_exposure,
    strategy_default:    existing?.strategy_default    ?? DEFAULTS.strategy_default,
    max_rounds:          existing?.max_rounds          ?? DEFAULTS.max_rounds,
    timeout_seconds:     existing?.timeout_seconds     ?? DEFAULTS.timeout_seconds,
  });

  const [saving, setSaving]     = useState(false);
  const [toast, setToast]       = useState<{ type: "success" | "error"; msg: string } | null>(null);

  const set = (key: string, value: string | number) =>
    setForm((prev) => ({ ...prev, [key]: value }));

  const handleSave = async () => {
    if (!enterpriseId) return;
    setSaving(true);
    setToast(null);

    let concessionObj: Record<string, unknown>;
    try {
      concessionObj = JSON.parse(form.concession_curve);
    } catch {
      setToast({ type: "error", msg: "Concession curve must be valid JSON" });
      setSaving(false);
      return;
    }

    const body = {
      agent_role:         form.agent_role,
      intrinsic_value:    Number(form.intrinsic_value),
      risk_factor:        Number(form.risk_factor),
      negotiation_margin: Number(form.negotiation_margin),
      concession_curve:   concessionObj,
      budget_ceiling:     form.budget_ceiling != null ? Number(form.budget_ceiling) : null,
      max_exposure:       Number(form.max_exposure),
      strategy_default:   form.strategy_default,
      max_rounds:         Number(form.max_rounds),
      timeout_seconds:    Number(form.timeout_seconds),
    };

    try {
      const res = await fetch(`/api/v1/enterprises/${enterpriseId}/agent-config`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify(body),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({ error: res.statusText }));
        throw new Error(err.detail || err.error || "Save failed");
      }

      await mutateAgentConfig();
      setToast({ type: "success", msg: "Agent configuration saved successfully" });
    } catch (err: unknown) {
      setToast({ type: "error", msg: (err as Error).message });
    } finally {
      setSaving(false);
      setTimeout(() => setToast(null), 4000);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <p className="text-sm text-zinc-400">
          {existing
            ? "Edit your agent\u2019s negotiation parameters below."
            : "No configuration found \u2014 fill in the form to create one."}
        </p>
      </div>

      {/* Form grid */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <FormSelect
          label="Agent Role"
          value={form.agent_role}
          onChange={(v) => set("agent_role", v)}
          options={["buyer", "seller"]}
        />
        <FormSelect
          label="Strategy Default"
          value={form.strategy_default}
          onChange={(v) => set("strategy_default", v)}
          options={["balanced", "aggressive", "conservative", "adaptive"]}
        />
        <FormField
          label="Intrinsic Value (\u20b9)"
          type="number"
          value={form.intrinsic_value}
          onChange={(v) => set("intrinsic_value", v)}
          placeholder="100000"
        />
        <FormField
          label="Risk Factor"
          type="number"
          value={form.risk_factor}
          onChange={(v) => set("risk_factor", v)}
          placeholder="0.12"
          step="0.01"
        />
        <FormField
          label="Negotiation Margin"
          type="number"
          value={form.negotiation_margin}
          onChange={(v) => set("negotiation_margin", v)}
          placeholder="0.15"
          step="0.01"
        />
        <FormField
          label="Budget Ceiling (\u20b9)"
          type="number"
          value={form.budget_ceiling ?? ""}
          onChange={(v) => set("budget_ceiling", v)}
          placeholder="500000"
        />
        <FormField
          label="Max Exposure (\u20b9)"
          type="number"
          value={form.max_exposure}
          onChange={(v) => set("max_exposure", v)}
          placeholder="1000000"
        />
        <FormField
          label="Max Rounds"
          type="number"
          value={form.max_rounds}
          onChange={(v) => set("max_rounds", v)}
          placeholder="10"
        />
        <FormField
          label="Timeout (seconds)"
          type="number"
          value={form.timeout_seconds}
          onChange={(v) => set("timeout_seconds", v)}
          placeholder="300"
        />
      </div>

      {/* Concession curve (full width) */}
      <div>
        <label className="mb-1.5 block text-sm font-medium text-zinc-400">
          Concession Curve (JSON)
        </label>
        <textarea
          rows={3}
          value={form.concession_curve}
          onChange={(e) => set("concession_curve", e.target.value)}
          className="w-full rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2 font-mono text-sm text-zinc-100 placeholder-zinc-600 outline-none transition-colors focus:border-emerald-500/50 focus:ring-1 focus:ring-emerald-500/30"
          placeholder='{"type": "linear", "steepness": 0.5}'
        />
      </div>

      {/* Toast */}
      {toast && (
        <div
          className={`flex items-center gap-2 rounded-lg border px-4 py-2.5 text-sm ${
            toast.type === "success"
              ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-400"
              : "border-red-500/30 bg-red-500/10 text-red-400"
          }`}
        >
          {toast.type === "success" ? (
            <Check className="h-4 w-4 shrink-0" />
          ) : (
            <Bot className="h-4 w-4 shrink-0" />
          )}
          {toast.msg}
        </div>
      )}

      {/* Save button */}
      <button
        onClick={handleSave}
        disabled={saving || !enterpriseId}
        className="flex items-center gap-2 rounded-lg bg-emerald-500 px-5 py-2.5 text-sm font-semibold text-black transition-all hover:bg-emerald-400 disabled:cursor-not-allowed disabled:opacity-50"
      >
        {saving ? (
          <Loader2 className="h-4 w-4 animate-spin" />
        ) : (
          <Check className="h-4 w-4" />
        )}
        {saving ? "Saving\u2026" : "Save Configuration"}
      </button>
    </div>
  );
}

/* ── Reusable form primitives ───────────────────────────────────────── */

function FormField({
  label,
  type = "text",
  value,
  onChange,
  placeholder,
  step,
}: {
  label: string;
  type?: string;
  value: string | number;
  onChange: (v: string) => void;
  placeholder?: string;
  step?: string;
}) {
  return (
    <div>
      <label className="mb-1.5 block text-sm font-medium text-zinc-400">
        {label}
      </label>
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        step={step}
        className="w-full rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2 text-sm text-zinc-100 placeholder-zinc-600 outline-none transition-colors focus:border-emerald-500/50 focus:ring-1 focus:ring-emerald-500/30"
      />
    </div>
  );
}

function FormSelect({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  options: string[];
}) {
  return (
    <div>
      <label className="mb-1.5 block text-sm font-medium text-zinc-400">
        {label}
      </label>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2 text-sm text-zinc-100 outline-none transition-colors focus:border-emerald-500/50 focus:ring-1 focus:ring-emerald-500/30"
      >
        {options.map((opt) => (
          <option key={opt} value={opt}>
            {opt.charAt(0).toUpperCase() + opt.slice(1)}
          </option>
        ))}
      </select>
    </div>
  );
}
