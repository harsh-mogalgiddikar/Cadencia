export interface Enterprise {
    enterprise_id: string;
    legal_name: string;
    pan?: string;
    gst?: string;
    email: string;
    wallet_address?: string;
    kyc_status: "PENDING" | "EMAIL_VERIFIED" | "ACTIVE";
    agent_card_url?: string;
    agent_card_data?: AgentCard;
}

export interface AgentCard {
    name: string;
    version: string;
    role: "buyer" | "seller";
    protocols: { id: string }[];
    settlement_networks: string[];
    payment_methods: string[];
    policy_constraints: {
        max_transaction_inr: number;
        requires_escrow: boolean;
        compliance_frameworks: string[];
    };
    framework: {
        name: string;
        version: string;
    };
}

export interface RegistryAgent {
    enterprise_id: string;
    legal_name: string;
    description: string;
    service_tags: string[];
    protocol: string;
    settlement_network: string;
    payment_method: string;
    availability: "active" | "busy" | "inactive";
    registered_at: string;
}

export interface Handshake {
    handshake_id: string;
    compatible: boolean;
    selected_protocol: string;
    selected_settlement: string;
    shared_protocols: string[];
    shared_settlement_networks: string[];
    incompatibility_reasons: string[];
    expires_at: string;
}

export interface NegotiationSession {
    session_id: string;
    status: string;
    current_round: number;
    max_rounds?: number;
    timeout_at: string;
    is_terminal: boolean;
    outcome?: string;
    final_agreed_value?: number;
    buyer_enterprise_id?: string;
    seller_enterprise_id?: string;
    created_at?: string;
}

export interface NegotiationRound {
    round_number: number;
    actor: "buyer" | "seller";
    action: "COUNTER" | "ACCEPT" | "REJECT" | "counter" | "accept" | "reject";
    offer_amount: number;
    timestamp: string;
}

export interface OfferDetail {
    offer_id: string;
    agent_role: string;
    value?: number;
    action: string;
    round: number;
    confidence?: number;
    strategy_tag?: string;
    timestamp: string;
}

export interface AuditEntry {
    sequence: number;
    action: string;
    actor_id: string;
    payload: Record<string, unknown>;
    this_hash: string;
    prev_hash: string;
    timestamp: string;
}

export interface MerkleData {
    session_id: string;
    merkle_root: string;
    leaf_count: number;
    anchor_tx_id: string | null;
    anchored_on_chain: boolean;
    verification_url?: string;
}

export interface EscrowData {
    escrow_address: string;
    amount_inr: number;
    network: string;
    status: string;
    buyer_address: string;
    seller_address: string;
}

export interface AuthState {
    enterprise_id: string;
    legal_name: string;
    token: string;
    role: "buyer" | "seller";
}

export interface FrameworkInfo {
    name: string;
    version: string;
    protocols: string[];
    settlement_networks: string[];
    compliance_frameworks: string[];
}

export interface AgentConfigData {
    agent_role: string;
    intrinsic_value: number;
    risk_factor: number;
    negotiation_margin: number;
    concession_curve: Record<string, number>;
    budget_ceiling?: number;
    max_exposure: number;
    strategy_default: string;
    max_rounds: number;
    timeout_seconds: number;
}

export interface LoginPayload {
    email: string;
    password: string;
}

export interface RegisterPayload {
    legal_name: string;
    pan_number: string;
    gst_number: string;
    email: string;
    password: string;
    role: "buyer" | "seller";
    wallet_address?: string;
    webhook_url?: string;
}

export interface EnterpriseProfile {
    enterprise_id: string;
    legal_name: string;
    pan?: string;
    gst?: string;
    email: string;
    role: "buyer" | "seller";
    wallet_address?: string;
    kyc_status: "PENDING" | "EMAIL_VERIFIED" | "ACTIVE";
    agent_card_url?: string;
    agent_card_data?: AgentCard;
    created_at?: string;
}
