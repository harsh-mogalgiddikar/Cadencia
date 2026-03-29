/* ───────────────────────────────────────────────────────────
 * types/api.ts — Shared TypeScript interfaces for backend API
 * ──────────────────────────────────────────────────────────── */

// ── Negotiation FSM states ─────────────────────────────────
export type NegotiationStatus =
  | "INIT"
  | "BUYER_ANCHOR"
  | "SELLER_RESPONSE"
  | "ROUND_LOOP"
  | "AGREED"
  | "WALKAWAY"
  | "TIMEOUT"
  | "STALLED"
  | "POLICY_BREACH"
  | "ROUND_LIMIT";

export const TERMINAL_STATES: NegotiationStatus[] = [
  "AGREED",
  "WALKAWAY",
  "TIMEOUT",
  "STALLED",
  "POLICY_BREACH",
  "ROUND_LIMIT",
];

// ── Session ────────────────────────────────────────────────
export interface SessionStatus {
  session_id: string;
  status: NegotiationStatus;
  current_round: number;
  max_rounds: number;
  timeout_at: string;
  is_terminal: boolean;
  outcome: string | null;
  final_agreed_value: number | null;
   expected_turn?: "buyer" | "seller" | null;
}

export interface SessionListResponse {
  items: SessionStatus[];
  total: number;
  page: number;
}

export interface CreateSessionPayload {
  seller_enterprise_id: string;
  initial_offer_value: number;
  timeout_seconds?: number;
  max_rounds?: number;
  milestone_template_id?: string;
}

// ── Offer ──────────────────────────────────────────────────
export interface OfferDetail {
  offer_id: string;
  agent_role: "buyer" | "seller";
  value: number | null;
  action: string;
  round: number;
  confidence: number | null;
  strategy_tag: string;
  timestamp: string;
}

export interface OfferListResponse {
  session_id: string;
  offers: OfferDetail[];
}

// ── Escrow ─────────────────────────────────────────────────
export type EscrowStatus =
  | "PENDING"
  | "DEPLOYED"
  | "FUNDED"
  | "RELEASED"
  | "REFUNDED";

export interface EscrowContract {
  escrow_id: string;
  session_id: string;
  contract_ref: string;
  network_id: string;
  amount: number | null;
  status: EscrowStatus;
  deployed_at: string | null;
  tx_ref: string | null;
}

export interface EscrowOnChainStatus {
  escrow_id: string;
  contract_ref: string;
  status: string;
  on_chain_balance_usdc: number;
  agreed_amount_usdc: number;
  balance_verified: boolean;
  sdk_available: boolean;
  explorer_url: string;
}

// ── Audit ──────────────────────────────────────────────────
export interface AuditEntry {
  log_id: string;
  entity_type: string;
  entity_id: string;
  action: string;
  actor_id: string;
  prev_hash: string;
  this_hash: string;
  payload: Record<string, unknown>;
  timestamp: string;
}

export interface MerkleInfo {
  session_id: string;
  merkle_root: string;
  leaf_count: number;
  anchor_tx_id: string | null;
  anchored_on_chain: boolean;
  verification_url: string | null;
}

export interface ChainVerification {
  valid: boolean;
  entries_checked: number;
  broken_link_at: number | null;
}

// ── Compliance ─────────────────────────────────────────────
export type ComplianceStatus = "APPROVED" | "COMPLIANT" | "WARNING" | "BLOCKED" | "NON_COMPLIANT" | "EXEMPT";

export interface ComplianceRecord {
  session_id: string;
  purpose_code: string;
  transaction_type: string;
  inr_amount: number;
  usdc_amount: number;
  limit_utilization_pct: number;
  status: ComplianceStatus;
  warnings: string[];
  blocking_reasons: string[];
}

// ── FX ─────────────────────────────────────────────────────
export interface FxQuote {
  quote_id: string;
  mid_rate: number;
  buy_rate: number;
  sell_rate: number;
  spread_bps: number;
  source: string;
  fetched_at: string;
  expires_at: string;
}

// ── Treasury ───────────────────────────────────────────────
export interface PlatformSummary {
  total_sessions: number;
  active_sessions: number;
  agreed_sessions: number;
  total_escrow_value_inr: number;
  total_escrow_value_usdc: number;
  compliance_rate: number;
  avg_rounds_to_agreement: number;
  walkaway_rate: number;
}

export interface EnterpriseSummary {
  enterprise_id: string;
  total_sessions: number;
  as_buyer: number;
  as_seller: number;
  total_value_inr: number;
  total_value_usdc: number;
  avg_agreed_value: number;
  win_rate: number;
}

// ── Registry / Handshake ───────────────────────────────────
export interface AgentCardSummary {
  enterprise_id: string;
  legal_name: string;
  agent_role: string;
  protocols: { id: string }[];
  settlement_networks: string[];
  capabilities: string[];
}

export interface HandshakeResult {
  handshake_id: string;
  compatible: boolean;
  shared_protocols: string[];
  shared_settlement_networks: string[];
  incompatibility_reasons: string[];
  selected_protocol: string | null;
  selected_settlement: string | null;
}

// ── Enterprise ─────────────────────────────────────────────
export interface EnterpriseDetail {
  enterprise_id: string;
  legal_name: string;
  pan: string | null;
  gst: string | null;
  kyc_status: string;
  wallet_address: string | null;
  agent_card_url: string | null;
  created_at: string;
  role?: string;
  agent_card_data?: Record<string, unknown>;
}

// ── Agent Config ───────────────────────────────────────────
export interface AgentConfig {
  config_id: string;
  enterprise_id: string;
  agent_role: string;
  intrinsic_value: number;
  risk_factor: number;
  negotiation_margin: number;
  concession_curve: Record<string, unknown>;
  budget_ceiling: number | null;
  max_exposure: number;
  strategy_default: string;
  max_rounds: number;
  timeout_seconds: number;
}
