## A2A Treasury Network — API Audit Report

## Backend Route Catalog

### Auth (`/v1/auth`)

| Method | Path              | Auth                   | Request Body (schema)                                           | Query/Path Params | Response (shape)                                  |
|--------|-------------------|------------------------|------------------------------------------------------------------|-------------------|---------------------------------------------------|
| POST   | `/v1/auth/register` | Bearer (admin)       | `RegisterUserRequest` `{ enterprise_id, email, password, role }` | —                 | `RegisterUserResponse` `{ user_id, email, role, enterprise_id }` |
| POST   | `/v1/auth/login`  | Public                 | `LoginRequest` `{ email, password }`                            | —                 | `TokenResponse` `{ access_token, refresh_token }` |
| POST   | `/v1/auth/refresh` | Public (not implemented) | `RefreshRequest` `{ refresh_token }`                         | —                 | 501 error (not implemented)                       |
| POST   | `/v1/auth/logout` | Bearer (any role)      | —                                                                | —                 | `MessageResponse` `{ detail }`                    |

### Enterprises (`/v1/enterprises`)

| Method | Path                                             | Auth              | Request Body (schema)                                                                                                    | Query/Path Params          | Response (shape)                                                                                                      |
|--------|--------------------------------------------------|-------------------|-------------------------------------------------------------------------------------------------------------------------|----------------------------|-----------------------------------------------------------------------------------------------------------------------|
| POST   | `/v1/enterprises/register`                       | Public           | `EnterpriseRegisterRequest` `{ legal_name, pan, gst, authorized_signatory, primary_bank_account, wallet_address, email, password }` | —                          | `EnterpriseRegisterResponse` `{ enterprise_id, legal_name, kyc_status, verification_token }`                         |
| POST   | `/v1/enterprises/{enterprise_id}/verify-email`   | Public           | `VerifyEmailRequest` `{ verification_token: str }` (currently not validated)                                            | `enterprise_id` (UUID)     | `EnterpriseStatusResponse` `{ enterprise_id, kyc_status }`                                                            |
| POST   | `/v1/enterprises/{enterprise_id}/activate`       | Bearer (admin)   | —                                                                                                                       | `enterprise_id` (UUID)     | `EnterpriseStatusResponse` `{ enterprise_id, kyc_status, agent_card_url }`                                           |
| GET    | `/v1/enterprises/`                               | Bearer (admin)   | —                                                                                                                       | `page`, `page_size`, `status` | `EnterpriseListResponse` `{ items: EnterpriseDetailResponse[], total, page }`                                     |
| GET    | `/v1/enterprises/{enterprise_id}`                | Bearer (any)     | —                                                                                                                       | `enterprise_id` (UUID)     | `EnterpriseDetailResponse` `{ enterprise_id, legal_name, pan, gst, kyc_status, wallet_address, agent_card_url, created_at }` |
| POST   | `/v1/enterprises/{enterprise_id}/agent-config`   | Bearer (admin)   | `AgentConfigRequest` `{ agent_role, intrinsic_value, risk_factor, negotiation_margin, concession_curve, budget_ceiling?, max_exposure, strategy_default, max_rounds, timeout_seconds }` | `enterprise_id` (UUID) | `AgentConfigResponse` mirrors config fields with numeric values as `float`                                           |
| POST   | `/v1/enterprises/{enterprise_id}/treasury-policy`| Bearer (admin)   | `TreasuryPolicyRequest` `{ buffer_threshold?, risk_tolerance, yield_strategy }`                                         | `enterprise_id` (UUID)     | `TreasuryPolicyResponse` `{ policy_id, enterprise_id, active }`                                                       |
| POST   | `/v1/enterprises/{enterprise_id}/webhook`        | Bearer (admin, same enterprise) | `WebhookConfigRequest` `{ webhook_url, webhook_secret }`                                                      | `enterprise_id` (UUID)     | `{ webhook_url, configured: bool }`                                                                                  |
| DELETE | `/v1/enterprises/{enterprise_id}/webhook`        | Bearer (admin, same enterprise) | —                                                                                                             | `enterprise_id` (UUID)     | `{ webhook_url: null, configured: False }`                                                                           |
| GET    | `/v1/enterprises/{enterprise_id}/webhook/test`   | Bearer (admin, same enterprise) | —                                                                                                             | `enterprise_id` (UUID)     | `{ sent: bool, status_code, error }`                                                                                 |
| GET    | `/v1/enterprises/{enterprise_id}/.well-known/agent.json` | Public  | —                                                                                                                       | `enterprise_id` (UUID)     | Enterprise agent card JSON (from `agent_card_data`), 404 unless KYC status ACTIVE and card present                   |

