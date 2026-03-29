"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import Link from "next/link";
import {
  CheckCircle2, Circle, Loader2, XCircle,
  ExternalLink, Copy, ChevronRight, Zap,
  Shield, ArrowRight,
} from "lucide-react";

/* ── Types ──────────────────────────────────────────────────────────────── */

type PhaseStatus = "idle" | "running" | "done" | "error";

interface PhaseEvent {
  phase:  number;
  status: PhaseStatus;
  label:  string;
  detail: string;
  data:   Record<string, unknown>;
}

interface DemoSummary {
  session_id:       string;
  agreed_value_inr: number;
  escrow: {
    escrow_id:    string;
    contract_ref: string;
    app_id:       string | number;
  };
  transactions: {
    fund_tx_id:    string;
    payment_tx_id: string;
    release_tx_id: string;
    anchor_tx_id:  string;
  };
  explorer_links: {
    fund:    string | null;
    payment: string | null;
    release: string | null;
    anchor:  string | null;
  };
  audit: {
    merkle_root: string;
    leaf_count:  number;
    on_chain:    boolean;
  };
  mode: "LIVE" | "SIMULATION";
}

/* ── Phase metadata ─────────────────────────────────────────────────────── */

const PHASES = [
  { n: 0,  icon: "💳", title: "Wallet Balance Check"          },
  { n: 1,  icon: "🏢", title: "Seed Demo Enterprises"         },
  { n: 2,  icon: "📡", title: "Register Discovery Agents"     },
  { n: 3,  icon: "🤝", title: "Capability Handshake"          },
  { n: 4,  icon: "📋", title: "Create Negotiation Session"    },
  { n: 5,  icon: "🤖", title: "Launch Autonomous Negotiation" },
  { n: 6,  icon: "⚡", title: "DANP-v1 Rounds in Progress"    },
  { n: 7,  icon: "🔗", title: "Deploy Algorand Escrow"        },
  { n: 8,  icon: "💰", title: "Fund Escrow Contract"          },
  { n: 9,  icon: "💳", title: "x402 Payment Delivery"         },
  { n: 10, icon: "✅", title: "Release Escrow to Seller"      },
  { n: 11, icon: "⚓", title: "Anchor Audit on Algorand"      },
  { n: 12, icon: "🎉", title: "Flow Complete"                 },
];

/* ── Sub-components ─────────────────────────────────────────────────────── */

function PhaseRow({ phase, event }: {
  phase: { n: number; icon: string; title: string };
  event?: PhaseEvent;
}) {
  const status = event?.status ?? "idle";

  return (
    <motion.div
      initial={{ opacity: 0, x: -12 }}
      animate={{ opacity: 1, x: 0 }}
      className={`flex items-start gap-4 rounded-xl border p-4 transition-colors duration-300
        ${status === "running" ? "border-blue-500/40  bg-blue-500/5"   : ""}
        ${status === "done"    ? "border-emerald-500/30 bg-emerald-500/5" : ""}
        ${status === "error"   ? "border-red-500/40   bg-red-500/5"    : ""}
        ${status === "idle"    ? "border-white/5      bg-white/[0.02]"  : ""}
      `}
    >
      {/* Status icon */}
      <div className="mt-0.5 shrink-0">
        {status === "idle"    && <Circle    className="h-5 w-5 text-zinc-600" />}
        {status === "running" && <Loader2   className="h-5 w-5 text-blue-400 animate-spin" />}
        {status === "done"    && <CheckCircle2 className="h-5 w-5 text-emerald-400" />}
        {status === "error"   && <XCircle   className="h-5 w-5 text-red-400" />}
      </div>

      {/* Content */}
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="text-base">{phase.icon}</span>
          <span className={`text-sm font-semibold
            ${status === "done"    ? "text-emerald-300" : ""}
            ${status === "running" ? "text-blue-300"    : ""}
            ${status === "error"   ? "text-red-300"     : ""}
            ${status === "idle"    ? "text-zinc-500"    : ""}
          `}>
            {event?.label ?? phase.title}
          </span>
        </div>

        {event?.detail && status !== "idle" && (
          <p className="mt-1 text-xs text-zinc-400 leading-relaxed">
            {event.detail}
          </p>
        )}

        {/* Phase-specific data renders */}
        {status === "done" && event?.data && (
          <PhaseDataDisplay phase={phase.n} data={event.data} />
        )}
      </div>
    </motion.div>
  );
}

