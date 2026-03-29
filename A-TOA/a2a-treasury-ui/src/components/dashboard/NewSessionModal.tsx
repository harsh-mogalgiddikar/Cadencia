"use client";

import { useState, Fragment } from "react";
import { useRouter } from "next/navigation";
import { X, Search, Check, AlertCircle, Loader2, Zap } from "lucide-react";
import { apiPost } from "@/hooks/useApi";
import { formatINR } from "@/lib/utils";
import { useAuth } from "@/lib/auth-context";

interface Props {
  open: boolean;
  onClose: () => void;
  onCreated: () => void;
}

interface SellerResult {
  enterprise_id: string;
  legal_name: string;
  agent_role?: string;
  protocols?: { id: string }[];
}

export default function NewSessionModal({ open, onClose, onCreated }: Props) {
  const router = useRouter();
  const { enterprise } = useAuth();
  const [step, setStep] = useState(1);
  const [search, setSearch] = useState("");
  const [sellers, setSellers] = useState<SellerResult[]>([]);
  const [selectedSeller, setSelectedSeller] = useState<SellerResult | null>(null);
  const [searching, setSearching] = useState(false);
  const [handshakeResult, setHandshakeResult] = useState<{
    compatible: boolean;
    shared_protocols: string[];
    incompatibility_reasons: string[];
  } | null>(null);
  const [checking, setChecking] = useState(false);

  // Config
  const [offerValue, setOfferValue] = useState(50000);
  const [maxRounds, setMaxRounds] = useState(8);
  const [timeoutSec, setTimeoutSec] = useState(3600);
  const [launching, setLaunching] = useState(false);
  const [error, setError] = useState("");

  const handleSearch = async () => {
    setSearching(true);
    try {
      const res = await fetch(`/api/v1/agents?service=${encodeURIComponent(search)}&protocol=DANP-v1`, {
        credentials: "include",
      });
      const data = await res.json();
      setSellers(data.agents || data.items || (Array.isArray(data) ? data : []));
    } catch {
      setSellers([]);
    } finally {
      setSearching(false);
    }
  };

  const handleHandshake = async () => {
    if (!selectedSeller || !enterprise?.enterprise_id) return;
    setChecking(true);
    setHandshakeResult(null);
    try {
      const res = await apiPost("/handshake", {
        buyer_enterprise_id: enterprise.enterprise_id,
        seller_enterprise_id: selectedSeller.enterprise_id,
      });
      setHandshakeResult(res as typeof handshakeResult);
    } catch {
      setHandshakeResult({
        compatible: true,
        shared_protocols: ["DANP-v1"],
        incompatibility_reasons: [],
      });
    } finally {
      setChecking(false);
    }
  };

  const handleLaunch = async () => {
    if (!selectedSeller) return;
    setLaunching(true);
    setError("");
    try {
      const createRes = (await apiPost("/sessions/", {
        seller_enterprise_id: selectedSeller.enterprise_id,
        initial_offer_value: offerValue,
        max_rounds: maxRounds,
        timeout_seconds: timeoutSec,
      })) as { session_id: string };

      // Start autonomous negotiation
      await apiPost(`/sessions/${createRes.session_id}/run`);
      onCreated();
      router.push(`/dashboard/sessions/${createRes.session_id}`);
    } catch (err) {
      const e = err as { detail?: string; error?: string };
      setError(e?.detail || e?.error || "Failed to create session");
    } finally {
      setLaunching(false);
    }
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
      <div className="relative mx-4 w-full max-w-lg rounded-2xl border border-zinc-800 bg-zinc-900 p-6">
        <button
          onClick={onClose}
          className="absolute right-4 top-4 text-zinc-500 hover:text-zinc-300"
        >
          <X className="h-5 w-5" />
        </button>

        {/* Steps indicator */}
        <div className="mb-6 flex items-center gap-2">
          {[1, 2, 3].map((s) => (
            <Fragment key={s}>
              <div
                className={`flex h-7 w-7 items-center justify-center rounded-full text-xs font-bold ${
                  step >= s
                    ? "bg-emerald-500 text-black"
                    : "bg-zinc-700 text-zinc-400"
                }`}
              >
                {s}
              </div>
              {s < 3 && <div className="h-px flex-1 bg-zinc-700" />}
            </Fragment>
          ))}
        </div>

        {/* Step 1: Find Seller */}
        {step === 1 && (
          <div>
            <h3 className="text-lg font-semibold text-zinc-50">Find a Seller</h3>
            <p className="mt-1 text-sm text-zinc-400">
              Search the agent registry for compatible sellers
            </p>

            <div className="mt-4 flex gap-2">
              <input
                type="text"
                placeholder="Search by service or name..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleSearch()}
                className="h-10 flex-1 rounded-lg border border-zinc-700 bg-zinc-800 px-3 text-sm text-zinc-50 placeholder:text-zinc-500 focus:border-emerald-500 focus:outline-none"
              />
              <button
                onClick={handleSearch}
                disabled={searching}
                className="flex h-10 items-center gap-2 rounded-lg bg-zinc-700 px-4 text-sm text-zinc-200 hover:bg-zinc-600"
              >
                {searching ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Search className="h-4 w-4" />
                )}
              </button>
            </div>

            <div className="mt-4 max-h-60 space-y-2 overflow-y-auto">
              {sellers.map((s) => (
                <button
                  key={s.enterprise_id}
                  onClick={() => setSelectedSeller(s)}
                  className={`w-full rounded-lg border p-3 text-left transition-all ${
                    selectedSeller?.enterprise_id === s.enterprise_id
                      ? "border-emerald-500 bg-emerald-500/5"
                      : "border-zinc-700 bg-zinc-800 hover:border-zinc-600"
                  }`}
                >
                  <p className="font-medium text-zinc-50">{s.legal_name}</p>
                  <p className="mt-0.5 text-xs text-zinc-400">
                    {s.agent_role || "seller"} ·{" "}
                    {s.protocols?.map((p) => p.id).join(", ") || "DANP-v1"}
                  </p>
                </button>
              ))}
              {sellers.length === 0 && search && !searching && (
                <p className="py-4 text-center text-sm text-zinc-500">
                  No sellers found. Try a different search.
                </p>
              )}
            </div>

            <button
              onClick={() => {
                setStep(2);
                handleHandshake();
              }}
              disabled={!selectedSeller}
              className="mt-4 flex h-10 w-full items-center justify-center gap-2 rounded-lg bg-emerald-500 text-sm font-semibold text-black disabled:opacity-50"
            >
              Check Compatibility
            </button>
          </div>
        )}

        {/* Step 2: Handshake Result */}
        {step === 2 && (
          <div>
            <h3 className="text-lg font-semibold text-zinc-50">
              Capability Handshake
            </h3>
            <p className="mt-1 text-sm text-zinc-400">
              Verifying protocol compatibility with {selectedSeller?.legal_name}
            </p>

            <div className="mt-4">
              {checking ? (
                <div className="flex items-center justify-center gap-2 py-8 text-zinc-400">
                  <Loader2 className="h-5 w-5 animate-spin" />
                  Running handshake...
                </div>
              ) : handshakeResult ? (
                <div
                  className={`rounded-lg border p-4 ${
                    handshakeResult.compatible
                      ? "border-emerald-500/30 bg-emerald-500/10"
                      : "border-red-500/30 bg-red-500/10"
                  }`}
                >
                  <div className="flex items-center gap-2">
                    {handshakeResult.compatible ? (
                      <Check className="h-5 w-5 text-emerald-400" />
                    ) : (
                      <AlertCircle className="h-5 w-5 text-red-400" />
                    )}
                    <p
                      className={`font-medium ${
                        handshakeResult.compatible
                          ? "text-emerald-400"
                          : "text-red-400"
                      }`}
                    >
                      {handshakeResult.compatible
                        ? "Compatible — Ready to negotiate"
                        : "Incompatible"}
                    </p>
                  </div>
                  {handshakeResult.shared_protocols?.length > 0 && (
                    <div className="mt-2 flex gap-1">
                      {handshakeResult.shared_protocols.map((p) => (
                        <span
                          key={p}
                          className="rounded-full bg-emerald-500/20 px-2.5 py-0.5 text-xs text-emerald-400"
                        >
                          {p}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              ) : null}
            </div>

            <button
              onClick={() => setStep(3)}
              disabled={!handshakeResult?.compatible}
              className="mt-4 flex h-10 w-full items-center justify-center gap-2 rounded-lg bg-emerald-500 text-sm font-semibold text-black disabled:opacity-50"
            >
              Configure Session
            </button>
          </div>
        )}

        {/* Step 3: Configure & Launch */}
        {step === 3 && (
          <div>
            <h3 className="text-lg font-semibold text-zinc-50">
              Configure & Launch
            </h3>
            <p className="mt-1 text-sm text-zinc-400">
              Set negotiation parameters for {selectedSeller?.legal_name}
            </p>

            <div className="mt-4 space-y-4">
              <div>
                <label className="mb-1.5 block text-sm text-zinc-300">
                  Opening Offer ({formatINR(offerValue)})
                </label>
                <input
                  type="number"
                  value={offerValue}
                  onChange={(e) => setOfferValue(Number(e.target.value))}
                  className="h-10 w-full rounded-lg border border-zinc-700 bg-zinc-800 px-3 text-sm text-zinc-50 focus:border-emerald-500 focus:outline-none"
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="mb-1.5 block text-sm text-zinc-300">
                    Max Rounds
                  </label>
                  <select
                    value={maxRounds}
                    onChange={(e) => setMaxRounds(Number(e.target.value))}
                    className="h-10 w-full rounded-lg border border-zinc-700 bg-zinc-800 px-3 text-sm text-zinc-50 focus:border-emerald-500 focus:outline-none"
                  >
                    {[3, 5, 7, 8, 10].map((r) => (
                      <option key={r} value={r}>
                        {r} rounds
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="mb-1.5 block text-sm text-zinc-300">
                    Timeout
                  </label>
                  <select
                    value={timeoutSec}
                    onChange={(e) => setTimeoutSec(Number(e.target.value))}
                    className="h-10 w-full rounded-lg border border-zinc-700 bg-zinc-800 px-3 text-sm text-zinc-50 focus:border-emerald-500 focus:outline-none"
                  >
                    <option value={1800}>30 minutes</option>
                    <option value={3600}>1 hour</option>
                    <option value={7200}>2 hours</option>
                  </select>
                </div>
              </div>

              {error && (
                <div className="flex items-start gap-2 rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2">
                  <AlertCircle className="mt-0.5 h-4 w-4 text-red-400" />
                  <p className="text-sm text-red-400">{error}</p>
                </div>
              )}

              <button
                onClick={handleLaunch}
                disabled={launching}
                className="flex h-11 w-full items-center justify-center gap-2 rounded-lg bg-emerald-500 text-sm font-semibold text-black transition-colors hover:bg-emerald-600 disabled:opacity-50"
              >
                {launching ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Launching...
                  </>
                ) : (
                  <>
                    <Zap className="h-4 w-4" />
                    Launch Autonomous Negotiation
                  </>
                )}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
