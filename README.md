<p align="center">
  <img src="https://img.shields.io/badge/Algorand-Testnet-black?style=for-the-badge&logo=algorand&logoColor=white" alt="Algorand Testnet"/>
  <img src="https://img.shields.io/badge/Google_A2A-Protocol-4285F4?style=for-the-badge&logo=google&logoColor=white" alt="Google A2A"/>
  <img src="https://img.shields.io/badge/x402-Payment_Protocol-8B5CF6?style=for-the-badge" alt="x402"/>
  <img src="https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python"/>
  <img src="https://img.shields.io/badge/Next.js-16-000000?style=for-the-badge&logo=next.js&logoColor=white" alt="Next.js"/>
</p>

# 🏛️ Cadence — A2A Treasury Network

### Agentic Commerce Framework (ACF) — AlgoBharat Hackathon · Problem 7

> **Autonomous AI agents that negotiate trade deals and settle payments on Algorand.**  
> Zero human involvement from first offer to final on-chain payment.

---

## 🎯 The Problem

Indian SMEs spend **3–7 days** on manual B2B trade negotiation and settlement per transaction. Cross-border payments add **FEMA/RBI compliance** overhead. There is no standard protocol for autonomous agent-to-agent commerce.

**Cadence solves this** by enabling two enterprise AI agents to autonomously discover each other, verify compatibility, negotiate a price, deploy an Algorand escrow, and settle via the x402 payment protocol — **all without any human intervention.**

---

## 🏗️ Architecture Overview

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
│         Buyer Agent · Neutral Engine · Seller Agent         │
├─────────────────────────────────────────────────────────────┤
│                 DISCOVERY LAYER                             │
│      Agent Registry · Capability Handshake · Agent Cards    │
└─────────────────────────────────────────────────────────────┘
```

---

## 📁 Repository Structure

```
Cadence/
├── A-TOA/
│   ├── a2a-treasury/          # 🐍 Backend — FastAPI + Python 3.11
│   │   ├── agents/            #    Buyer, Seller, and Neutral negotiation agents
│   │   ├── a2a_protocol/      #    Google A2A protocol implementation
│   │   ├── api/               #    REST API endpoints (FastAPI)
│   │   ├── blockchain/        #    Algorand integration (escrow, settlement)
│   │   ├── compliance/        #    FEMA/RBI compliance engine
│   │   ├── core/              #    Core business logic
│   │   ├── dashboard/         #    Analytics & monitoring
│   │   ├── db/                #    PostgreSQL models & Alembic migrations
│   │   ├── framework/         #    ACF protocol framework (DANP-v1, FixedPrice-v1)
│   │   ├── treasury/          #    Treasury management
│   │   ├── scripts/           #    Utility scripts
│   │   ├── tests/             #    Test suite
│   │   ├── demo.py            #    Basic demo script
│   │   ├── demo_acf.py        #    7-step ACF framework demo
│   │   └── simulate_negotiation.py  # Full 22-phase simulation
│   │
│   ├── a2a-treasury-ui/       # ⚛️ Frontend — Next.js 16 + React 19
│   │   ├── src/
│   │   │   ├── app/           #    Next.js App Router pages
│   │   │   ├── components/    #    Reusable UI components
│   │   │   ├── hooks/         #    Custom React hooks
│   │   │   ├── lib/           #    Utilities & API clients
│   │   │   └── types/         #    TypeScript type definitions
│   │   └── __tests__/         #    Jest + Playwright test suites
│   │
│   └── run_simulation.py      # 🚀 Root simulation runner
│
├── .gitignore
└── README.md
```

---

## ⚡ End-to-End Flow (7 Steps)

| Step | Phase | What Happens |
|------|-------|-------------|
| **1** | **Register** | Two enterprises register → Agent Cards provisioned in ACF discovery registry |
| **2** | **Policy** | Budget ceilings, compliance flags, and escrow requirements loaded |
| **3** | **Handshake** | Protocol + settlement compatibility verified (`DANP-v1` + `x402-algorand`) |
| **4** | **Negotiate** | DANP-v1 FSM runs autonomously — agreement reached in 2–3 rounds |
| **5** | **Escrow** | Algorand multisig escrow deployed on testnet |
| **6** | **Payment** | Buyer receives HTTP 402 challenge → signs Algorand tx → confirmed on-chain |
| **7** | **Audit** | 19+ entries in SHA-256 hash chain, Merkle root anchored on Algorand |

---

## 🔬 Framework Protocols

### DANP-v1 — Dynamic Adaptive Negotiation Protocol

A 4-layer FSM combining reservation pricing, concession curves, LLM strategic advisory, and guardrail enforcement.

| Layer | Component | Role |
|-------|-----------|------|
| 1 | Reservation/Target Prices | Economic boundaries per agent |
| 2 | DANP FSM | State machine: `ANCHOR → COUNTER → AGREED` |
| 3 | Groq LLM (Llama 3.3 70B) | Strategic advisory — suggests modifiers |
| 4 | Guardrails | Budget ceiling enforcement, policy breach detection |

### FixedPrice-v1 — Fixed Price Protocol

Single-round protocol — seller posts a fixed price, buyer accepts or rejects. Demonstrates framework extensibility alongside DANP-v1.

---

## 🔐 Verification Layer

Every session produces a cryptographically verifiable audit trail:

| Component | What It Does |
|-----------|-------------|
| **SHA-256 Hash Chain** | Every audit entry links to the previous via hash — tamper-evident |
| **Merkle Root** | Computed at session close — single hash represents entire audit trail |
| **On-Chain Anchor** | Merkle root stored as Algorand tx note — provable on blockchain forever |
| **Leaf Verification** | Proves any single entry is authentic via Merkle proof |

---

## 🛠️ Tech Stack

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
| Frontend | Next.js 16 + React 19 | Dashboard UI |
| Database | PostgreSQL 15 | Persistent state |
| Cache/Registry | Redis 7 | Agent registry, rate limiting, FX cache |
| Infrastructure | Docker Compose | One-command deployment |

---

## 🚀 Quick Start

### Prerequisites

- **Docker Desktop** (for PostgreSQL + Redis)
- **Python 3.11+**
- **Node.js 18+** (for the UI)
- **Git**

### 1. Clone & Configure

```bash
git clone https://github.com/harsh-mogalgiddikar/Candence.git
cd Candence/A-TOA/a2a-treasury
cp .env.example .env
# Edit .env — add your GROQ_API_KEY
# For LIVE Algorand payments: set X402_SIMULATION_MODE=false + wallet mnemonics
```

### 2. Start Backend Services

```bash
docker-compose up -d --build
# Wait ~15 seconds for DB + Redis health checks