### Sessions (`/v1/sessions`)

| Method | Path                               | Auth            | Request Body (schema)                                                                                 | Query/Path Params                             | Response (shape)                                                                                           |
|--------|------------------------------------|-----------------|--------------------------------------------------------------------------------------------------------|-----------------------------------------------|------------------------------------------------------------------------------------------------------------|
| POST   | `/v1/sessions/`                    | Bearer (admin) | `CreateSessionRequest` `{ seller_enterprise_id, initial_offer_value, milestone_template_id?, timeout_seconds?, max_rounds? }` | —                                             | `CreateSessionResponse` `{ session_id, ... }` including initial status and metadata                        |
| POST   | `/v1/sessions/{session_id}/action` | Bearer (any)   | `AgentActionEnvelope` `{ session_id, agent_role, action, value?, rationale?, ... }`                  | `session_id` (UUID)                            | `ActionResponse` `{ status, new_state, offers?, ... }` (per `api.schemas.session`)                         |
| GET    | `/v1/sessions/{session_id}/status` | Bearer (any)   | —                                                                                                      | `session_id` (UUID)                            | `SessionStatusResponse` `{ session_id, status, current_round, max_rounds, timeout_at, is_terminal, outcome, final_agreed_value? }` |
| GET    | `/v1/sessions/{session_id}/offers` | Bearer (any)   | —                                                                                                      | `session_id` (UUID)                            | `OfferListResponse` `{ session_id, offers: OfferDetail[] }`                                                |
| GET    | `/v1/sessions/{session_id}/transcript` | Bearer (any) | —                                                                                                      | `session_id` (UUID)                            | Exported audit transcript `{ entries: AuditEntry[], ... }`                                                 |
| POST   | `/v1/sessions/{session_id}/run`    | Bearer (admin) | —                                                                                                      | `session_id` (UUID)                            | `{ session_id, status: "RUNNING", message }`                                                               |
| GET    | `/v1/sessions/`                    | Bearer (admin) | —                                                                                                      | `enterprise_id?`, `status?`, `page`, `page_size` | `SessionListResponse` `{ items: SessionStatusResponse[], total, page }`                                  |
| POST   | `/v1/sessions/multi`               | Bearer (admin) | `MultiSessionRequest` `{ seller_enterprise_ids: str[], initial_offer_value, timeout_seconds? }`       | —                                             | `{ multi_session_id, child_session_ids, status, seller_count }`                                            |
| GET    | `/v1/sessions/multi/{multi_session_id}` | Bearer (any) | —                                                                                                      | `multi_session_id`                             | Multi-session status object                                                                                |
| GET    | `/v1/sessions/multi/{multi_session_id}/leaderboard` | Bearer (any) | —                                                                                                      | `multi_session_id`                             | Multi-session leaderboard object                                                                           |

### Audit (`/v1/audit`)

| Method | Path                         | Auth            | Request Body (schema)                     | Query/Path Params                        | Response (shape)                                                                                   |
|--------|------------------------------|-----------------|-------------------------------------------|------------------------------------------|----------------------------------------------------------------------------------------------------|
| GET    | `/v1/audit/{enterprise_id}/log` | Bearer (any) | —                                         | `enterprise_id`, `page`, `page_size`     | Paginated enterprise audit log `{ items: AuditEntry[], total, page }`                             |
| GET    | `/v1/audit/verify-chain`     | Bearer (any)   | —                                         | `session_id?`                            | Chain verification `{ valid, entries_checked, broken_link_at? }`                                  |
| GET    | `/v1/audit/{session_id}/merkle` | Public       | —                                         | `session_id` (UUID)                      | `{ session_id, merkle_root, leaf_count, anchor_tx_id?, anchored_on_chain: bool, verification_url? }` (202/404/pending variants) |
| POST   | `/v1/audit/{session_id}/verify-leaf` | Public   | `VerifyLeafRequest` `{ leaf_hash }`       | `session_id` (UUID)                      | `{ leaf_hash, merkle_root, proof, verified }`                                                     |

### Escrow (`/v1/escrow`)

