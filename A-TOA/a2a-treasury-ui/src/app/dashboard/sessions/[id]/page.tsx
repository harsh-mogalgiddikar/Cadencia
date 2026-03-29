"use client";

import { useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { motion, AnimatePresence } from "framer-motion";
import {
  ArrowLeft,
  RefreshCw,
  ExternalLink,
  ShieldCheck,
  Hash,
  Clock,
  Loader2,
  AlertTriangle,
  Check,
} from "lucide-react";
import {
  useSessionStatus,
  useSessionOffers,
  useEscrowBySession,
  useMerkleRoot,
  useFxRate,
  apiPost,
} from "@/hooks/useApi";
import { formatINR, timeAgo, cn } from "@/lib/utils";
import StatusBadge from "@/components/ui/StatusBadge";
import CopyButton from "@/components/ui/CopyButton";
import ApiError from "@/components/ui/ApiError";
import { CardSkeleton } from "@/components/ui/Skeleton";
import type {
  SessionStatus,
  OfferDetail,
  OfferListResponse,
  EscrowContract,
  MerkleInfo,
  FxQuote,
} from "@/types/api";

const LIVE_STATES = ["INIT", "BUYER_ANCHOR", "SELLER_RESPONSE", "ROUND_LOOP"];

export default function SessionDetailPage() {
  const params = useParams();
  const id = params.id as string;
  const scrollRef = useRef<HTMLDivElement>(null);
  const [prevOfferCount, setPrevOfferCount] = useState(0);

  const { data: statusData, error: statusErr, isLoading: statusLoading } = useSessionStatus(id);
  const { data: offersData, error: offersErr } = useSessionOffers(id);
  const { data: escrowData } = useEscrowBySession(id);
  const { data: merkleData } = useMerkleRoot(id);
  const { data: fxData } = useFxRate();

  const session = statusData as SessionStatus | undefined;
  const offers = (offersData as OfferListResponse)?.offers ?? [];
  const escrow = escrowData as EscrowContract | undefined;
  const merkle = merkleData as MerkleInfo | undefined;
  const fx = fxData as FxQuote | undefined;
  const isLive = session && LIVE_STATES.includes(session.status);

  // Auto-scroll on new offers
  useEffect(() => {
    if (offers.length > prevOfferCount) {
      scrollRef.current?.scrollTo({
        top: scrollRef.current.scrollHeight,
        behavior: "smooth",
      });
      setPrevOfferCount(offers.length);
    }
  }, [offers.length, prevOfferCount]);

  // Escrow actions
  const [escrowAction, setEscrowAction] = useState<string | null>(null);
  const handleEscrowAction = async (action: "fund" | "release" | "refund") => {
    if (!escrow) return;
    const confirmed = confirm(`Are you sure you want to ${action} this escrow? This action cannot be undone.`);
    if (!confirmed) return;
    setEscrowAction(action);
    try {
      if (action === "release") {
        await apiPost(`/escrow/${escrow.escrow_id}/release`, {
          milestone: "milestone-1",
        });
      } else if (action === "refund") {
        await apiPost(`/escrow/${escrow.escrow_id}/refund`, {
          reason: "Dispute — refund",
        });
      } else {
        await apiPost(`/escrow/${escrow.escrow_id}/fund`);
      }
    } catch {
      alert(`Failed to ${action} escrow`);
    } finally {
      setEscrowAction(null);
    }
  };

  if (statusLoading) {
    return (
      <div className="mx-auto max-w-6xl space-y-6">
        <CardSkeleton />
        <div className="grid gap-6 lg:grid-cols-5">
          <div className="lg:col-span-3">
            <CardSkeleton />
          </div>
          <div className="lg:col-span-2">
            <CardSkeleton />
          </div>
        </div>
      </div>
    );
  }

  if (statusErr) {
    return (
      <div className="mx-auto max-w-6xl">
        <ApiError error={statusErr} />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      {/* Header */}
      <div className="flex flex-wrap items-center gap-4">
        <Link
          href="/dashboard/sessions"
          className="flex items-center gap-1 text-sm text-zinc-400 hover:text-zinc-300"
        >
          <ArrowLeft className="h-4 w-4" />
          Sessions
        </Link>
        <div className="flex items-center gap-3">
          <CopyButton text={id} truncate={16} />
          {session && <StatusBadge status={session.status} pulse={isLive} />}
        </div>
        {isLive && (
          <span className="ml-auto flex items-center gap-1.5 text-sm text-emerald-400">
            <span className="relative flex h-2 w-2">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
              <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-500" />
            </span>
            LIVE — Agents negotiating...
          </span>
        )}
      </div>

      {/* Info bar */}
      {session && (
        <div className="flex flex-wrap items-center gap-4 rounded-lg border border-zinc-800 bg-zinc-900 px-4 py-2.5 text-sm text-zinc-400">
          <span>
            Round: {session.current_round}/{session.max_rounds}
          </span>
          <span className="text-zinc-600">·</span>
          <span>
            Timeout: {timeAgo(session.timeout_at)}
          </span>
          {fx && (
            <>
              <span className="text-zinc-600">·</span>
              <span>FX: ₹{fx.mid_rate?.toFixed(2)}/USD</span>
            </>
          )}
          {session.final_agreed_value && (
            <>
              <span className="text-zinc-600">·</span>
              <span className="font-medium text-emerald-400">
                Agreed: {formatINR(session.final_agreed_value)}
              </span>
            </>
          )}
        </div>
      )}

      {/* Main content */}
      <div className="grid gap-6 lg:grid-cols-5">
        {/* Left: Offer Timeline */}
        <div className="lg:col-span-3">
          <div className="rounded-xl border border-zinc-800 bg-zinc-900">
            <div className="border-b border-zinc-800 px-4 py-3">
              <h3 className="font-semibold text-zinc-50">
                Negotiation Transcript
              </h3>
            </div>
            <div
              ref={scrollRef}
              className="max-h-[600px] overflow-y-auto p-4 space-y-3"
            >
              {offersErr ? (
                <ApiError error={offersErr} />
              ) : offers.length === 0 ? (
                <div className="py-12 text-center text-zinc-500">
                  {isLive
                    ? "Waiting for first offer..."
                    : "No offers recorded"}
                </div>
              ) : (
                <AnimatePresence initial={false}>
                  {offers.map((offer: OfferDetail, idx: number) => {
                    const isBuyer = offer.agent_role === "buyer";
                    const isAccept = offer.action === "accept";
                    const isReject =
                      offer.action === "reject" ||
                      offer.action === "walkaway";

                    if (isAccept) {
                      return (
                        <motion.div
                          key={offer.offer_id || idx}
                          initial={{ opacity: 0, y: 12 }}
                          animate={{ opacity: 1, y: 0 }}
                          transition={{ duration: 0.3 }}
                          className="rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-4 py-3 text-center"
                        >
                          <p className="font-semibold text-emerald-400">
                            ✅ {offer.agent_role.toUpperCase()} ACCEPTED{" "}
                            {offer.value
                              ? formatINR(offer.value)
                              : ""}{" "}
                            — Deal Agreed!
                          </p>
                        </motion.div>
                      );
                    }

                    if (isReject) {
                      return (
                        <motion.div
                          key={offer.offer_id || idx}
                          initial={{ opacity: 0, y: 12 }}
                          animate={{ opacity: 1, y: 0 }}
                          transition={{ duration: 0.3 }}
                          className="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-center"
                        >
                          <p className="font-medium text-red-400">
                            ❌ {offer.agent_role.toUpperCase()} walked away
                          </p>
                        </motion.div>
                      );
                    }

                    return (
                      <motion.div
                        key={offer.offer_id || idx}
                        initial={{ opacity: 0, y: 12 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ duration: 0.3 }}
                        className={cn(
                          "rounded-lg border-l-4 bg-zinc-800 p-3",
                          isBuyer
                            ? "border-emerald-500 mr-12"
                            : "border-cyan-400 ml-12",
                        )}
                      >
                        <div className="flex items-center justify-between text-xs text-zinc-500">
                          <span>
                            Round {offer.round} · {offer.agent_role.toUpperCase()}
                          </span>
                          <span className="uppercase tracking-wider">
                            {offer.action}
                          </span>
                        </div>
                        <p className="mt-1 text-xl font-bold text-zinc-50">
                          {offer.value ? formatINR(offer.value) : "—"}
                        </p>
                        <div className="mt-1 flex items-center gap-3 text-xs text-zinc-500">
                          {offer.confidence !== null && (
                            <span>
                              Confidence: {(offer.confidence * 100).toFixed(0)}%
                            </span>
                          )}
                          {offer.strategy_tag && (
                            <span>Strategy: {offer.strategy_tag}</span>
                          )}
                        </div>
                      </motion.div>
                    );
                  })}
                </AnimatePresence>
              )}

              {isLive && offers.length > 0 && (
                <div className="flex items-center justify-center gap-2 py-3 text-sm text-zinc-500">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Waiting for next offer...
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Right: Details Panel */}
        <div className="space-y-4 lg:col-span-2">
          {/* Escrow */}
          <div className="rounded-xl border border-zinc-800 bg-zinc-900 p-4">
            <h4 className="mb-3 flex items-center gap-2 text-sm font-semibold text-zinc-300">
              <ShieldCheck className="h-4 w-4 text-emerald-500" />
              Escrow
            </h4>
            {escrow ? (
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-zinc-500">Status</span>
                  <StatusBadge status={escrow.status} kind="escrow" />
                </div>
                <div className="flex justify-between">
                  <span className="text-zinc-500">Amount</span>
                  <span className="text-zinc-50">
                    {escrow.amount ? `${escrow.amount.toFixed(2)} USDC` : "—"}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-zinc-500">Contract</span>
                  <CopyButton
                    text={escrow.contract_ref || "—"}
                    truncate={16}
                  />
                </div>
                {escrow.tx_ref && (
                  <a
                    href={`https://lora.algokit.io/testnet/transaction/${escrow.tx_ref}`}
                    target="_blank"
                    rel="noreferrer"
                    className="flex items-center gap-1 text-xs text-cyan-400 hover:text-cyan-300"
                  >
                    View on Explorer
                    <ExternalLink className="h-3 w-3" />
                  </a>
                )}
                {/* Actions */}
                {session?.status === "AGREED" && (
                  <div className="mt-3 flex gap-2">
                    {escrow.status === "DEPLOYED" && (
                      <button
                        onClick={() => handleEscrowAction("fund")}
                        disabled={escrowAction !== null}
                        className="flex-1 rounded-lg bg-amber-500 px-3 py-1.5 text-xs font-semibold text-black hover:bg-amber-600 disabled:opacity-50"
                      >
                        {escrowAction === "fund" ? "..." : "Fund"}
                      </button>
                    )}
                    {escrow.status === "FUNDED" && (
                      <>
                        <button
                          onClick={() => handleEscrowAction("release")}
                          disabled={escrowAction !== null}
                          className="flex-1 rounded-lg bg-emerald-500 px-3 py-1.5 text-xs font-semibold text-black hover:bg-emerald-600 disabled:opacity-50"
                        >
                          {escrowAction === "release" ? "..." : "Release"}
                        </button>
                        <button
                          onClick={() => handleEscrowAction("refund")}
                          disabled={escrowAction !== null}
                          className="flex-1 rounded-lg bg-red-500/80 px-3 py-1.5 text-xs font-semibold text-white hover:bg-red-500 disabled:opacity-50"
                        >
                          {escrowAction === "refund" ? "..." : "Refund"}
                        </button>
                      </>
                    )}
                  </div>
                )}
              </div>
            ) : (
              <p className="text-sm text-zinc-500">No escrow deployed yet</p>
            )}
          </div>

          {/* Audit Summary */}
          <div className="rounded-xl border border-zinc-800 bg-zinc-900 p-4">
            <h4 className="mb-3 flex items-center gap-2 text-sm font-semibold text-zinc-300">
              <Hash className="h-4 w-4 text-cyan-400" />
              Audit Trail
            </h4>
            {merkle ? (
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-zinc-500">Leaf Count</span>
                  <span className="text-zinc-50">{merkle.leaf_count}</span>
                </div>
                <div>
                  <span className="text-xs text-zinc-500">Merkle Root</span>
                  <p className="mt-0.5 break-all font-mono text-xs text-cyan-400">
                    {merkle.merkle_root}
                  </p>
                </div>
                {merkle.anchor_tx_id && (
                  <div className="flex items-center gap-2">
                    {merkle.anchored_on_chain ? (
                      <Check className="h-3.5 w-3.5 text-emerald-400" />
                    ) : (
                      <AlertTriangle className="h-3.5 w-3.5 text-amber-400" />
                    )}
                    <span className="text-xs text-zinc-400">
                      {merkle.anchored_on_chain
                        ? "Anchored on-chain"
                        : "Simulated anchor"}
                    </span>
                  </div>
                )}
                <Link
                  href={`/dashboard/audit/${id}`}
                  className="flex items-center gap-1 text-xs text-emerald-500 hover:text-emerald-400"
                >
                  View Full Audit Trail →
                </Link>
              </div>
            ) : (
              <p className="text-sm text-zinc-500">
                Merkle root pending or session in progress
              </p>
            )}
          </div>

          {/* Session Metadata */}
          <div className="rounded-xl border border-zinc-800 bg-zinc-900 p-4">
            <h4 className="mb-3 flex items-center gap-2 text-sm font-semibold text-zinc-300">
              <Clock className="h-4 w-4 text-zinc-400" />
              Session Info
            </h4>
            {session && (
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-zinc-500">Round</span>
                  <span className="text-zinc-50">
                    {session.current_round} / {session.max_rounds}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-zinc-500">Terminal</span>
                  <span className="text-zinc-50">
                    {session.is_terminal ? "Yes" : "No"}
                  </span>
                </div>
                {session.outcome && (
                  <div className="flex justify-between">
                    <span className="text-zinc-500">Outcome</span>
                    <span className="text-zinc-50">{session.outcome}</span>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