function PhaseDataDisplay({
  phase, data,
}: { phase: number; data: Record<string, unknown> }) {

  if (phase === 6 && data.final_agreed_value) {
    return (
      <div className="mt-2 inline-flex items-center gap-2 rounded-lg
        bg-emerald-500/10 border border-emerald-500/20 px-3 py-1.5">
        <span className="text-xs text-zinc-400">Agreed price</span>
        <span className="text-sm font-bold text-emerald-300">
          ₹{Number(data.final_agreed_value).toLocaleString("en-IN")}
        </span>
      </div>
    );
  }

  if ([8, 9, 10, 11].includes(phase) && data.explorer_url) {
    return (
      <a
        href={data.explorer_url as string}
        target="_blank"
        rel="noopener noreferrer"
        className="mt-2 inline-flex items-center gap-1.5 text-xs text-blue-400
          hover:text-blue-300 transition-colors"
      >
        <ExternalLink className="h-3 w-3" />
        View on Lora Explorer
      </a>
    );
  }

  if (phase === 3) {
    return (
      <div className="mt-2 flex gap-2 flex-wrap">
        {data.selected_protocol && (
          <span className="rounded-full bg-blue-500/10 border border-blue-500/20
            px-2 py-0.5 text-xs text-blue-300">
            {String(data.selected_protocol)}
          </span>
        )}
        {data.selected_settlement && (
          <span className="rounded-full bg-purple-500/10 border border-purple-500/20
            px-2 py-0.5 text-xs text-purple-300">
            {String(data.selected_settlement)}
          </span>
        )}
      </div>
    );
  }

  return null;
}

function TxHash({ label, txId, explorerUrl }: {
  label: string; txId: string; explorerUrl: string | null;
}) {
  const short = txId?.length > 16
    ? `${txId.slice(0, 8)}…${txId.slice(-8)}`
    : txId;
  const isSimulated = txId?.startsWith("SIM");
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(txId);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <div className="flex items-center justify-between rounded-lg border
      border-white/5 bg-white/[0.03] p-3">
      <div>
        <p className="text-xs text-zinc-500 mb-0.5">{label}</p>
        <p className={`font-mono text-xs ${
          isSimulated ? "text-yellow-400" : "text-emerald-300"
        }`}>
          {short}
          {isSimulated && (
            <span className="ml-2 text-[10px] text-yellow-600">(simulated)</span>
          )}
        </p>
      </div>
      <div className="flex items-center gap-2">
        <button
          onClick={handleCopy}
          className="rounded p-1.5 text-zinc-500 hover:text-zinc-300
            hover:bg-white/5 transition-colors"
          title="Copy TX hash"
        >
          {copied ? (
            <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />
          ) : (
            <Copy className="h-3.5 w-3.5" />
          )}
        </button>
        {explorerUrl && !isSimulated && (
          <a
            href={explorerUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="rounded p-1.5 text-blue-400 hover:text-blue-300
              hover:bg-blue-500/10 transition-colors"
          >
            <ExternalLink className="h-3.5 w-3.5" />
          </a>
        )}
      </div>
    </div>
  );
}