| Method | Path                                  | Auth            | Request Body (schema)                      | Query/Path Params         | Response (shape)                                                                                       |
|--------|---------------------------------------|-----------------|--------------------------------------------|---------------------------|--------------------------------------------------------------------------------------------------------|
| GET    | `/v1/escrow/session/{session_id}`     | Bearer (any)   | —                                          | `session_id` (UUID)       | `{ escrow_id, session_id, contract_ref, network_id, amount, status, deployed_at, tx_ref }`            |
| GET    | `/v1/escrow/{escrow_id}`             | Bearer (any)   | —                                          | `escrow_id` (UUID)        | Same escrow object as above                                                                           |
| POST   | `/v1/escrow/{escrow_id}/release`     | Bearer (admin) | `ReleaseRequest` `{ milestone: "milestone-1" (default) }` | `escrow_id` (UUID)        | Escrow manager result `{ status, tx_id, ... }`                                                        |
| POST   | `/v1/escrow/{escrow_id}/refund`      | Bearer (admin) | `RefundRequest` `{ reason: "Dispute — refund" (default) }` | `escrow_id` (UUID)        | Escrow manager result `{ status, tx_id, ... }`                                                        |
| POST   | `/v1/escrow/{escrow_id}/fund`        | Bearer (admin) | —                                          | `escrow_id` (UUID)        | Escrow funding result `{ status, tx_id, ... }`                                                        |
| GET    | `/v1/escrow/{escrow_id}/status`      | Bearer (any)   | —                                          | `escrow_id` (UUID)        | `{ escrow_id, contract_ref, status, on_chain_balance_usdc, agreed_amount_usdc, balance_verified, sdk_available, explorer_url }` |

### FX (`/v1/fx`)

| Method | Path                        | Auth            | Request Body (schema)                        | Query/Path Params | Response (shape)                                                                                                          |
|--------|-----------------------------|-----------------|----------------------------------------------|-------------------|---------------------------------------------------------------------------------------------------------------------------|
| GET    | `/v1/fx/rate`              | Bearer (any)   | —                                            | —                 | `FxQuote` `{ quote_id, mid_rate, buy_rate, sell_rate, spread_bps, source, fetched_at, expires_at }`                      |
| GET    | `/v1/fx/session/{session_id}` | Bearer (any) | —                                            | `session_id`      | Session FX quote `{ quote_id, mid_rate, buy_rate, sell_rate, spread_bps, source, session_id, fetched_at }`               |
| POST   | `/v1/fx/convert`           | Bearer (any)   | `ConvertRequest` `{ amount, from_currency, to_currency, session_id? }` | —                 | Conversion result `{ inr_amount, usdc_amount, rate, direction, ... }` (model-dumped from fx engine)                      |
| GET    | `/v1/fx/history`           | Bearer (any)   | —                                            | `limit`           | `{ quotes: FxQuoteLike[], count }`                                                                                       |

### Treasury (`/v1/treasury`)

| Method | Path                                      | Auth            | Request Body (schema) | Query/Path Params        | Response (shape)                                                            |
|--------|-------------------------------------------|-----------------|------------------------|--------------------------------|-----------------------------------------------------------------------------|
| GET    | `/v1/treasury/platform`                  | Bearer (any)   | —                      | —                              | Platform summary (matches `PlatformSummary` fields)                        |
| GET    | `/v1/treasury/session/{session_id}/pnl`  | Bearer (any)   | —                      | `session_id`                  | Session P&L for current enterprise                                          |
| GET    | `/v1/treasury/session/{session_id}/llm`  | Bearer (any)   | —                      | `session_id`                  | LLM performance metrics                                                     |
| GET    | `/v1/treasury/{enterprise_id}`           | Bearer (any)   | —                      | `enterprise_id`              | Enterprise summary (matches `EnterpriseSummary` fields)                    |
| GET    | `/v1/treasury/{enterprise_id}/exposure`  | Bearer (any)   | —                      | `enterprise_id`              | Exposure report object                                                      |
| GET    | `/v1/treasury/{enterprise_id}/timeline`  | Bearer (any)   | —                      | `enterprise_id`, `days`      | Negotiation timeline data                                                   |
| GET    | `/v1/treasury/{enterprise_id}/strategy`  | Bearer (any)   | —                      | `enterprise_id`              | Strategy performance breakdown                                              |
| GET    | `/v1/treasury/{enterprise_id}/counterparties` | Bearer (any) | —                  | `enterprise_id`              | Counterparty analysis                                                       |

### Compliance (`/v1/compliance`)

| Method | Path                                   | Auth            | Request Body (schema)                                    | Query/Path Params | Response (shape)                                                             |
|--------|----------------------------------------|-----------------|----------------------------------------------------------|-------------------|------------------------------------------------------------------------------|
| GET    | `/v1/compliance/purpose-codes`        | Public          | —                                                        | —                 | `{ codes: RBI_PURPOSE_CODES[] }`                                             |
| GET    | `/v1/compliance/session/{session_id}` | Bearer (any)   | —                                                        | `session_id`      | Compliance record model-dumped (`ComplianceRecord` shape)                    |
| POST   | `/v1/compliance/check`                | Bearer (any)   | `ComplianceCheckRequest` `{ buyer_enterprise_id, seller_enterprise_id, inr_amount, purpose_code }` | —                 | Compliance check result model-dumped (`ComplianceRecord`-like)               |
| GET    | `/v1/compliance/{enterprise_id}/history` | Bearer (any) | —                                                        | `enterprise_id`, `limit` | `{ records: ComplianceRecord[], count }`                                 |

