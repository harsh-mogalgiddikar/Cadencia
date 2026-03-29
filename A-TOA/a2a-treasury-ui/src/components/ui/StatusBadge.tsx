import type { NegotiationStatus, EscrowStatus, ComplianceStatus } from "@/types/api";

const negotiationConfig: Record<string, { color: string; label: string }> = {
  INIT:            { color: "zinc",    label: "Initializing" },
  BUYER_ANCHOR:    { color: "blue",    label: "Buyer Anchored" },
  SELLER_RESPONSE: { color: "purple",  label: "Seller Responding" },
  ROUND_LOOP:      { color: "amber",   label: "Negotiating" },
  AGREED:          { color: "emerald", label: "✅ Agreed" },
  WALKAWAY:        { color: "red",     label: "❌ Walkaway" },
  TIMEOUT:         { color: "orange",  label: "⏰ Timeout" },
  STALLED:         { color: "yellow",  label: "Stalled" },
  POLICY_BREACH:   { color: "red",     label: "🚨 Policy Breach" },
  ROUND_LIMIT:     { color: "orange",  label: "Round Limit" },
};

const escrowConfig: Record<string, { color: string; label: string }> = {
  PENDING:  { color: "zinc",    label: "Pending" },
  DEPLOYED: { color: "blue",    label: "Deployed" },
  FUNDED:   { color: "amber",   label: "Funded" },
  RELEASED: { color: "emerald", label: "Released" },
  REFUNDED: { color: "red",     label: "Refunded" },
};

const complianceConfig: Record<string, { color: string; label: string }> = {
  APPROVED:       { color: "emerald", label: "Approved" },
  COMPLIANT:      { color: "emerald", label: "Compliant" },
  WARNING:        { color: "amber",   label: "Warning" },
  BLOCKED:        { color: "red",     label: "Blocked" },
  NON_COMPLIANT:  { color: "red",     label: "Non-Compliant" },
  EXEMPT:         { color: "zinc",    label: "Exempt" },
};

const colorMap: Record<string, string> = {
  zinc:    "bg-zinc-500/10 text-zinc-400 border-zinc-500/30",
  blue:    "bg-blue-500/10 text-blue-400 border-blue-500/30",
  purple:  "bg-purple-500/10 text-purple-400 border-purple-500/30",
  amber:   "bg-amber-500/10 text-amber-400 border-amber-500/30",
  emerald: "bg-emerald-500/10 text-emerald-400 border-emerald-500/30",
  red:     "bg-red-500/10 text-red-400 border-red-500/30",
  orange:  "bg-orange-500/10 text-orange-400 border-orange-500/30",
  yellow:  "bg-yellow-500/10 text-yellow-400 border-yellow-500/30",
  cyan:    "bg-cyan-500/10 text-cyan-400 border-cyan-500/30",
};

interface Props {
  status: NegotiationStatus | EscrowStatus | ComplianceStatus | string;
  kind?: "negotiation" | "escrow" | "compliance";
  pulse?: boolean;
}

export default function StatusBadge({ status, kind = "negotiation", pulse }: Props) {
  const config =
    kind === "escrow"
      ? escrowConfig
      : kind === "compliance"
      ? complianceConfig
      : negotiationConfig;
  const entry = config[status] || { color: "zinc", label: status };
  const colors = colorMap[entry.color] || colorMap.zinc;
  const shouldPulse = pulse || (kind === "negotiation" && status === "ROUND_LOOP");

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium ${colors}`}
    >
      {shouldPulse && (
        <span className="relative flex h-2 w-2">
          <span className={`absolute inline-flex h-full w-full animate-ping rounded-full opacity-75 ${entry.color === "amber" ? "bg-amber-400" : entry.color === "emerald" ? "bg-emerald-400" : "bg-blue-400"}`} />
          <span className={`relative inline-flex h-2 w-2 rounded-full ${entry.color === "amber" ? "bg-amber-500" : entry.color === "emerald" ? "bg-emerald-500" : "bg-blue-500"}`} />
        </span>
      )}
      {entry.label}
    </span>
  );
}
