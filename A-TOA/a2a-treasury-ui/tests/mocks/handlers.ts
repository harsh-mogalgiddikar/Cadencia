import { http, HttpResponse } from "msw";

const API = "http://localhost:8000";

export const handlers = [
  // ── Auth ──────────────────────────────────────────────────
  http.post(`${API}/v1/auth/login`, async ({ request }) => {
    const body = (await request.json()) as { email: string; password: string };
    if (
      body.email === "test@enterprise.com" &&
      body.password === "password123"
    ) {
      return HttpResponse.json({
        access_token: "mock_jwt_token",
        token_type: "bearer",
      });
    }
    return HttpResponse.json(
      { detail: "Invalid credentials" },
      { status: 401 }
    );
  }),

  // Enterprise registration
  http.post(`${API}/v1/enterprises/register`, async ({ request }) => {
    const body = (await request.json()) as { email: string; legal_name: string };
    if (body.email === "existing@enterprise.com") {
      return HttpResponse.json(
        { detail: "An enterprise with this email already exists." },
        { status: 409 }
      );
    }
    return HttpResponse.json(
      {
        id: "ent-uuid-001",
        legal_name: body.legal_name,
        email: body.email,
        kyc_status: "PENDING",
      },
      { status: 201 }
    );
  }),

  // Enterprise me
  http.get(`${API}/v1/enterprises/me`, () => {
    return HttpResponse.json({
      enterprise_id: "ent-uuid-001",
      legal_name: "Acme Textiles Pvt. Ltd.",
      email: "test@enterprise.com",
      pan: "ABCDE1234F",
      gst: "22ABCDE1234F1Z5",
      role: "buyer",
      kyc_status: "ACTIVE",
      wallet_address: "TESTWALLETADDRESS7F3A",
      agent_card_data: {
        name: "Acme Agent",
        version: "1.0",
        role: "buyer",
        protocols: [{ id: "DANP-v1" }],
        settlement_networks: ["algorand-testnet"],
        payment_methods: ["x402"],
        policy_constraints: {
          max_transaction_inr: 500000,
          requires_escrow: true,
          compliance_frameworks: ["FEMA"],
        },
        framework: { name: "ACF", version: "1.0" },
      },
    });
  }),

  // Sessions list
  http.get(`${API}/v1/sessions`, () => {
    return HttpResponse.json({
      items: [
        {
          session_id: "sess-uuid-001",
          status: "AGREED",
          current_round: 2,
          max_rounds: 5,
          timeout_at: new Date(Date.now() + 300000).toISOString(),
          is_terminal: true,
          outcome: "AGREED",
          final_agreed_value: 90270,
          buyer_enterprise_id: "ent-uuid-001",
          seller_enterprise_id: "ent-uuid-002",
          created_at: new Date().toISOString(),
        },
        {
          session_id: "sess-uuid-002",
          status: "ROUND_LOOP",
          current_round: 1,
          max_rounds: 5,
          timeout_at: new Date(Date.now() + 300000).toISOString(),
          is_terminal: false,
          outcome: null,
          final_agreed_value: null,
          buyer_enterprise_id: "ent-uuid-001",
          seller_enterprise_id: "ent-uuid-003",
          created_at: new Date().toISOString(),
        },
      ],
      total: 2,
      page: 1,
    });
  }),

  // Session status
  http.get(`${API}/v1/sessions/:id/status`, ({ params }) => {
    return HttpResponse.json({
      session_id: params.id,
      status: "AGREED",
      current_round: 2,
      max_rounds: 5,
      timeout_at: new Date(Date.now() + 300000).toISOString(),
      is_terminal: true,
      outcome: "AGREED",
      final_agreed_value: 90270,
    });
  }),

  // Session transcript / offers
  http.get(`${API}/v1/sessions/:id/transcript`, ({ params }) => {
    return HttpResponse.json({
      session_id: params.id,
      offers: [
        {
          offer_id: "offer-1",
          agent_role: "buyer",
          value: 85000,
          action: "counter",
          round: 1,
          confidence: 0.72,
          strategy_tag: "anchor",
          timestamp: new Date().toISOString(),
        },
        {
          offer_id: "offer-2",
          agent_role: "seller",
          value: 95918,
          action: "counter",
          round: 1,
          confidence: 0.68,
          strategy_tag: "anchor",
          timestamp: new Date().toISOString(),
        },
        {
          offer_id: "offer-3",
          agent_role: "buyer",
          value: 90270,
          action: "counter",
          round: 2,
          confidence: 0.85,
          strategy_tag: "concede",
          timestamp: new Date().toISOString(),
        },
        {
          offer_id: "offer-4",
          agent_role: "seller",
          value: 90270,
          action: "accept",
          round: 2,
          confidence: 0.9,
          strategy_tag: "accept",
          timestamp: new Date().toISOString(),
        },
      ],
      chain_valid: true,
    });
  }),

  // Treasury dashboard
  http.get(`${API}/v1/treasury/dashboard`, () => {
    return HttpResponse.json({
      total_sessions: 47,
      active_sessions: 3,
      agreed_sessions: 30,
      total_escrow_value_inr: 4250000,
      total_escrow_value_usdc: 50898,
      compliance_rate: 0.96,
      avg_rounds_to_agreement: 2.3,
      walkaway_rate: 0.08,
    });
  }),

  // Escrow
  http.get(`${API}/v1/escrow/session/:id`, ({ params }) => {
    return HttpResponse.json({
      escrow_id: "escrow-uuid-001",
      session_id: params.id,
      contract_ref: "ESC-7F3A",
      network_id: "algorand-testnet",
      amount: 1081.08,
      status: "FUNDED",
      deployed_at: new Date().toISOString(),
      tx_ref: "ALGO-FUND-TX-001",
    });
  }),

  http.post(`${API}/v1/escrow/:id/release`, () => {
    return HttpResponse.json({ success: true, tx_id: "ALGO-RELEASE-TX-001" });
  }),

  // Audit
  http.get(`${API}/v1/audit/:id/merkle`, ({ params }) => {
    return HttpResponse.json({
      session_id: params.id,
      merkle_root: "a3f9b2c4d5e6f7a8b9c0d1e2f3a4b5c6",
      leaf_count: 19,
      anchor_tx_id: "ALGO-TX-ANCHOR-001",
      anchored_on_chain: true,
      verification_url: null,
    });
  }),

  http.get(`${API}/v1/audit/verify-chain`, () => {
    return HttpResponse.json({
      valid: true,
      entries_checked: 127,
      broken_link_at: null,
    });
  }),

  // FX Rate
  http.get(`${API}/v1/fx/rate`, () => {
    return HttpResponse.json({
      quote_id: "fx-001",
      mid_rate: 0.01198,
      buy_rate: 0.01195,
      sell_rate: 0.01201,
      spread_bps: 5,
      source: "frankfurter",
      fetched_at: new Date().toISOString(),
      expires_at: new Date(Date.now() + 300000).toISOString(),
    });
  }),

  // Compliance
  http.get(`${API}/v1/compliance`, () => {
    return HttpResponse.json([
      {
        session_id: "sess-uuid-001",
        purpose_code: "P0103",
        transaction_type: "DOMESTIC",
        inr_amount: 90270,
        usdc_amount: 1081.08,
        limit_utilization_pct: 0.036,
        status: "APPROVED",
        warnings: [],
        blocking_reasons: [],
      },
    ]);
  }),

  // Health
  http.get(`${API}/health`, () => {
    return HttpResponse.json({
      status: "healthy",
      services: {
        postgres: "healthy",
        redis: "healthy",
        algorand: "healthy",
        groq: "healthy",
        fx: "healthy",
      },
    });
  }),
];
