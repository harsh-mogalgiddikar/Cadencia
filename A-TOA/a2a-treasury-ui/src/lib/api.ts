import axios from "axios";

const BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  "http://localhost:8000";

const api = axios.create({ baseURL: BASE });

// Attach JWT token to every request if present in localStorage
api.interceptors.request.use((config) => {
    if (typeof window !== "undefined") {
        const raw = localStorage.getItem("acf_auth");
        if (raw) {
            try {
                const auth = JSON.parse(raw);
                if (auth.token) {
                    config.headers.Authorization = `Bearer ${auth.token}`;
                }
            } catch {
                // ignore malformed JSON
            }
        }
    }
    return config;
});

// ── AUTH ────────────────────────────────────────────────────────────────

export const registerEnterprise = (data: {
    legal_name: string;
    email: string;
    password: string;
    pan?: string;
    gst?: string;
    authorized_signatory?: string;
    primary_bank_account?: string;
    wallet_address?: string;
}) => api.post("/v1/enterprises/register", data);

export const verifyEmail = (enterpriseId: string, verificationToken: string) =>
    api.post(`/v1/enterprises/${enterpriseId}/verify-email`, {
        verification_token: verificationToken,
    });

export const loginEnterprise = (email: string, password: string) =>
    api.post("/v1/auth/login", { email, password });

export const activateEnterprise = (enterpriseId: string) =>
    api.post(`/v1/enterprises/${enterpriseId}/activate`);

export const configureAgent = (
    enterpriseId: string,
    config: {
        agent_role: string;
        intrinsic_value: number;
        risk_factor: number;
        negotiation_margin?: number;
        concession_curve: Record<string, number>;
        budget_ceiling?: number;
        max_exposure?: number;
        strategy_default?: string;
        max_rounds?: number;
        timeout_seconds?: number;
    }
) => api.post(`/v1/enterprises/${enterpriseId}/agent-config`, config);

export const setTreasuryPolicy = (
    enterpriseId: string,
    policy: {
        buffer_threshold?: number;
        risk_tolerance?: string;
        yield_strategy?: string;
    }
) => api.post(`/v1/enterprises/${enterpriseId}/treasury-policy`, policy);

// ── REGISTRY ───────────────────────────────────────────────────────────

export const registerInRegistry = (serviceTags: string[]) =>
    api.post("/v1/agents/register", {
        service_tags: serviceTags,
        description: "ACF Demo Agent",
        availability: "active",
    });

export const queryRegistry = (params?: {
    service?: string;
    protocol?: string;
    network?: string;
    availability?: string;
}) => api.get("/v1/agents", { params });

export const getAgentById = (enterpriseId: string) =>
    api.get(`/v1/agents/${enterpriseId}`);

// ── HANDSHAKE ──────────────────────────────────────────────────────────

export const performHandshake = (
    buyerEnterpriseId: string,
    sellerEnterpriseId: string
) =>
    api.post("/v1/handshake", {
        buyer_enterprise_id: buyerEnterpriseId,
        seller_enterprise_id: sellerEnterpriseId,
    });

// ── NEGOTIATION ────────────────────────────────────────────────────────

export const createSession = (data: {
    seller_enterprise_id: string;
    initial_offer_value: number;
    milestone_template_id?: string;
    timeout_seconds?: number;
    max_rounds?: number;
}) => api.post("/v1/sessions/", data);

export const runNegotiation = (sessionId: string) =>
    api.post(`/v1/sessions/${sessionId}/run`);

export const getSessionStatus = (sessionId: string) =>
    api.get(`/v1/sessions/${sessionId}/status`);

export const getSessionTranscript = (sessionId: string) =>
    api.get(`/v1/sessions/${sessionId}/transcript`);

export const getSessionOffers = (sessionId: string) =>
    api.get(`/v1/sessions/${sessionId}/offers`);

// ── ESCROW ─────────────────────────────────────────────────────────────

export const getEscrow = (sessionId: string) =>
    api.get(`/v1/escrow/session/${sessionId}`);

// ── DELIVERY / x402 ───────────────────────────────────────────────────

export const triggerDelivery = (
    sessionId: string,
    paymentHeader?: string
) =>
    api.post(
        `/v1/deliver/${sessionId}`,
        {},
        paymentHeader ? { headers: { "X-PAYMENT": paymentHeader } } : {}
    );

// ── AUDIT ──────────────────────────────────────────────────────────────

export const getAuditLog = (sessionId: string) =>
    api.get(`/v1/audit/${sessionId}/log`);

export const verifyChain = () => api.get("/v1/audit/verify-chain");

export const getMerkleRoot = (sessionId: string) =>
    api.get(`/v1/audit/${sessionId}/merkle`);

// ── FRAMEWORK ──────────────────────────────────────────────────────────

export const getFrameworkInfo = () => api.get("/v1/framework/info");

export const getProtocols = () => api.get("/v1/framework/protocols");

// ── AGENT CARD ─────────────────────────────────────────────────────────

export const getAgentCard = (enterpriseId: string) =>
    api.get(`/v1/enterprises/${enterpriseId}/.well-known/agent.json`);
