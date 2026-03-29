# A2A Treasury Network
### Agentic Commerce Framework (ACF) — AlgoBharat Hackathon · Problem 7

> Autonomous AI agents that negotiate trade deals and settle payments on Algorand.  
> Zero human involvement from first offer to final on-chain payment.

***

## What Is This?

The A2A Treasury Network is an **Agentic Commerce Framework** — a protocol stack that
enables autonomous machine-to-machine B2B commerce. Two enterprise AI agents discover
each other, verify protocol compatibility, negotiate a price autonomously, deploy an
Algorand escrow, and settle via the x402 payment protocol.

**No human is involved at any point.**

***

## The Problem (AlgoBharat Problem 7)

Indian SMEs spend 3–7 days on manual B2B trade negotiation and settlement for every
transaction. Cross-border payments add FEMA/RBI compliance overhead. There is no
standard protocol for autonomous agent-to-agent commerce.

***

## ACF Framework Architecture

```
┌─────────────────────────────────────────────────────────────┐
│              AGENTIC COMMERCE FRAMEWORK (ACF)               │
├──────────────┬──────────────┬──────────────┬────────────────┤
│   PROTOCOL   │  SETTLEMENT  │    POLICY    │  VERIFICATION  │
│    LAYER     │    LAYER     │    LAYER     │     LAYER      │
│              │              │              │                │
│  DANP-v1     │  x402 +      │  ACF Policy  │  SHA-256 Chain │
│  FixedPrice  │  Algorand    │  Engine      │  Merkle Root   │
│  -v1         │  Testnet     │  Guardrails  │  On-chain      │
│              │              │              │  Anchor        │
├──────────────┴──────────────┴──────────────┴────────────────┤
│                    AGENT LAYER                              │
│         Buyer Agent · Neutral Engine · Seller Agent        │
├─────────────────────────────────────────────────────────────┤
│                 DISCOVERY LAYER                             │
│      Agent Registry · Capability Handshake · Agent Cards  │
└─────────────────────────────────────────────────────────────┘
```

***

## End-to-End Flow (7 Steps)

```
1. REGISTER    Two enterprises register → Agent Cards provisioned
               Agents register in ACF discovery registry
               GET /v1/agents?service=cotton&protocol=DANP-v1 → finds them

2. POLICY      Budget ceilings, compliance flags, escrow requirements loaded
               ACFPolicyEngine enforces constraints throughout lifecycle

3. HANDSHAKE   POST /v1/handshake → compatibility verified before negotiation
               Selects shared protocol (DANP-v1) and settlement (x402-algorand)

4. NEGOTIATE   DANP-v1 FSM runs autonomously
               Buyer ₹85,000 → Seller ₹95,918 → Buyer ₹90,270 → Seller ACCEPTS
               Agreement in 2–3 rounds. Zero human input.

5. ESCROW      Algorand multisig escrow deployed on testnet
               Address derived from buyer + seller public keys

6. PAYMENT     Buyer agent receives HTTP 402 challenge
               Signs Algorand PaymentTxn autonomously
               Submits X-PAYMENT header → confirmed on-chain
               tx_id stored in SHA-256 audit chain

7. AUDIT       19+ audit entries · SHA-256 hash chain VALID
               Merkle root computed · Anchored on Algorand testnet
               Every offer, guardrail, and payment cryptographically provable
```

***

## Framework Protocols

### DANP-v1 — Dynamic Adaptive Negotiation Protocol
4-layer FSM combining reservation pricing, concession curves, LLM strategic advisory,
and guardrail enforcement. Agents reach agreement in 2–3 rounds autonomously.

| Layer | Component | Role |
|-------|-----------|------|
| Layer 1 | Reservation/Target Prices | Economic boundaries per agent |
| Layer 2 | DANP FSM | State machine: ANCHOR → COUNTER → AGREED |
| Layer 3 | Groq LLM (Llama 3.3 70B) | Strategic advisory — suggests modifiers |
| Layer 4 | Guardrails | Budget ceiling enforcement, policy breach |

### FixedPrice-v1 — Fixed Price Protocol
Seller posts a fixed price. Buyer accepts or rejects. Single round, no concession.
Demonstrates framework extensibility — a second fully working protocol alongside DANP.