### Delivery / x402 (`/v1/deliver`)

| Method | Path                     | Auth            | Request Body (schema) | Headers                    | Query/Path Params | Response (shape)                                                                                      |
|--------|--------------------------|-----------------|------------------------|----------------------------|-------------------|-------------------------------------------------------------------------------------------------------|
| POST   | `/v1/deliver/{session_id}` | Bearer (any) | —                      | Optional `X-PAYMENT` token | `session_id`      | First call (no header): HTTP 402 with x402 challenge JSON; second call (with header): `{ delivered, session_id, payment_tx_id, network, amount_usdc, x402_verified, simulation, confirmed_round? }` or idempotent 200 |

### Framework (`/v1/framework`)

| Method | Path                               | Auth  | Request Body (schema) | Response (shape)                                                |
|--------|------------------------------------|-------|------------------------|-----------------------------------------------------------------|
| GET    | `/v1/framework/protocols`         | Public| —                      | `{ protocols: [{ id, version, supports_multi_party, requires_escrow, max_rounds, supported_settlement_networks, supported_payment_methods }] }` |
| GET    | `/v1/framework/settlement-providers` | Public | —                    | `{ providers: [{ id, supported_networks, supported_payment_methods, supports_escrow, simulation_mode }] }` |
| GET    | `/v1/framework/info`              | Public| —                      | `{ framework, version, protocol_count, settlement_provider_count, registered_protocols, registered_settlement_providers }` |
| POST   | `/v1/framework/fixed-price-demo`  | Public| `{ fixed_price, buyer_budget }` | Demo result object `{ protocol, session_id, fixed_price, buyer_budget, initiate_result, respond_result, evaluate_result, finalize_result?, outcome, message }` |

### Handshake (`/v1/handshake`)

| Method | Path                             | Auth  | Request Body (schema)                             | Query/Path Params | Response (shape)                                                                                           |
|--------|----------------------------------|-------|---------------------------------------------------|-------------------|------------------------------------------------------------------------------------------------------------|
| POST   | `/v1/handshake/`                | Public| `HandshakeRequest` `{ buyer_enterprise_id, seller_enterprise_id, session_id? }` | —                 | On compatible: 200 `{ handshake_id, compatible, selected_protocol, selected_settlement, shared_protocols, shared_settlement_networks, shared_payment_methods, incompatibility_reasons, expires_at, buyer_enterprise_id, seller_enterprise_id, message }`; on incompatible: 409 with same shape + message |
| GET    | `/v1/handshake/{handshake_id}`   | Public| —                                                 | `handshake_id`    | Stored handshake record with compatibility fields, timestamps, expired flag                               |
| GET    | `/v1/handshake/session/{session_id}` | Public | —                                              | `session_id`      | Most recent handshake for session with same fields                                                         |

### Registry (`/v1/agents`)

| Method | Path                       | Auth              | Request Body (schema)                         | Query/Path Params                                                 | Response (shape)                                                                                         |
|--------|----------------------------|-------------------|-----------------------------------------------|--------------------------------------------------------------------|----------------------------------------------------------------------------------------------------------|
| POST   | `/v1/agents/register`      | Bearer (any user) | `RegisterAgentRequest` `{ service_tags, description, availability }` | —                                                                  | `{ registered, enterprise_id, agent_id, service_tags, expires_in_hours, message }`                       |
| GET    | `/v1/agents/`              | Public           | —                                             | `service?`, `protocol?`, `network?`, `availability?`, `limit`      | `{ agents: [{ enterprise_id, agent_id, legal_name, description, service_tags, protocol, settlement_network, payment_method, availability, registered_at }], total, filters_applied }` |
| GET    | `/v1/agents/{enterprise_id}` | Public         | —                                             | `enterprise_id`                                                   | Single agent entry with full registry details + parsed `agent_card`                                     |
| PATCH  | `/v1/agents/availability`  | Bearer (any user) | `AvailabilityRequest` `{ availability }`      | —                                                                  | `{ enterprise_id, agent_id, availability, service_tags, message }`                                      |


## Frontend API Call Catalog

This section will enumerate each frontend API call (from `lib/api.ts`, `app/api/*`, `hooks/useApi.ts`, and dashboard components) with URL, method, request body, response fields consumed, and usage sites, followed by a detailed mismatch analysis and fixes.

## Mismatches Found & Fixed

This section will be completed after finishing the full frontend catalog and alignment work.