function SummaryPanel({ summary }: { summary: DemoSummary }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="mt-8 rounded-2xl border border-emerald-500/20
        bg-gradient-to-b from-emerald-500/5 to-transparent p-6 space-y-6"
    >
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h3 className="text-lg font-bold text-emerald-300">
            Flow Complete
          </h3>
          <p className="text-sm text-zinc-400 mt-0.5">
            Full negotiation → escrow → settlement →
            audit anchored {summary.mode === "LIVE"
              ? "LIVE on Algorand testnet"
              : "in simulation mode"}
          </p>
        </div>
        <span className={`rounded-full px-3 py-1 text-xs font-semibold
          ${summary.mode === "LIVE"
            ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30"
            : "bg-yellow-500/20 text-yellow-300 border border-yellow-500/30"
          }`}>
          {summary.mode}
        </span>
      </div>

      {/* Key metrics */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {[
          { label: "Agreed Price",    value: `₹${Number(summary.agreed_value_inr).toLocaleString("en-IN")}` },
          { label: "Contract Ref",    value: summary.escrow.contract_ref ? `${String(summary.escrow.contract_ref).slice(0, 12)}…` : "—" },
          { label: "Audit Events",    value: `${summary.audit.leaf_count} events` },
          { label: "On-Chain Anchor", value: summary.audit.on_chain ? "✅ Yes" : "Simulated" },
        ].map(({ label, value }) => (
          <div key={label}
            className="rounded-lg border border-white/5 bg-white/[0.03] p-3">
            <p className="text-xs text-zinc-500">{label}</p>
            <p className="text-sm font-semibold text-white mt-0.5">{value}</p>
          </div>
        ))}
      </div>

      {/* Transaction hashes */}
      <div>
        <h4 className="text-xs font-semibold text-zinc-400 uppercase
          tracking-wider mb-3">
          Algorand Transaction Hashes
        </h4>
        <div className="space-y-2">
          <TxHash label="Escrow Funded"
            txId={summary.transactions.fund_tx_id}
            explorerUrl={summary.explorer_links.fund} />
          <TxHash label="x402 Payment"
            txId={summary.transactions.payment_tx_id}
            explorerUrl={summary.explorer_links.payment} />
          <TxHash label="Escrow Released"
            txId={summary.transactions.release_tx_id}
            explorerUrl={summary.explorer_links.release} />
          <TxHash label="Merkle Root Anchored"
            txId={summary.transactions.anchor_tx_id}
            explorerUrl={summary.explorer_links.anchor} />
        </div>
      </div>

      {/* Merkle root */}
      <div className="rounded-lg border border-white/5 bg-white/[0.03] p-3">
        <p className="text-xs text-zinc-500 mb-1">SHA-256 Merkle Root</p>
        <p className="font-mono text-xs text-zinc-300 break-all">
          {summary.audit.merkle_root}
        </p>
      </div>

      {/* Actions */}
      <div className="flex flex-wrap gap-3 pt-2">
        <Link
          href={`/dashboard/sessions/${summary.session_id}`}
          className="inline-flex items-center gap-2 rounded-lg bg-white/5
            border border-white/10 px-4 py-2 text-sm text-zinc-300
            hover:bg-white/10 transition-colors"
        >
          View Session <ArrowRight className="h-4 w-4" />
        </Link>
        <Link
          href={`/dashboard/audit`}
          className="inline-flex items-center gap-2 rounded-lg bg-white/5
            border border-white/10 px-4 py-2 text-sm text-zinc-300
            hover:bg-white/10 transition-colors"
        >
          Audit Trail <Shield className="h-4 w-4" />
        </Link>
        {summary.explorer_links.anchor && (
          <a
            href={summary.explorer_links.anchor}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-2 rounded-lg
              bg-blue-500/10 border border-blue-500/20 px-4 py-2
              text-sm text-blue-300 hover:bg-blue-500/20 transition-colors"
          >
            Lora Explorer <ExternalLink className="h-4 w-4" />
          </a>
        )}
      </div>
    </motion.div>
  );
}

/* ── Main Page ──────────────────────────────────────────────────────────── */