```
POST /v1/framework/fixed-price-demo
→ { "outcome": "ACCEPTED", "protocol": "FixedPrice-v1", "rounds_taken": 1 }
```

***

## Discovery & Handshake

Before negotiation, agents discover each other and verify compatibility:

```bash
# Register in registry
POST /v1/agents/register
{ "service_tags": ["cotton", "textiles"], "availability": "active" }

# Discover compatible agents
GET /v1/agents?service=cotton&protocol=DANP-v1&network=algorand-testnet

# Capability handshake — verify protocol + settlement compatibility
POST /v1/handshake
{ "buyer_enterprise_id": "<uuid>", "seller_enterprise_id": "<uuid>" }
→ { "compatible": true, "selected_protocol": "DANP-v1",
    "selected_settlement": "x402-algorand-testnet", "handshake_id": "<uuid>" }
```

***

## Verification Layer

Every session produces a cryptographically verifiable audit trail:

| Component | What It Does |
|-----------|--------------|
| SHA-256 Hash Chain | Every audit entry links to the previous via hash — tamper-evident |
| Merkle Root | Computed at session close — single hash represents entire audit trail |
| On-Chain Anchor | Merkle root stored as Algorand tx note — provable on blockchain forever |
| Leaf Verification | `POST /v1/audit/{id}/verify-leaf` proves any single entry is authentic |

```bash
GET /v1/audit/{session_id}/merkle
→ { "merkle_root": "a3f9...", "leaf_count": 19,
    "anchor_tx_id": "ALGO-TX...", "anchored_on_chain": true }
```

***

## Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Agent Protocol | Google A2A + Agent Cards | Agent identity, task routing |
| Negotiation | DANP-v1 FSM | 4-layer autonomous price discovery |
| Second Protocol | FixedPrice-v1 | Framework extensibility proof |
| LLM Advisory | Groq Llama 3.3 70B | Strategy modulation |
| Payment Protocol | x402 | HTTP-native autonomous agent payments |
| Blockchain | Algorand Testnet | Escrow + settlement + audit anchor |
| FX Engine | Frankfurter API | Live INR/USDC rates |
| Compliance | FEMA/RBI | 11 purpose codes, cross-border checks |
| Backend | FastAPI + Python 3.11 | REST API |
| Database | PostgreSQL 15 | Persistent state |
| Cache/Registry | Redis 7 | Agent registry, rate limiting, FX cache |
| Infrastructure | Docker Compose | One-command deployment |

***

## Quick Start

### Prerequisites
- Docker Desktop
- Python 3.11
- Git

### 1. Clone and configure
```bash
git clone <repo-url>
cd a2a-treasury
cp .env.example .env
# Edit .env — add your GROQ_API_KEY
# For LIVE Algorand payments: set X402_SIMULATION_MODE=false + wallet mnemonics
```

### 2. Start services
```bash
docker-compose up -d --build
# Wait 15 seconds for DB + Redis health checks
```

### 3. Run migrations
```bash
docker-compose exec api alembic upgrade head
```

### 4. Run the 7-step ACF demo
```bash
python demo_acf.py
```

### 5. Run full 22-phase simulation
```bash
python simulate_negotiation.py --mode autonomous
```

### 6. Try FixedPrice protocol directly
```bash
curl -s -X POST http://localhost:8000/v1/framework/fixed-price-demo \
  -H "Content-Type: application/json" \
  -d '{"fixed_price": 90000, "buyer_budget": 95000}' | python -m json.tool
```

***

## Makefile Commands

```bash
make demo-acf    # Run 7-step ACF framework demo
make sim         # Run full 22-phase simulation
make up          # Start Docker services
make down        # Stop Docker services
make fresh       # Clean restart + run demo
make health      # Quick health check
make logs        # Tail API logs
make registry    # List all registered agents
make handshake   # Test capability handshake endpoint
```

***

## Key API Endpoints