# Run migrations
docker-compose exec api alembic upgrade head
```

### 3. Run the 7-Step ACF Demo

```bash
python demo_acf.py
```

### 4. Run Full 22-Phase Simulation

```bash
# From repo root
python A-TOA/run_simulation.py --mode autonomous

# Or from the a2a-treasury directory
python simulate_negotiation.py --mode autonomous
```

### 5. Start the Dashboard UI

```bash
cd ../a2a-treasury-ui
cp .env.local.example .env.local
npm install
npm run dev
# Open http://localhost:3000
```

---

## ⚙️ Makefile Commands

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

---

## 📡 Key API Endpoints

### Framework
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/v1/framework/protocols` | List registered protocols (DANP-v1, FixedPrice-v1) |
| `GET` | `/v1/framework/settlement-providers` | List settlement providers |
| `POST` | `/v1/framework/fixed-price-demo` | Live FixedPrice-v1 demo |

### Discovery & Handshake
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/v1/agents/register` | Register agent in discovery registry |
| `GET` | `/v1/agents` | Query registry (filter by service, protocol, network) |
| `POST` | `/v1/handshake` | Run capability compatibility handshake |

### Negotiation & Settlement
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/v1/sessions/` | Create negotiation session |
| `POST` | `/v1/sessions/{id}/run` | Run autonomous negotiation |
| `GET` | `/v1/sessions/{id}/transcript` | Get SHA-256 audit chain |
| `POST` | `/v1/deliver/{id}` | x402 payment delivery (402 → sign → 200) |

### Verification
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/v1/audit/{id}/merkle` | Get session Merkle root |
| `POST` | `/v1/audit/{id}/verify-leaf` | Verify single audit entry |
| `GET` | `/v1/audit/verify-chain` | Verify full SHA-256 chain |

> 📖 Full interactive docs available at `http://localhost:8000/docs`

---

## 🔧 Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GROQ_API_KEY` | ✅ | Groq LLM API key |
| `X402_SIMULATION_MODE` | ✅ | `true` = simulated, `false` = LIVE Algorand |
| `ANCHOR_ENABLED` | ✅ | `true` = anchor Merkle root on Algorand |
| `BUYER_WALLET_MNEMONIC` | LIVE only | 25-word Algorand mnemonic |
| `BUYER_WALLET_ADDRESS` | LIVE only | Buyer Algorand testnet address |
| `SELLER_WALLET_ADDRESS` | LIVE only | Seller Algorand testnet address |
| `DATABASE_URL` | ✅ | PostgreSQL connection string |
| `REDIS_URL` | ✅ | Redis connection string |

---

## 🔀 Simulation vs LIVE Mode

| Feature | Simulation | LIVE |
|---------|-----------|------|
| Payment token | `SIM-X402-ALGO-{hash}` | Base64 signed Algorand PaymentTxn |
| Transaction | No on-chain activity | Real broadcast to Algorand testnet |
| tx_id | `SIM-ALGOTX-{hash}` | Real Algorand tx_id |
| Anchor tx | `SIM-ANCHOR-{hash}` | Real Algorand tx with Merkle root note |
| Wallet required | ❌ No | ✅ Yes — must be funded |
| Explorer link | None | [Lora Explorer](https://lora.algokit.io/testnet) |

---

## 🏆 Hackathon Highlights

- **🌐 Novel x402 on Algorand** — One of the first implementations of HTTP-native autonomous agent payments on Algorand
- **🔄 Dual Protocol Framework** — DANP-v1 and FixedPrice-v1 registered in the same framework, proving real protocol abstraction
- **🔗 Cryptographic Audit Trail** — SHA-256 hash chain + Merkle root + on-chain Algorand anchor
- **🇮🇳 Full FEMA/RBI Compliance** — 11 RBI purpose codes, automatic compliance checks, cross-border guardrails
- **🤖 Zero Human Interaction** — Complete lifecycle runs autonomously from discovery through settlement

---

## 📄 License

MIT

---

## 🙏 Built With

- [**Algorand**](https://algorand.com) — Blockchain infrastructure
- [**x402 Protocol**](https://x402.org) — HTTP payment protocol for AI agents
- [**Google A2A**](https://github.com/google/A2A) — Agent-to-Agent protocol
- [**Groq**](https://console.groq.com) — Ultra-fast LLM inference (Llama 3.3 70B)
- [**FastAPI**](https://fastapi.tiangolo.com) — Python backend framework
- [**Next.js**](https://nextjs.org) — React framework for the dashboard
- [**algosdk**](https://py-algorand-sdk.readthedocs.io) — Algorand Python SDK