export default function DemoPage() {
  const [phases, setPhases] = useState<Map<number, PhaseEvent>>(new Map());
  const [running, setRunning]   = useState(false);
  const [finished, setFinished] = useState(false);
  const [summary, setSummary]   = useState<DemoSummary | null>(null);
  const [error, setError]       = useState<string | null>(null);
  const [isLiveMode, setIsLiveMode] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    fetch("/api/demo/mode")
      .then(r => r.json())
      .then(d => setIsLiveMode(d.is_live ?? false))
      .catch(() => setIsLiveMode(false));
  }, []);

  const runDemo = useCallback(async () => {
    setPhases(new Map());
    setFinished(false);
    setSummary(null);
    setError(null);
    setRunning(true);

    abortRef.current = new AbortController();

    try {
      const res = await fetch("/api/demo/run", {
        signal: abortRef.current.signal,
      });

      if (!res.ok || !res.body) {
        throw new Error(`Failed to start demo: ${res.status}`);
      }

      const reader  = res.body.getReader();
      const decoder = new TextDecoder();
      let   buffer  = "";

      // eslint-disable-next-line no-constant-condition
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n\n");
        buffer = lines.pop() ?? "";

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          try {
            const event: PhaseEvent = JSON.parse(line.slice(6));
            setPhases(prev => new Map(prev).set(event.phase, event));

            if (event.phase === 12 && event.status === "done") {
              setSummary(event.data.summary as DemoSummary);
              setFinished(true);
            }
            if (event.status === "error") {
              setError(event.detail);
            }
          } catch {
            // malformed SSE line — skip
          }
        }
      }
    } catch (err: unknown) {
      if ((err as Error).name !== "AbortError") {
        setError((err as Error).message);
      }
    } finally {
      setRunning(false);
    }
  }, []);

  const stopDemo = useCallback(() => {
    abortRef.current?.abort();
    setRunning(false);
  }, []);

  const currentPhase = Array.from(phases.values())
    .filter(e => e.status === "running")
    .pop()?.phase ?? 0;

  return (
    <div className="min-h-screen bg-[#0a0a0f] text-white">
      {/* Top nav bar for demo page */}
      <nav className="sticky top-0 z-50 border-b border-zinc-800 bg-zinc-950/80 backdrop-blur-md">
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-6">
          <Link
            href="/"
            className="flex items-center gap-2.5 text-lg font-bold tracking-tight text-white transition-colors hover:text-emerald-400"
          >
            <div className="flex h-8 w-8 items-center justify-center rounded-md bg-emerald-500">
              <span className="text-sm font-black text-black">A2</span>
            </div>
            <span>A2A Treasury</span>
          </Link>
          <div className="flex items-center gap-3">
            <Link
              href="/dashboard"
              className="rounded-lg px-4 py-2 text-sm font-medium text-zinc-300 transition-colors hover:text-white"
            >
              Dashboard
            </Link>
            <Link
              href="/auth/login"
              className="rounded-lg px-4 py-2 text-sm font-medium text-zinc-300 transition-colors hover:text-white"
            >
              Sign In
            </Link>
          </div>
        </div>
      </nav>

      <div className="max-w-3xl mx-auto px-4 py-16 space-y-8">

        {/* Header */}
        <div className="text-center space-y-4">
          <div className="inline-flex items-center gap-2 rounded-full
            border border-blue-500/30 bg-blue-500/10 px-4 py-1.5
            text-sm text-blue-300">
            <Zap className="h-3.5 w-3.5" />
            AlgoBharat Hack Series 3.0 — Live Demo
          </div>
          <h1 className="text-4xl font-bold tracking-tight bg-gradient-to-r from-white via-zinc-200 to-zinc-400 bg-clip-text text-transparent">
            A2A Treasury Network
          </h1>
          <p className="text-zinc-400 max-w-xl mx-auto leading-relaxed">
            Watch two AI agents discover each other, negotiate a price
            autonomously, deploy an Algorand smart contract, and settle
            payment via x402 — all triggered by a single button click.
          </p>
        </div>

        {/* Flow diagram (pre-run) */}
        {!running && !finished && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="flex items-center justify-center gap-1
              flex-wrap text-xs text-zinc-500"
          >
            {[
              "Discovery", "Handshake", "Negotiate",
              "Escrow", "x402 Pay", "Anchor",
            ].map((step, i, arr) => (
              <span key={step} className="flex items-center gap-1">
                <span className="rounded-full bg-white/5 border
                  border-white/10 px-2.5 py-1">
                  {step}
                </span>
                {i < arr.length - 1 && (
                  <ChevronRight className="h-3 w-3 text-zinc-700" />
                )}
              </span>
            ))}
          </motion.div>
        )}

        {/* Mode indicator */}
        <div className="flex justify-center">
          <div className={`inline-flex items-center gap-2 rounded-full px-4 py-1.5
            text-xs font-medium border
            ${isLiveMode
              ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-300"
              : "bg-yellow-500/10 border-yellow-500/30 text-yellow-300"
            }`}>
            <span className={`h-1.5 w-1.5 rounded-full ${
              isLiveMode ? "bg-emerald-400 animate-pulse" : "bg-yellow-400"
            }`} />
            {isLiveMode ? "LIVE — Algorand Testnet" : "Simulation Mode"}
          </div>
        </div>

        {/* Run button */}
        <div className="flex justify-center">
          {!running ? (
            <button
              onClick={runDemo}
              disabled={running}
              className="group relative inline-flex items-center gap-3
                rounded-2xl bg-gradient-to-r from-blue-600 to-blue-500
                px-8 py-4 text-base font-semibold text-white shadow-lg
                shadow-blue-500/25 hover:shadow-blue-500/40
                hover:from-blue-500 hover:to-blue-400
                transition-all duration-200 active:scale-95"
            >
              <Zap className="h-5 w-5" />
              {finished ? "Run Demo Again" : "Run Full Demo Flow"}
              <span className="absolute inset-0 rounded-2xl ring-2
                ring-blue-400/0 group-hover:ring-blue-400/30
                transition-all duration-200" />
            </button>
          ) : (
            <button
              onClick={stopDemo}
              className="inline-flex items-center gap-2 rounded-2xl
                border border-red-500/30 bg-red-500/10 px-6 py-3
                text-sm text-red-400 hover:bg-red-500/20 transition-colors"
            >
              <XCircle className="h-4 w-4" />
              Stop Demo
            </button>
          )}
        </div>

        {/* Progress indicator */}
        {(running || finished) && (
          <div className="space-y-1">
            <div className="flex justify-between text-xs text-zinc-500 mb-2">
              <span>
                Phase {Math.min(currentPhase || phases.size, 13)} of 13
              </span>
              <span>
                {finished
                  ? "Complete"
                  : `${Math.round(((phases.size) / 13) * 100)}%`}
              </span>
            </div>
            <div className="h-1 w-full rounded-full bg-white/5">
              <motion.div
                className="h-full rounded-full bg-gradient-to-r
                  from-blue-500 to-emerald-500"
                animate={{
                  width: `${Math.round((phases.size / 13) * 100)}%`,
                }}
                transition={{ duration: 0.3 }}
              />
            </div>
          </div>
        )}

        {/* Phase list */}
        <AnimatePresence mode="popLayout">
          {(running || finished) && (
            <div className="space-y-2">
              {PHASES.map(phase => (
                <PhaseRow
                  key={phase.n}
                  phase={phase}
                  event={phases.get(phase.n)}
                />
              ))}
            </div>
          )}
        </AnimatePresence>

        {/* Error state */}
        {error && !running && (
          <div className="rounded-xl border border-red-500/30
            bg-red-500/10 p-4 text-sm text-red-300">
            <p className="font-semibold mb-1">Demo encountered an error</p>
            <p className="text-xs text-red-400">{error}</p>
            <p className="text-xs text-zinc-500 mt-2">
              Check that the backend is running and Algorand testnet
              wallets are funded. You can re-try by clicking the button above.
            </p>
          </div>
        )}

        {/* Summary panel */}
        {summary && <SummaryPanel summary={summary} />}

      </div>
    </div>
  );
}