### Framework
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/v1/framework/protocols` | List registered protocols (DANP-v1, FixedPrice-v1) |
| GET | `/v1/framework/settlement-providers` | List settlement providers |
| GET | `/v1/framework/info` | Full framework summary |
| POST | `/v1/framework/fixed-price-demo` | Live FixedPrice-v1 demo |

### Discovery & Handshake
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/v1/agents/register` | Register agent in discovery registry |
| GET | `/v1/agents` | Query registry (filter by service, protocol, network) |
| GET | `/v1/agents/{enterprise_id}` | Get specific agent's registry entry |
| POST | `/v1/handshake` | Run capability compatibility handshake |
| GET | `/v1/handshake/{handshake_id}` | Retrieve stored handshake |

### Negotiation & Settlement
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/v1/sessions/` | Create negotiation session |
| POST | `/v1/sessions/{id}/run` | Run autonomous negotiation |
| GET | `/v1/sessions/{id}/status` | Poll session status |
| GET | `/v1/sessions/{id}/transcript` | Get SHA-256 audit chain |
| POST | `/v1/deliver/{id}` | x402 payment delivery (402 → sign → 200) |
| GET | `/v1/escrow/session/{id}` | Get escrow details |

### Verification
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/v1/audit/{id}/merkle` | Get session Merkle root |
| POST | `/v1/audit/{id}/verify-leaf` | Verify single audit entry |
| GET | `/v1/audit/verify-chain` | Verify full SHA-256 chain |

Full interactive docs: `http://localhost:8000/docs`

***

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GROQ_API_KEY` | Yes | Groq LLM API key |
| `X402_SIMULATION_MODE` | Yes | `true` = simulated, `false` = LIVE Algorand |
| `ANCHOR_ENABLED` | Yes | `true` = anchor Merkle root on Algorand |
| `BUYER_WALLET_MNEMONIC` | LIVE only | 25-word Algorand mnemonic |
| `BUYER_WALLET_ADDRESS` | LIVE only | Buyer Algorand testnet address |
| `SELLER_WALLET_ADDRESS` | LIVE only | Seller Algorand testnet address |
| `DATABASE_URL` | Yes | PostgreSQL connection (set by Docker) |
| `REDIS_URL` | Yes | Redis connection (set by Docker) |

***

## Simulation vs LIVE Mode

| Feature | Simulation | LIVE |
|---------|-----------|------|
| Payment token | `SIM-X402-ALGO-{hash}` | Base64 signed Algorand PaymentTxn |
| Transaction | No on-chain activity | Real broadcast to Algorand testnet |
| tx_id | `SIM-ALGOTX-{hash}` | Real Algorand tx_id |
| Anchor tx | `SIM-ANCHOR-{hash}` | Real Algorand tx with Merkle root note |
| Wallet required | No | Yes — buyer wallet must be funded |
| Explorer link | None | Lora Explorer |

***

## Verifying On-Chain Transactions

After running in LIVE mode:
- Transaction: `https://lora.algokit.io/testnet/transaction/{TX_ID}`
- Buyer Account: `https://lora.algokit.io/testnet/account/{BUYER_ADDRESS}`
- Escrow Account: `https://lora.algokit.io/testnet/account/{ESCROW_ADDRESS}`

***

## Hackathon Highlights

**Novel x402 on Algorand** — HTTP-native autonomous agent payments using Algorand native
transactions. One of the first implementations of x402 on Algorand.

**Dual Protocol Framework** — DANP-v1 and FixedPrice-v1 registered in the same framework.
Proves `NegotiationProtocol` is a real abstraction, not a single-protocol wrapper.

**Cryptographic Audit Trail** — SHA-256 hash chain + Merkle root + on-chain Algorand
anchor. Every session's integrity is verifiable from the blockchain.

**Full FEMA/RBI Compliance** — 11 RBI purpose codes, automatic compliance checks,
cross-border transaction guardrails.

**Zero Human Interactions** — The 22-phase simulation and 7-step ACF demo both prove
the complete lifecycle runs without any human input.

***

## License
MIT

## Built With
- [Algorand](https://algorand.com) — Blockchain infrastructure
- [x402 Protocol](https://x402.org) — HTTP payment protocol for AI agents
- [Groq](https://console.groq.com) — Ultra-fast LLM inference (Llama 3.3 70B)
- [FastAPI](https://fastapi.tiangolo.com) — Python backend framework
- [Google A2A](https://github.com/google/A2A) — Agent-to-Agent protocol
- [algosdk](https://py-algorand-sdk.readthedocs.io) — Algorand Python SDK
