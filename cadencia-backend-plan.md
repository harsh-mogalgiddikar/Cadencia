# Cadencia — Backend Implementation Plan

> **Project**: Cadencia — B2B Agentic Commerce Marketplace  
> **Migration**: PyTeal → Algorand SDK Smart Contracts  
> **Version**: 1.0.0  
> **Date**: 2026-03-31  
> **Stack**: Python ≥3.11 · FastAPI · Algorand SDK (py-algorand-sdk) · PostgreSQL · Redis  

---

## Table of Contents

1. [Migration Overview](#1-migration-overview)
2. [Current Architecture Audit](#2-current-architecture-audit)
3. [Phase 1 — Algorand SDK Contract Layer](#3-phase-1--algorand-sdk-contract-layer)
4. [Phase 2 — Escrow Lifecycle Rewrite](#4-phase-2--escrow-lifecycle-rewrite)
5. [Phase 3 — Payment & Settlement Refactor](#5-phase-3--payment--settlement-refactor)
6. [Phase 4 — Core Engine Cleanup & Multi-Tenancy](#6-phase-4--core-engine-cleanup--multi-tenancy)
7. [Phase 5 — Marketplace Discovery & Matchmaking](#7-phase-5--marketplace-discovery--matchmaking)
8. [Phase 6 — API Hardening & Auth Overhaul](#8-phase-6--api-hardening--auth-overhaul)
9. [Phase 7 — Deployment Configuration & Production Readiness](#9-phase-7--deployment-configuration--production-readiness)
10. [Complete API Reference](#10-complete-api-reference)
11. [File-Level Change Manifest](#11-file-level-change-manifest)
12. [Data Flow Diagrams](#12-data-flow-diagrams)

---

## 1. Migration Overview

### 1.1 Why Migrate from PyTeal

The current system uses PyTeal to write TEAL smart contracts that are compiled and deployed at runtime. This introduces several problems for a production marketplace:

- **Runtime TEAL compilation** adds latency and a failure point to every escrow deployment
- **PyTeal is a code-generation library**, not a contract framework — it produces TEAL source that must be separately compiled, which creates a fragile pipeline
- **No native ABI routing** — the current `contract_client.py` manually constructs ABI method calls
- **Deployment complexity** — the `deploy.py` script compiles PyTeal → TEAL → submits, requiring the PyTeal dependency chain in production

### 1.2 Target Architecture

Replace PyTeal with **pre-compiled ARC-4 ABI-compliant contracts** managed entirely through the **Algorand Python SDK (`py-algorand-sdk`)**. The contracts will be:

- Pre-compiled to TEAL and stored as static assets (no runtime compilation)
- Interacted with exclusively through `algosdk.v2client` and `algosdk.transaction`
- ARC-4 ABI compliant for clean method dispatch
- Deployed once per escrow session, referenced by `app_id`

### 1.3 Migration Scope Summary

| Component | Action | Reason |
|---|---|---|
| `blockchain/contracts/treasury_escrow.py` | **REMOVE** | PyTeal source — replaced by pre-compiled TEAL |
| `blockchain/contracts/deploy.py` | **REMOVE** | PyTeal compilation script — no longer needed |
| `blockchain/contract_client.py` | **REWRITE** | Replace PyTeal ABI calls with `algosdk.transaction` |
| `blockchain/escrow_manager.py` | **REWRITE** | Remove PyTeal dependency, use new SDK client |
| `blockchain/algo_client.py` | **REFACTOR** | Upgrade to use `algosdk.v2client.algod` patterns |
| `blockchain/simulation.py` | **REMOVE** | Folded into the new SDK client as dry-run |
| `blockchain/payment_handler.py` | **REFACTOR** | Align with new transaction construction |
| `core/x402_handler.py` | **REFACTOR** | Use new payment primitives |
| `core/anchor_service.py` | **REFACTOR** | Use new transaction builder |
| `framework/settlement/x402_algorand.py` | **REFACTOR** | Point to new settlement client |

---

## 2. Current Architecture Audit

### 2.1 Blockchain Module Dependency Graph

```
blockchain/
├── contracts/
│   ├── treasury_escrow.py    ← PyTeal source (REMOVE)
│   └── deploy.py             ← Compiles PyTeal → TEAL (REMOVE)
├── contract_client.py        ← ABI wrapper over compiled TEAL (REWRITE)
├── escrow_manager.py         ← 1018-line orchestrator (REWRITE)
├── algo_client.py            ← AlgodClient wrapper (REFACTOR)
├── payment_handler.py        ← Payment utilities (REFACTOR)
└── simulation.py             ← Dry-run helper (REMOVE — fold into SDK client)
```

### 2.2 Current Escrow Flow (PyTeal-based)

```
1. Session reaches AGREED state
2. escrow_manager.trigger_escrow() called
3.   → generate_escrow_payload() builds params from session
4.   → deploy_escrow() calls contract_client.deploy_new_escrow()
5.     → contract_client compiles PyTeal → TEAL at runtime
6.     → Submits ApplicationCreateTxn to Algorand
7.     → Returns app_id
8.   → Persists escrow record to DB
9. fund_escrow() → contract_client.fund_escrow() → PaymentTxn to app address
10. release_escrow() → contract_client.release_escrow() → ABI call with Merkle root
11. refund_escrow() → contract_client.refund_escrow() → ABI call with reason
```

**Problems with this flow:**
- Step 5 (runtime compilation) can fail if PyTeal version mismatches
- The 3-level fallback (contract → proof-tx → simulation) masks real failures
- `SIM-` references leak into production data

### 2.3 Current x402 Flow

```
1. Seller builds 402 response → core/x402_handler.py
2. Buyer signs PaymentTxn → algosdk.transaction.PaymentTxn
3. Server verifies X-PAYMENT header → broadcasts to Algorand
4. Simulation mode accepts SIM-X402-ALGO- tokens
```

**Problem:** Simulation mode has no gating — `X402_SIMULATION_MODE` defaults to `false` but the code still accepts `SIM-` prefixed tokens as a fallback.

---

## 3. Phase 1 — Algorand SDK Contract Layer

### 3.1 Objective

Build a clean, SDK-native smart contract interaction layer that replaces all PyTeal dependencies. Pre-compile the escrow contract to static TEAL files and interact with them exclusively through `py-algorand-sdk`.

### 3.2 Detailed Technical Tasks

#### Task 1.1 — Pre-compile Escrow Contract to Static TEAL

Take the existing `treasury_escrow.py` PyTeal source, compile it **once** to produce two static files:

```
blockchain/contracts/teal/
├── escrow_approval.teal      # Approval program
└── escrow_clear.teal         # Clear-state program
```

This is a one-time operation. After compilation, the PyTeal source and deploy script are deleted. The TEAL files become static assets checked into version control.

**Compilation command (run once, locally):**
```python
# scripts/compile_contract.py (one-time utility, not part of production)
from blockchain.contracts.treasury_escrow import approval_program, clear_program
from pyteal import compileTeal, Mode

with open("blockchain/contracts/teal/escrow_approval.teal", "w") as f:
    f.write(compileTeal(approval_program(), mode=Mode.Application, version=10))

with open("blockchain/contracts/teal/escrow_clear.teal", "w") as f:
    f.write(compileTeal(clear_program(), mode=Mode.Application, version=10))
```

#### Task 1.2 — Create `AlgorandSDKClient`

New file: `blockchain/sdk_client.py`

This replaces both `algo_client.py` and `simulation.py` with a single, clean SDK wrapper.

```python
# blockchain/sdk_client.py

from algosdk.v2client.algod import AlgodClient
from algosdk.v2client.indexer import IndexerClient
from algosdk import transaction, account, mnemonic, encoding
from algosdk.abi import Contract, Method
from pathlib import Path
from typing import Optional
import os
import logging

logger = logging.getLogger(__name__)

TEAL_DIR = Path(__file__).parent / "contracts" / "teal"


class AlgorandSDKClient:
    """
    Single entry point for all Algorand interactions.
    No PyTeal dependency. Uses pre-compiled TEAL + algosdk only.
    """

    def __init__(self):
        self.algod_address = os.getenv(
            "ALGORAND_ALGOD_ADDRESS",
            "https://testnet-api.algonode.cloud"
        )
        self.algod_token = os.getenv("ALGORAND_ALGOD_TOKEN", "")
        self.indexer_address = os.getenv(
            "ALGORAND_INDEXER_ADDRESS",
            "https://testnet-idx.algonode.cloud"
        )
        self.network = os.getenv("ALGORAND_NETWORK", "testnet")
        self.algod = AlgodClient(self.algod_token, self.algod_address)
        self.indexer = IndexerClient("", self.indexer_address)

        # Load pre-compiled TEAL
        self._approval_teal: Optional[str] = None
        self._clear_teal: Optional[str] = None

    @property
    def approval_teal(self) -> str:
        if self._approval_teal is None:
            self._approval_teal = (TEAL_DIR / "escrow_approval.teal").read_text()
        return self._approval_teal

    @property
    def clear_teal(self) -> str:
        if self._clear_teal is None:
            self._clear_teal = (TEAL_DIR / "escrow_clear.teal").read_text()
        return self._clear_teal

    def get_suggested_params(self) -> transaction.SuggestedParams:
        return self.algod.suggested_params()

    def compile_teal(self, source: str) -> bytes:
        """Compile TEAL source to bytecode via algod compile endpoint."""
        result = self.algod.compile(source)
        return encoding.base64.b64decode(result["result"])

    def submit_and_wait(
        self,
        signed_txn: transaction.SignedTransaction,
        wait_rounds: int = 4
    ) -> dict:
        """Submit a signed transaction and wait for confirmation."""
        tx_id = self.algod.send_transaction(signed_txn)
        result = transaction.wait_for_confirmation(
            self.algod, tx_id, wait_rounds
        )
        return {"tx_id": tx_id, "confirmed_round": result["confirmed-round"]}

    def submit_group_and_wait(
        self,
        signed_txns: list[transaction.SignedTransaction],
        wait_rounds: int = 4
    ) -> dict:
        """Submit an atomic group and wait for confirmation."""
        tx_id = self.algod.send_transactions(signed_txns)
        result = transaction.wait_for_confirmation(
            self.algod, tx_id, wait_rounds
        )
        return {"tx_id": tx_id, "confirmed_round": result["confirmed-round"]}

    def get_account_info(self, address: str) -> dict:
        return self.algod.account_info(address)

    def get_application_info(self, app_id: int) -> dict:
        return self.algod.application_info(app_id)

    def dry_run(self, signed_txn: transaction.SignedTransaction) -> dict:
        """Simulate transaction without broadcasting."""
        dr_request = transaction.create_dryrun(self.algod, [signed_txn])
        return self.algod.dryrun(dr_request)

    def health_check(self) -> dict:
        """Check algod connectivity and node status."""
        try:
            status = self.algod.status()
            return {
                "healthy": True,
                "network": self.network,
                "last_round": status["last-round"],
                "catchup_time": status.get("catchup-time", 0),
            }
        except Exception as e:
            return {"healthy": False, "error": str(e)}


# Singleton instance
_client: Optional[AlgorandSDKClient] = None


def get_algorand_client() -> AlgorandSDKClient:
    global _client
    if _client is None:
        _client = AlgorandSDKClient()
    return _client
```

#### Task 1.3 — Create `EscrowContract` SDK Wrapper

New file: `blockchain/escrow_contract.py`

This replaces `contract_client.py` with clean SDK-native contract interaction.

```python
# blockchain/escrow_contract.py

from algosdk import transaction, account, mnemonic, encoding
from algosdk.abi import Method
from blockchain.sdk_client import get_algorand_client
from typing import Optional
import os
import logging

logger = logging.getLogger(__name__)


class EscrowContract:
    """
    Manages TreasuryEscrow smart contract lifecycle via Algorand SDK.
    No PyTeal dependency — uses pre-compiled TEAL.
    """

    # ARC-4 ABI method signatures matching the compiled contract
    METHOD_FUND = Method.from_signature("fund(pay)void")
    METHOD_RELEASE = Method.from_signature("release(string)void")
    METHOD_REFUND = Method.from_signature("refund(string)void")

    def __init__(self):
        self.client = get_algorand_client()
        self._creator_sk: Optional[str] = None
        self._creator_address: Optional[str] = None

    @property
    def creator_sk(self) -> str:
        if self._creator_sk is None:
            m = os.environ["ALGORAND_ESCROW_CREATOR_MNEMONIC"]
            self._creator_sk = mnemonic.to_private_key(m)
        return self._creator_sk

    @property
    def creator_address(self) -> str:
        if self._creator_address is None:
            self._creator_address = account.address_from_private_key(
                self.creator_sk
            )
        return self._creator_address

    def deploy(
        self,
        buyer_address: str,
        seller_address: str,
        amount_microalgo: int,
        session_id: str,
    ) -> dict:
        """
        Deploy a new escrow application instance.

        Returns:
            {"app_id": int, "app_address": str, "tx_id": str}
        """
        sp = self.client.get_suggested_params()

        approval_compiled = self.client.compile_teal(
            self.client.approval_teal
        )
        clear_compiled = self.client.compile_teal(self.client.clear_teal)

        # Global state: buyer(addr), seller(addr), amount(uint64),
        #               session_id(bytes), funded(uint64), status(uint64)
        global_schema = transaction.StateSchema(
            num_uints=3, num_byte_slices=3
        )
        local_schema = transaction.StateSchema(num_uints=0, num_byte_slices=0)

        # App args: [buyer_address, seller_address, amount, session_id]
        app_args = [
            encoding.decode_address(buyer_address),
            encoding.decode_address(seller_address),
            amount_microalgo.to_bytes(8, "big"),
            session_id.encode("utf-8"),
        ]

        txn = transaction.ApplicationCreateTxn(
            sender=self.creator_address,
            sp=sp,
            on_complete=transaction.OnComplete.NoOpOC,
            approval_program=approval_compiled,
            clear_program=clear_compiled,
            global_schema=global_schema,
            local_schema=local_schema,
            app_args=app_args,
        )

        signed = txn.sign(self.creator_sk)
        result = self.client.submit_and_wait(signed)

        # Extract app_id from confirmed transaction
        app_id = self.client.algod.pending_transaction_info(
            result["tx_id"]
        )["application-index"]
        app_address = encoding.encode_address(
            encoding.checksum(b"appID" + app_id.to_bytes(8, "big"))
        )

        logger.info(
            "Escrow deployed: app_id=%d session=%s", app_id, session_id
        )
        return {
            "app_id": app_id,
            "app_address": app_address,
            "tx_id": result["tx_id"],
        }

    def fund(
        self, app_id: int, funder_sk: str, amount_microalgo: int
    ) -> dict:
        """
        Fund the escrow with a payment transaction.
        Atomic group: PaymentTxn to app_address + AppCallTxn(fund).
        """
        sp = self.client.get_suggested_params()
        funder_address = account.address_from_private_key(funder_sk)
        app_address = encoding.encode_address(
            encoding.checksum(b"appID" + app_id.to_bytes(8, "big"))
        )

        # Payment to escrow address
        pay_txn = transaction.PaymentTxn(
            sender=funder_address,
            sp=sp,
            receiver=app_address,
            amt=amount_microalgo,
        )

        # App call to record funding
        app_txn = transaction.ApplicationCallTxn(
            sender=funder_address,
            sp=sp,
            index=app_id,
            on_complete=transaction.OnComplete.NoOpOC,
            app_args=[b"fund"],
        )

        # Atomic group
        gid = transaction.calculate_group_id([pay_txn, app_txn])
        pay_txn.group = gid
        app_txn.group = gid

        signed_pay = pay_txn.sign(funder_sk)
        signed_app = app_txn.sign(funder_sk)

        result = self.client.submit_group_and_wait(
            [signed_pay, signed_app]
        )
        logger.info("Escrow funded: app_id=%d amount=%d", app_id, amount_microalgo)
        return result

    def release(
        self, app_id: int, merkle_root: str
    ) -> dict:
        """
        Release escrow funds to the seller.
        Includes Merkle root for audit verification.
        """
        sp = self.client.get_suggested_params()

        txn = transaction.ApplicationCallTxn(
            sender=self.creator_address,
            sp=sp,
            index=app_id,
            on_complete=transaction.OnComplete.NoOpOC,
            app_args=[b"release", merkle_root.encode("utf-8")],
        )

        signed = txn.sign(self.creator_sk)
        result = self.client.submit_and_wait(signed)
        logger.info("Escrow released: app_id=%d", app_id)
        return result

    def refund(
        self, app_id: int, reason: str
    ) -> dict:
        """
        Refund escrow funds to the buyer.
        """
        sp = self.client.get_suggested_params()

        txn = transaction.ApplicationCallTxn(
            sender=self.creator_address,
            sp=sp,
            index=app_id,
            on_complete=transaction.OnComplete.NoOpOC,
            app_args=[b"refund", reason.encode("utf-8")],
        )

        signed = txn.sign(self.creator_sk)
        result = self.client.submit_and_wait(signed)
        logger.info("Escrow refunded: app_id=%d reason=%s", app_id, reason)
        return result

    def delete(self, app_id: int) -> dict:
        """Delete escrow application (cleanup)."""
        sp = self.client.get_suggested_params()

        txn = transaction.ApplicationDeleteTxn(
            sender=self.creator_address, sp=sp, index=app_id
        )

        signed = txn.sign(self.creator_sk)
        return self.client.submit_and_wait(signed)
```

#### Task 1.4 — Create Static TEAL Directory Structure

```
blockchain/
├── contracts/
│   ├── teal/
│   │   ├── escrow_approval.teal    # Pre-compiled approval program
│   │   └── escrow_clear.teal       # Pre-compiled clear program
│   └── __init__.py
├── sdk_client.py                    # NEW — AlgorandSDKClient
├── escrow_contract.py               # NEW — EscrowContract
├── escrow_manager.py                # REWRITE (Phase 2)
├── algo_client.py                   # DEPRECATED → remove after migration
├── contract_client.py               # DEPRECATED → remove after migration
├── payment_handler.py               # REFACTOR (Phase 3)
└── simulation.py                    # DEPRECATED → remove
```

### 3.3 Dependencies

- `py-algorand-sdk >= 2.6.0` (already in requirements.txt)
- PyTeal is needed **only once** for the compilation step, then removed from production dependencies
- Algorand testnet node access (Algonode — no API key needed)

### 3.4 Expected Outputs

- `blockchain/sdk_client.py` — production-ready Algorand SDK wrapper
- `blockchain/escrow_contract.py` — complete escrow lifecycle via SDK
- `blockchain/contracts/teal/escrow_approval.teal` — static compiled TEAL
- `blockchain/contracts/teal/escrow_clear.teal` — static compiled TEAL
- Unit tests: `tests/test_sdk_client.py`, `tests/test_escrow_contract.py`
- PyTeal removed from `requirements.txt` production dependencies

---

## 4. Phase 2 — Escrow Lifecycle Rewrite

### 4.1 Objective

Rewrite `escrow_manager.py` (the largest file in the codebase at 1018 lines) to use the new `EscrowContract` SDK wrapper. Remove the 3-level fallback chain. Remove all `SIM-` simulation references from the production code path.

### 4.2 Detailed Technical Tasks

#### Task 2.1 — Rewrite `EscrowManager`

The current `escrow_manager.py` has three execution paths:
1. Smart contract deployment via `TreasuryEscrowClient` (PyTeal)
2. 0-ALGO self-transfer proof transaction (fallback)
3. Simulated `SIM-` reference (fallback of fallback)

The rewrite eliminates paths 2 and 3. The only execution path is the `EscrowContract` SDK wrapper from Phase 1.

**New `blockchain/escrow_manager.py` structure:**

```python
# blockchain/escrow_manager.py (rewritten)

from blockchain.escrow_contract import EscrowContract
from blockchain.sdk_client import get_algorand_client
from db.database import get_session_factory
from db.models import EscrowContract as EscrowModel, Negotiation
from db.audit_logger import AuditLogger
from core.merkle_service import MerkleService
from sqlalchemy import select
from typing import Optional
import logging
import uuid

logger = logging.getLogger(__name__)


class EscrowManager:
    """
    Manages the full escrow lifecycle for agreed negotiation sessions.
    Uses Algorand SDK exclusively — no PyTeal, no simulation fallbacks.
    """

    def __init__(self):
        self.contract = EscrowContract()
        self.audit = AuditLogger()
        self.merkle = MerkleService()

    async def trigger_escrow(self, session_id: str) -> dict:
        """
        Full pipeline: validate session → deploy → persist → audit.
        Called automatically when a session reaches AGREED state.
        """
        session_factory = get_session_factory()
        async with session_factory() as db:
            session = await db.get(Negotiation, session_id)
            if not session or session.status != "AGREED":
                raise ValueError(
                    f"Session {session_id} not in AGREED state"
                )

            # Check idempotency — don't re-deploy
            existing = await db.execute(
                select(EscrowModel).where(
                    EscrowModel.session_id == session_id
                )
            )
            if existing.scalar_one_or_none():
                logger.info("Escrow already exists for session %s", session_id)
                return {"status": "already_deployed"}

            payload = self._build_payload(session)
            deploy_result = self.contract.deploy(
                buyer_address=payload["buyer_address"],
                seller_address=payload["seller_address"],
                amount_microalgo=payload["amount_microalgo"],
                session_id=session_id,
            )

            escrow_record = EscrowModel(
                escrow_id=str(uuid.uuid4()),
                session_id=session_id,
                contract_ref=f"algo-app-{deploy_result['app_id']}",
                app_id=deploy_result["app_id"],
                amount=payload["amount_usdc"],
                status="DEPLOYED",
                deploy_tx_id=deploy_result["tx_id"],
            )
            db.add(escrow_record)
            await db.commit()

            await self.audit.append(
                entity_type="escrow",
                entity_id=escrow_record.escrow_id,
                action="ESCROW_DEPLOYED",
                actor_id="system",
                payload={
                    "session_id": session_id,
                    "app_id": deploy_result["app_id"],
                    "tx_id": deploy_result["tx_id"],
                },
                db=db,
            )

            return {
                "status": "deployed",
                "escrow_id": escrow_record.escrow_id,
                "app_id": deploy_result["app_id"],
                "tx_id": deploy_result["tx_id"],
            }

    async def fund_escrow(
        self, escrow_id: str, funder_mnemonic: str
    ) -> dict:
        """Fund a deployed escrow contract."""
        from algosdk import mnemonic as mn

        session_factory = get_session_factory()
        async with session_factory() as db:
            escrow = await db.get(EscrowModel, escrow_id)
            if not escrow or escrow.status != "DEPLOYED":
                raise ValueError(f"Escrow {escrow_id} not fundable")

            funder_sk = mn.to_private_key(funder_mnemonic)
            result = self.contract.fund(
                app_id=escrow.app_id,
                funder_sk=funder_sk,
                amount_microalgo=int(escrow.amount * 1_000_000),
            )

            escrow.status = "FUNDED"
            escrow.fund_tx_id = result["tx_id"]
            await db.commit()

            return {"status": "funded", "tx_id": result["tx_id"]}

    async def release_escrow(self, escrow_id: str) -> dict:
        """Release escrow to seller with Merkle root verification."""
        session_factory = get_session_factory()
        async with session_factory() as db:
            escrow = await db.get(EscrowModel, escrow_id)
            if not escrow or escrow.status != "FUNDED":
                raise ValueError(f"Escrow {escrow_id} not releasable")

            merkle_info = await self.merkle.get_session_merkle(
                escrow.session_id, db
            )
            merkle_root = merkle_info.get("merkle_root", "no-merkle")

            result = self.contract.release(
                app_id=escrow.app_id, merkle_root=merkle_root
            )

            escrow.status = "RELEASED"
            escrow.release_tx_id = result["tx_id"]
            await db.commit()

            return {"status": "released", "tx_id": result["tx_id"]}

    async def refund_escrow(self, escrow_id: str, reason: str) -> dict:
        """Refund escrow to buyer."""
        session_factory = get_session_factory()
        async with session_factory() as db:
            escrow = await db.get(EscrowModel, escrow_id)
            if not escrow or escrow.status not in ("DEPLOYED", "FUNDED"):
                raise ValueError(f"Escrow {escrow_id} not refundable")

            result = self.contract.refund(
                app_id=escrow.app_id, reason=reason
            )

            escrow.status = "REFUNDED"
            escrow.refund_tx_id = result["tx_id"]
            await db.commit()

            return {"status": "refunded", "tx_id": result["tx_id"]}

    def _build_payload(self, session: Negotiation) -> dict:
        """Build escrow deployment parameters from an agreed session."""
        return {
            "buyer_address": session.buyer_wallet_address,
            "seller_address": session.seller_wallet_address,
            "amount_usdc": float(session.final_agreed_value),
            "amount_microalgo": int(
                session.final_agreed_value * 1_000_000
            ),
        }
```

#### Task 2.2 — Update DB Model for Escrow

Add `deploy_tx_id` column to `escrow_contracts` table if not present:

```python
# In db/models.py — EscrowContract model, add:
deploy_tx_id = Column(String(128), nullable=True)
```

#### Task 2.3 — Remove Deprecated Files

After Phase 2 is verified working:

```bash
# Remove
rm blockchain/contracts/treasury_escrow.py
rm blockchain/contracts/deploy.py
rm blockchain/contract_client.py
rm blockchain/simulation.py

# Remove from requirements.txt
# pyteal (remove this line)
```

#### Task 2.4 — Update `agents/neutral_agent.py`

The neutral agent calls `EscrowManager` on AGREED state. Update the import path:

```python
# OLD
from blockchain.escrow_manager import EscrowManager

# NEW (same import path, but the class is rewritten)
from blockchain.escrow_manager import EscrowManager
# No change needed — the interface is preserved
```

The neutral agent's `_handle_agreed()` method should work unchanged because the `EscrowManager` public API (`trigger_escrow`, `fund_escrow`, `release_escrow`, `refund_escrow`) is preserved.

### 4.3 Dependencies

- Phase 1 complete (`sdk_client.py`, `escrow_contract.py`, TEAL files)
- Database migration for `deploy_tx_id` column

### 4.4 Expected Outputs

- Rewritten `blockchain/escrow_manager.py` (~200 lines, down from 1018)
- No simulation fallbacks — contract deployment is the only path
- All escrow operations produce real on-chain transactions
- Existing tests in `test_state_machine.py` pass (escrow trigger is mocked)
- New test: `tests/test_escrow_manager_sdk.py`

---

## 5. Phase 3 — Payment & Settlement Refactor

### 5.1 Objective

Refactor the x402 payment handler and anchor service to use `AlgorandSDKClient`. Remove simulation token acceptance from the production code path.

### 5.2 Detailed Technical Tasks

#### Task 3.1 — Refactor `core/x402_handler.py`

**Current problems:**
- Accepts `SIM-X402-ALGO-` tokens as valid payment proof
- Directly constructs `algosdk.transaction.PaymentTxn` rather than going through the SDK client
- `X402_SIMULATION_MODE` env var defaults to `false` but simulation code is still reachable

**Changes:**

```python
# core/x402_handler.py — key changes

from blockchain.sdk_client import get_algorand_client

class X402Handler:
    def __init__(self):
        self.client = get_algorand_client()
        self.simulation_mode = os.getenv(
            "X402_SIMULATION_MODE", "false"
        ).lower() == "true"
        self.demo_cap_micro = int(
            os.getenv("X402_DEMO_AMOUNT_MICRO", "100000")
        )

    def build_402_response(
        self,
        seller_address: str,
        amount_microalgo: int,
        session_id: str,
        resource_url: str,
    ) -> dict:
        """Build HTTP 402 Payment Required response body."""
        return {
            "x402_version": "1",
            "network": self.client.network,
            "payment": {
                "receiver": seller_address,
                "amount": min(amount_microalgo, self.demo_cap_micro),
                "note": f"x402:cadencia:{session_id}",
            },
            "resource": resource_url,
        }

    def verify_and_submit_payment(
        self, x_payment_header: str, expected_receiver: str
    ) -> dict:
        """
        Verify X-PAYMENT header contains a valid signed Algorand
        transaction and broadcast it.

        In simulation mode: accepts without broadcasting.
        In production mode: decodes, verifies, and submits.
        """
        if self.simulation_mode:
            return {
                "status": "simulated",
                "tx_id": f"SIM-X402-{uuid.uuid4().hex[:12]}",
            }

        # Decode the signed transaction from the header
        raw_bytes = base64.b64decode(x_payment_header)
        signed_txn = encoding.msgpack_decode(raw_bytes)

        # Verify receiver matches expected
        if signed_txn.transaction.receiver != expected_receiver:
            raise ValueError("Payment receiver mismatch")

        # Submit via SDK client
        result = self.client.submit_and_wait(signed_txn)
        return {"status": "confirmed", "tx_id": result["tx_id"]}
```

**Key change:** `SIM-` tokens are ONLY accepted when `X402_SIMULATION_MODE=true` is explicitly set. No fallback path.

#### Task 3.2 — Refactor `core/anchor_service.py`

```python
# core/anchor_service.py — key changes

from blockchain.sdk_client import get_algorand_client
from algosdk import transaction, account, mnemonic

class AnchorService:
    def __init__(self):
        self.client = get_algorand_client()
        self.enabled = os.getenv("ANCHOR_ENABLED", "true").lower() == "true"
        self.simulation = os.getenv(
            "ALGORAND_SIMULATION", "false"
        ).lower() == "true"

    def anchor_merkle_root(
        self, session_id: str, merkle_root: str
    ) -> dict:
        if not self.enabled:
            return {"status": "disabled"}

        note = f"cadencia:anchor:v1:{session_id}:{merkle_root}"

        if self.simulation:
            return {
                "status": "simulated",
                "tx_id": f"SIM-ANCHOR-{session_id[:8]}",
            }

        # Real on-chain anchor: self-transfer with note
        creator_sk = mnemonic.to_private_key(
            os.environ["ALGORAND_ESCROW_CREATOR_MNEMONIC"]
        )
        creator_address = account.address_from_private_key(creator_sk)
        sp = self.client.get_suggested_params()

        txn = transaction.PaymentTxn(
            sender=creator_address,
            sp=sp,
            receiver=creator_address,
            amt=0,
            note=note.encode("utf-8"),
        )
        signed = txn.sign(creator_sk)
        result = self.client.submit_and_wait(signed)
        return {"status": "anchored", "tx_id": result["tx_id"]}
```

#### Task 3.3 — Refactor `framework/settlement/x402_algorand.py`

Update to reference the new `X402Handler` and `AlgorandSDKClient`:

```python
# framework/settlement/x402_algorand.py — update imports
from core.x402_handler import X402Handler
from blockchain.sdk_client import get_algorand_client

class X402AlgorandSettlement(SettlementProvider):
    def __init__(self):
        self.x402 = X402Handler()
        self.client = get_algorand_client()
        # ... rest unchanged, delegates to x402 handler
```

#### Task 3.4 — Refactor `blockchain/payment_handler.py`

```python
# blockchain/payment_handler.py — update to use SDK client
from blockchain.sdk_client import get_algorand_client
from algosdk import transaction, account, mnemonic

class PaymentHandler:
    def __init__(self):
        self.client = get_algorand_client()

    def send_payment(
        self,
        sender_mnemonic: str,
        receiver_address: str,
        amount_microalgo: int,
        note: str = "",
    ) -> dict:
        sk = mnemonic.to_private_key(sender_mnemonic)
        sender_address = account.address_from_private_key(sk)
        sp = self.client.get_suggested_params()

        txn = transaction.PaymentTxn(
            sender=sender_address,
            sp=sp,
            receiver=receiver_address,
            amt=amount_microalgo,
            note=note.encode("utf-8") if note else None,
        )
        signed = txn.sign(sk)
        return self.client.submit_and_wait(signed)
```

### 5.3 Dependencies

- Phase 1 complete (`sdk_client.py`)
- Environment variables: `X402_SIMULATION_MODE`, `ALGORAND_SIMULATION`, `ANCHOR_ENABLED`

### 5.4 Expected Outputs

- Refactored `core/x402_handler.py` — no implicit simulation fallbacks
- Refactored `core/anchor_service.py` — uses `AlgorandSDKClient`
- Refactored `blockchain/payment_handler.py` — uses `AlgorandSDKClient`
- Refactored `framework/settlement/x402_algorand.py` — updated imports
- `blockchain/algo_client.py` can now be deleted (all callers migrated)
- Test updates: `tests/test_x402.py`, `tests/test_anchor.py`

---

## 6. Phase 4 — Core Engine Cleanup & Multi-Tenancy

### 6.1 Objective

Strip demo scaffolding, rebrand to Cadencia, and make the core engine multi-tenant-ready. No new features — this is a cleanup and stabilization pass.

### 6.2 Detailed Technical Tasks

#### Task 4.1 — Remove Demo Scaffolding

**Files to modify:**

| File | Change |
|---|---|
| `api/main.py` | Remove `DEMO_MODE` bootstrap logic. Remove auto-seed of demo accounts at startup. |
| `api/routes/demo.py` | **DELETE** entirely or move behind `ADMIN_DEMO_ENABLED=true` flag |
| `.env` | Remove `DEMO_MODE=true`, `AUTO_ACTIVATE_ENTERPRISES=true`, hardcoded demo credentials |
| `scripts/seed_demo.py` | Keep as a dev-only script, not called at startup |
| `demo.py` | **DELETE** (CLI demo script) |
| `demo_acf.py` | **DELETE** (ACF demo script) |

#### Task 4.2 — Rebrand to Cadencia

**Files to modify:**

| File | Change |
|---|---|
| `api/main.py` | App title: `Cadencia API`, description updated |
| `a2a_protocol/agent_card.py` | Platform name: `cadencia`, URLs updated |
| `core/anchor_service.py` | Note prefix: `cadencia:anchor:v1:` (already done in Phase 3) |
| `core/x402_handler.py` | Note prefix: `x402:cadencia:` |
| `core/webhook_notifier.py` | Header prefix: `X-Cadencia-Signature`, `X-Cadencia-Event` |
| `api/routes/ui.py` | Config response: `platform_name: "cadencia"` |
| `/.well-known/agent.json` | Agent card: name, description, organization updated |

#### Task 4.3 — Enforce KYC Gating

Currently `AUTO_ACTIVATE_ENTERPRISES=true` bypasses KYC. For production:

```python
# api/routes/auth.py — register endpoint
# After creating enterprise, set kyc_status = "PENDING" always
# Remove the auto-activate shortcut

enterprise.kyc_status = "PENDING"  # Never "ACTIVE" on registration
```

Add a new admin-only endpoint:

```
POST /v1/admin/enterprises/{enterprise_id}/activate
Authorization: Bearer <admin-jwt>

Response: { "status": "ACTIVE" }
```

For the hackathon, add a lightweight self-activation flow:

```
POST /v1/enterprises/{enterprise_id}/verify-kyc
Body: { "pan": "XXXXX1234X", "gst": "22XXXXX1234X1Z5" }

Response: { "kyc_status": "ACTIVE" }  # If PAN/GST format valid
```

#### Task 4.4 — Agent Config Self-Service

Ensure enterprises can configure their agent parameters via API without touching the database:

```
PUT /v1/enterprises/{enterprise_id}/agent-config
Authorization: Bearer <enterprise-jwt>
Body: {
    "agent_role": "buyer",
    "intrinsic_value": 50000.0,
    "risk_factor": 0.05,
    "negotiation_margin": 0.10,
    "concession_curve": "linear",
    "budget_ceiling": 60000.0,
    "max_exposure": 100000.0
}

Response: { "config_id": "uuid", "status": "saved" }
```

This endpoint already exists conceptually in the `enterprises.py` route but needs to be verified and tested as a standalone flow.

#### Task 4.5 — Clean Up Health Check

```python
# api/main.py — /health endpoint
# Replace "A2A Treasury" references with "Cadencia"
# Add version field

@app.get("/health")
async def health():
    return {
        "platform": "cadencia",
        "version": "1.0.0",
        "services": {
            "database": await check_db(),
            "redis": await check_redis(),
            "algorand": get_algorand_client().health_check(),
            "llm": await check_groq(),
            "fx": await check_fx(),
        }
    }
```

### 6.3 Dependencies

- Phases 1–3 complete (blockchain layer migrated)
- No new external dependencies

### 6.4 Expected Outputs

- All demo-only files removed or gated
- Rebranded to "Cadencia" across all API responses, agent cards, webhooks
- KYC gating enforced — no auto-activation
- Agent config self-service verified
- Health check cleaned up
- No `SIM-` references in non-simulation code paths

---

## 7. Phase 5 — Marketplace Discovery & Matchmaking

### 7.1 Objective

Transform the system from a two-party demo into a real marketplace where enterprises discover each other, agents evaluate compatibility, and negotiations start organically.

### 7.2 Detailed Technical Tasks

#### Task 5.1 — Extend Enterprise Model for Marketplace Listings

Add columns to `enterprises` table:

```python
# db/models.py — Enterprise model additions

# Trade profile
trade_role = Column(String(20))           # "buyer", "seller", "both"
commodities = Column(ARRAY(String))        # ["steel", "textiles", "electronics"]
min_order_value = Column(Float)            # Minimum transaction value (USDC)
max_order_value = Column(Float)            # Maximum transaction value (USDC)
preferred_settlement = Column(String(50))  # "escrow", "x402", "both"
geography = Column(String(100))            # "IN", "US", "IN,US"
listing_active = Column(Boolean, default=True)  # Visible in marketplace
```

**Migration:** Add via Alembic or startup auto-migration (existing pattern in `api/main.py`).

#### Task 5.2 — Marketplace Search API

New route module: `api/routes/marketplace.py`

```python
# api/routes/marketplace.py

@router.get("/v1/marketplace/search")
async def search_marketplace(
    role: Optional[str] = Query(None),          # "buyer" or "seller"
    commodity: Optional[str] = Query(None),
    min_value: Optional[float] = Query(None),
    max_value: Optional[float] = Query(None),
    geography: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_enterprise = Depends(get_current_enterprise),
):
    """
    Search the marketplace for counterparties.
    Excludes the requesting enterprise from results.
    Only returns enterprises with kyc_status=ACTIVE and listing_active=True.
    """
    ...
```

#### Task 5.3 — Matchmaking Engine

New file: `core/matchmaking.py`

```python
# core/matchmaking.py

class MatchmakingEngine:
    """
    Scores and ranks potential counterparties for an enterprise.
    Uses: commodity overlap, value range overlap, geography compatibility,
    past negotiation success rate, compliance status.
    """

    async def find_matches(
        self,
        enterprise_id: str,
        commodity: str,
        target_value: float,
        max_results: int = 10,
        db: AsyncSession = None,
    ) -> list[dict]:
        """
        Returns ranked list of matching counterparties.
        Each result includes: enterprise_id, legal_name, match_score,
        agent_card, shared_protocols.
        """
        ...

    def _compute_match_score(
        self,
        seeker: Enterprise,
        candidate: Enterprise,
        commodity: str,
        target_value: float,
    ) -> float:
        """
        Score 0.0–1.0 based on:
        - Commodity overlap (0.4 weight)
        - Value range overlap (0.3 weight)
        - Geography compatibility (0.15 weight)
        - Historical success rate (0.15 weight)
        """
        ...
```

#### Task 5.4 — Discovery → Handshake → Session Pipeline

New endpoint that chains the full flow:

```
POST /v1/marketplace/initiate
Authorization: Bearer <enterprise-jwt>
Body: {
    "counterparty_id": "uuid",
    "commodity": "steel_coils",
    "proposed_value": 45000.00,
    "currency": "USDC"
}

Response: {
    "handshake_id": "uuid",
    "compatible": true,
    "session_id": "uuid",     # if compatible, session auto-created
    "shared_protocols": ["DANP-v1"],
    "status": "NEGOTIATION_READY"
}
```

This endpoint internally:
1. Validates both enterprises are ACTIVE
2. Runs capability handshake
3. If compatible, creates a negotiation session
4. Returns session_id for the frontend to connect to

#### Task 5.5 — Update Agent Card for Marketplace

```python
# a2a_protocol/agent_card.py — extend card generation

def generate_agent_card(enterprise, agent_config):
    return {
        "name": f"cadencia-agent-{enterprise.enterprise_id[:8]}",
        "description": f"Autonomous trade agent for {enterprise.legal_name}",
        "protocols": ["DANP-v1"],
        "settlement_networks": ["algorand-testnet"],
        "payment_methods": ["escrow", "x402"],
        # NEW marketplace fields
        "trade_profile": {
            "role": enterprise.trade_role,
            "commodities": enterprise.commodities,
            "value_range": {
                "min": enterprise.min_order_value,
                "max": enterprise.max_order_value,
            },
            "geography": enterprise.geography,
        },
        "policy_constraints": {
            "compliance_frameworks": ["FEMA", "RBI"],
            "kyc_status": enterprise.kyc_status,
        },
    }
```

### 7.3 Dependencies

- Phase 4 complete (clean enterprise model, KYC gating)
- Existing handshake system (`api/routes/handshake.py`)
- Existing session creation system (`api/routes/sessions.py`)

### 7.4 Expected Outputs

- Extended `enterprises` table with trade profile columns
- `api/routes/marketplace.py` — search and initiation endpoints
- `core/matchmaking.py` — scoring engine
- Updated agent cards with trade profile
- Integration test: register → list marketplace → initiate → session created

---

## 8. Phase 6 — API Hardening & Auth Overhaul

### 8.1 Objective

Secure all endpoints for production deployment. Tighten CORS, add rate limiting, improve error responses, and ensure the API is frontend-integration-ready.

### 8.2 Detailed Technical Tasks

#### Task 6.1 — CORS Configuration

```python
# api/main.py — replace wildcard CORS

ALLOWED_ORIGINS = os.getenv(
    "CORS_ALLOWED_ORIGINS",
    "http://localhost:3000"  # Dev default
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-Correlation-ID"],
)
```

#### Task 6.2 — API Rate Limiting

New middleware or dependency:

```python
# api/middleware.py — add rate limiter

from datetime import datetime, timedelta

class RateLimiter:
    """
    Per-enterprise rate limiting using Redis.
    Limits: 100 requests/minute for standard tier,
    1000/minute for premium.
    """
    async def check(
        self, enterprise_id: str, tier: str = "standard"
    ) -> bool:
        limits = {"standard": 100, "premium": 1000}
        key = f"ratelimit:{enterprise_id}:{datetime.utcnow().minute}"
        count = await self.redis.incr(key)
        if count == 1:
            await self.redis.expire(key, 60)
        return count <= limits.get(tier, 100)
```

#### Task 6.3 — Standardize Error Responses

All API errors should follow a consistent format:

```json
{
    "error": {
        "code": "ESCROW_NOT_FUNDABLE",
        "message": "Escrow abc-123 is not in DEPLOYED state",
        "details": {
            "escrow_id": "abc-123",
            "current_status": "FUNDED"
        }
    },
    "request_id": "corr-xyz-456"
}
```

#### Task 6.4 — JWT Token Refresh

Add a refresh endpoint:

```
POST /v1/auth/refresh
Authorization: Bearer <current-jwt>

Response: {
    "access_token": "new-jwt",
    "expires_in": 86400,
    "token_type": "bearer"
}
```

#### Task 6.5 — API Key Authentication (for B2B integrations)

Wire up the existing `api_keys` table:

```
POST /v1/auth/api-keys
Authorization: Bearer <enterprise-jwt>
Body: {
    "name": "production-key",
    "scopes": ["read:sessions", "write:sessions", "read:escrow"]
}

Response: {
    "key_id": "uuid",
    "api_key": "cad_live_xxxxxxxxxxxx",  # Shown ONCE
    "key_prefix": "cad_live_xxxx",
    "scopes": ["read:sessions", "write:sessions", "read:escrow"]
}
```

API key auth via `X-API-Key` header as an alternative to JWT.

#### Task 6.6 — Request Validation Tightening

Audit all Pydantic schemas for:
- String length limits (prevent oversized payloads)
- Numeric range constraints (no negative amounts, no absurd values)
- Enum validation for status fields
- UUID format validation for all ID fields

### 8.3 Dependencies

- Redis (for rate limiting)
- Existing auth system (JWT)
- Existing `api_keys` DB table

### 8.4 Expected Outputs

- CORS locked to configured origins
- Rate limiting active per enterprise
- Consistent error response format across all endpoints
- JWT refresh endpoint
- API key authentication as JWT alternative
- All Pydantic schemas tightened
- Test: `tests/test_api_hardening.py`

---

## 9. Phase 7 — Deployment Configuration & Production Readiness

### 9.1 Objective

Configure the application for production deployment. Docker, environment management, database migrations, HTTPS, and monitoring.

### 9.2 Detailed Technical Tasks

#### Task 7.1 — Production Environment Configuration

Create `.env.production` template:

```bash
# .env.production

# --- Core ---
APP_NAME=cadencia
APP_VERSION=1.0.0
APP_ENV=production
DEBUG=false

# --- Database ---
DATABASE_URL=postgresql+asyncpg://${DB_USER}:${DB_PASS}@${DB_HOST}:5432/cadencia
DB_POOL_SIZE=20
DB_MAX_OVERFLOW=10

# --- Redis ---
REDIS_URL=redis://${REDIS_HOST}:6379/0

# --- Auth ---
JWT_SECRET_KEY=${JWT_SECRET}  # Generate: openssl rand -hex 32
JWT_ACCESS_EXPIRE_HOURS=24

# --- Algorand ---
ALGORAND_NETWORK=testnet
ALGORAND_ALGOD_ADDRESS=https://testnet-api.algonode.cloud
ALGORAND_INDEXER_ADDRESS=https://testnet-idx.algonode.cloud
ALGORAND_ESCROW_CREATOR_MNEMONIC=${ESCROW_MNEMONIC}
ALGORAND_SIMULATION=false

# --- LLM ---
GROQ_API_KEY=${GROQ_KEY}
GROQ_MODEL=llama-3.3-70b-versatile
LLM_ENABLED=true

# --- x402 ---
X402_SIMULATION_MODE=false
X402_DEMO_AMOUNT_MICRO=100000

# --- FX ---
FX_PROVIDER=frankfurter
FX_SPREAD_BPS=25

# --- Compliance ---
COMPLIANCE_STRICT_MODE=false

# --- Anchoring ---
ANCHOR_ENABLED=true

# --- CORS ---
CORS_ALLOWED_ORIGINS=https://cadencia.app,https://www.cadencia.app

# --- Demo (disabled in production) ---
DEMO_MODE=false
AUTO_ACTIVATE_ENTERPRISES=false
ADMIN_DEMO_ENABLED=false
```

#### Task 7.2 — Docker Production Configuration

Update `docker-compose.prod.yml`:

```yaml
version: "3.9"

services:
  api:
    build:
      context: ./a2a-treasury
      dockerfile: Dockerfile
    command: >
      gunicorn api.main:app
      --worker-class uvicorn.workers.UvicornWorker
      --workers 4
      --bind 0.0.0.0:8000
      --timeout 120
      --access-logfile -
    env_file: .env.production
    ports:
      - "8000:8000"
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: cadencia
      POSTGRES_USER: ${DB_USER}
      POSTGRES_PASSWORD: ${DB_PASS}
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${DB_USER}"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    command: redis-server --appendonly yes
    volumes:
      - redisdata:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  caddy:
    image: caddy:2-alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile
      - caddy_data:/data
    depends_on:
      - api

volumes:
  pgdata:
  redisdata:
  caddy_data:
```

#### Task 7.3 — Caddy Reverse Proxy (HTTPS)

```
# Caddyfile
cadencia.app {
    reverse_proxy api:8000
    encode gzip
    header {
        Strict-Transport-Security "max-age=31536000; includeSubDomains"
        X-Content-Type-Options "nosniff"
        X-Frame-Options "DENY"
    }
}
```

#### Task 7.4 — Database Migration Strategy

Create a startup migration script that runs idempotently:

```python
# scripts/migrate.py

async def run_migrations():
    """
    Idempotent schema migration.
    Checks for missing columns/tables and adds them.
    Runs at container startup before the API accepts traffic.
    """
    async with engine.begin() as conn:
        # Create all tables if not exist
        await conn.run_sync(Base.metadata.create_all)

        # Add new columns for marketplace
        await _add_column_if_missing(conn, "enterprises", "trade_role", "VARCHAR(20)")
        await _add_column_if_missing(conn, "enterprises", "commodities", "TEXT[]")
        await _add_column_if_missing(conn, "enterprises", "min_order_value", "FLOAT")
        await _add_column_if_missing(conn, "enterprises", "max_order_value", "FLOAT")
        await _add_column_if_missing(conn, "enterprises", "listing_active", "BOOLEAN DEFAULT TRUE")
        await _add_column_if_missing(conn, "enterprises", "geography", "VARCHAR(100)")
        await _add_column_if_missing(conn, "escrow_contracts", "deploy_tx_id", "VARCHAR(128)")
```

#### Task 7.5 — Dockerfile Optimization

```dockerfile
# Dockerfile
FROM python:3.12-slim AS base

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl && rm -rf /var/lib/apt/lists/*

# Python deps (cached layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application code
COPY . .

# Pre-compiled TEAL files (static assets)
COPY blockchain/contracts/teal/ blockchain/contracts/teal/

# Non-root user
RUN useradd -m cadencia
USER cadencia

EXPOSE 8000

CMD ["gunicorn", "api.main:app", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--workers", "4", \
     "--bind", "0.0.0.0:8000"]
```

#### Task 7.6 — Frontend Deployment Config

```bash
# a2a-treasury-ui/.env.production

NEXT_PUBLIC_API_URL=https://cadencia.app
NEXT_PUBLIC_PLATFORM_NAME=Cadencia
NEXT_PUBLIC_ALGORAND_NETWORK=testnet
```

### 9.3 Dependencies

- All previous phases complete
- Domain name registered (or use a cloud provider subdomain for hackathon)
- Algorand testnet wallet funded

### 9.4 Expected Outputs

- `.env.production` with all production-safe defaults
- `docker-compose.prod.yml` with health checks and proper orchestration
- `Caddyfile` for HTTPS termination
- `scripts/migrate.py` for idempotent DB setup
- Optimized `Dockerfile`
- Frontend `.env.production`
- Full deployment runbook in `docs/DEPLOY.md`

---

## 10. Complete API Reference

### 10.1 Authentication

#### `POST /v1/auth/register`

Register a new enterprise and admin user.

| Field | Value |
|---|---|
| **Method** | `POST` |
| **Auth** | None |
| **Content-Type** | `application/json` |

**Request:**
```json
{
    "enterprise": {
        "legal_name": "Bharat Steel Corp",
        "pan": "ABCDE1234F",
        "gst": "22ABCDE1234F1Z5",
        "geography": "IN",
        "trade_role": "buyer",
        "commodities": ["steel", "metals"],
        "min_order_value": 10000.0,
        "max_order_value": 500000.0
    },
    "user": {
        "email": "admin@bharatsteel.com",
        "password": "SecureP@ss2026!",
        "full_name": "Rajesh Kumar",
        "role": "admin"
    }
}
```

**Response (201):**
```json
{
    "enterprise_id": "uuid",
    "user_id": "uuid",
    "kyc_status": "PENDING",
    "message": "Registration successful. Complete KYC to activate."
}
```

---

#### `POST /v1/auth/login`

Authenticate and receive JWT.

| Field | Value |
|---|---|
| **Method** | `POST` |
| **Auth** | None |

**Request:**
```json
{
    "email": "admin@bharatsteel.com",
    "password": "SecureP@ss2026!"
}
```

**Response (200):**
```json
{
    "access_token": "eyJhbGciOiJIUzI1NiIs...",
    "token_type": "bearer",
    "expires_in": 86400,
    "enterprise_id": "uuid",
    "role": "admin",
    "kyc_status": "ACTIVE"
}
```

---

#### `POST /v1/auth/refresh`

Refresh an expiring JWT.

| Field | Value |
|---|---|
| **Method** | `POST` |
| **Auth** | `Bearer <jwt>` |

**Response (200):**
```json
{
    "access_token": "new-jwt",
    "expires_in": 86400,
    "token_type": "bearer"
}
```

---

#### `POST /v1/auth/api-keys`

Create a B2B API key.

| Field | Value |
|---|---|
| **Method** | `POST` |
| **Auth** | `Bearer <jwt>` (admin only) |

**Request:**
```json
{
    "name": "production-integration",
    "scopes": ["read:sessions", "write:sessions", "read:escrow"]
}
```

**Response (201):**
```json
{
    "key_id": "uuid",
    "api_key": "cad_live_a1b2c3d4e5f6g7h8",
    "key_prefix": "cad_live_a1b2",
    "scopes": ["read:sessions", "write:sessions", "read:escrow"],
    "warning": "Store this key securely. It will not be shown again."
}
```

---

### 10.2 Enterprise Management

#### `GET /v1/enterprises/{enterprise_id}`

Get enterprise details.

| Field | Value |
|---|---|
| **Method** | `GET` |
| **Auth** | `Bearer <jwt>` |

**Response (200):**
```json
{
    "enterprise_id": "uuid",
    "legal_name": "Bharat Steel Corp",
    "pan": "ABCDE1234F",
    "gst": "22ABCDE1234F1Z5",
    "kyc_status": "ACTIVE",
    "trade_role": "buyer",
    "commodities": ["steel", "metals"],
    "min_order_value": 10000.0,
    "max_order_value": 500000.0,
    "geography": "IN",
    "wallet_address": "JBWICHVZU3CAL43...",
    "agent_card": { ... },
    "created_at": "2026-03-31T10:00:00Z"
}
```

---

#### `PUT /v1/enterprises/{enterprise_id}/agent-config`

Configure agent negotiation parameters.

| Field | Value |
|---|---|
| **Method** | `PUT` |
| **Auth** | `Bearer <jwt>` (enterprise owner) |

**Request:**
```json
{
    "agent_role": "buyer",
    "intrinsic_value": 50000.0,
    "risk_factor": 0.05,
    "negotiation_margin": 0.10,
    "concession_curve": "linear",
    "budget_ceiling": 60000.0,
    "max_exposure": 100000.0
}
```

**Response (200):**
```json
{
    "config_id": "uuid",
    "enterprise_id": "uuid",
    "agent_role": "buyer",
    "status": "saved"
}
```

---

#### `POST /v1/enterprises/{enterprise_id}/verify-kyc`

Lightweight KYC verification for hackathon.

| Field | Value |
|---|---|
| **Method** | `POST` |
| **Auth** | `Bearer <jwt>` (enterprise owner) |

**Request:**
```json
{
    "pan": "ABCDE1234F",
    "gst": "22ABCDE1234F1Z5"
}
```

**Response (200):**
```json
{
    "enterprise_id": "uuid",
    "kyc_status": "ACTIVE",
    "verified_at": "2026-03-31T10:05:00Z"
}
```

---

### 10.3 Marketplace

#### `GET /v1/marketplace/search`

Search for counterparties.

| Field | Value |
|---|---|
| **Method** | `GET` |
| **Auth** | `Bearer <jwt>` |

**Query Parameters:**

| Param | Type | Required | Description |
|---|---|---|---|
| `role` | string | No | Filter by "buyer" or "seller" |
| `commodity` | string | No | Filter by commodity |
| `min_value` | float | No | Minimum order value |
| `max_value` | float | No | Maximum order value |
| `geography` | string | No | Country code filter |
| `page` | int | No | Page number (default: 1) |
| `limit` | int | No | Results per page (default: 20, max: 100) |

**Response (200):**
```json
{
    "results": [
        {
            "enterprise_id": "uuid",
            "legal_name": "Delhi Exports Ltd",
            "trade_role": "seller",
            "commodities": ["steel", "iron_ore"],
            "value_range": { "min": 5000.0, "max": 200000.0 },
            "geography": "IN",
            "match_score": 0.87,
            "agent_card_url": "/v1/enterprises/uuid/agent-card"
        }
    ],
    "total": 42,
    "page": 1,
    "limit": 20
}
```

---

#### `POST /v1/marketplace/initiate`

Initiate a trade with a counterparty (handshake + session creation).

| Field | Value |
|---|---|
| **Method** | `POST` |
| **Auth** | `Bearer <jwt>` |

**Request:**
```json
{
    "counterparty_id": "uuid",
    "commodity": "steel_coils",
    "proposed_value": 45000.00,
    "currency": "USDC",
    "max_rounds": 10,
    "timeout_minutes": 30
}
```

**Response (201):**
```json
{
    "handshake_id": "uuid",
    "compatible": true,
    "shared_protocols": ["DANP-v1"],
    "session_id": "uuid",
    "status": "NEGOTIATION_READY",
    "buyer_enterprise_id": "uuid",
    "seller_enterprise_id": "uuid"
}
```

**Response (409) — Incompatible:**
```json
{
    "handshake_id": "uuid",
    "compatible": false,
    "reason": "No shared settlement networks",
    "buyer_capabilities": ["algorand-testnet"],
    "seller_capabilities": ["ethereum-mainnet"]
}
```

---

### 10.4 Negotiation Sessions

#### `POST /v1/sessions`

Create a negotiation session (typically called by marketplace/initiate, but also available directly).

| Field | Value |
|---|---|
| **Method** | `POST` |
| **Auth** | `Bearer <jwt>` |

**Request:**
```json
{
    "buyer_enterprise_id": "uuid",
    "seller_enterprise_id": "uuid",
    "commodity": "steel_coils",
    "initial_value": 45000.00,
    "currency": "USDC",
    "max_rounds": 10,
    "timeout_minutes": 30,
    "protocol": "DANP-v1"
}
```

**Response (201):**
```json
{
    "session_id": "uuid",
    "status": "INIT",
    "buyer_enterprise_id": "uuid",
    "seller_enterprise_id": "uuid",
    "max_rounds": 10,
    "timeout_at": "2026-03-31T11:00:00Z",
    "created_at": "2026-03-31T10:30:00Z"
}
```

---

#### `POST /v1/sessions/{session_id}/action`

Submit a negotiation action (or trigger autonomous negotiation).

| Field | Value |
|---|---|
| **Method** | `POST` |
| **Auth** | `Bearer <jwt>` |

**Request:**
```json
{
    "action": "counter",
    "value": 47500.00,
    "agent_role": "buyer"
}
```

Valid actions: `counter`, `accept`, `reject`

**Response (200):**
```json
{
    "session_id": "uuid",
    "status": "SELLER_RESPONSE",
    "current_round": 2,
    "last_offer": {
        "agent_role": "buyer",
        "action": "counter",
        "value": 47500.00,
        "confidence": 0.82,
        "strategy_tag": "concede",
        "rationale": "Moved toward midpoint based on seller flexibility"
    },
    "expected_turn": "seller"
}
```

---

#### `POST /v1/sessions/{session_id}/auto-negotiate`

Trigger fully autonomous negotiation (NeutralProtocolEngine).

| Field | Value |
|---|---|
| **Method** | `POST` |
| **Auth** | `Bearer <jwt>` |

**Response (200 — SSE stream):**
```
data: {"round": 1, "agent": "buyer", "action": "counter", "value": 48000.0}

data: {"round": 1, "agent": "seller", "action": "counter", "value": 52000.0}

data: {"round": 2, "agent": "buyer", "action": "counter", "value": 49500.0}

...

data: {"round": 5, "agent": "seller", "action": "accept", "value": 50200.0, "status": "AGREED"}
```

---

#### `GET /v1/sessions`

List sessions for the authenticated enterprise.

| Field | Value |
|---|---|
| **Method** | `GET` |
| **Auth** | `Bearer <jwt>` |

**Query Parameters:**

| Param | Type | Description |
|---|---|---|
| `status` | string | Filter: INIT, AGREED, WALKAWAY, etc. |
| `page` | int | Page number |
| `limit` | int | Results per page |

**Response (200):**
```json
{
    "sessions": [
        {
            "session_id": "uuid",
            "counterparty": "Delhi Exports Ltd",
            "status": "AGREED",
            "final_value": 50200.00,
            "rounds_completed": 5,
            "created_at": "2026-03-31T10:30:00Z"
        }
    ],
    "total": 15,
    "page": 1
}
```

---

#### `GET /v1/sessions/{session_id}`

Get full session details including all rounds.

| Field | Value |
|---|---|
| **Method** | `GET` |
| **Auth** | `Bearer <jwt>` |

**Response (200):**
```json
{
    "session_id": "uuid",
    "status": "AGREED",
    "buyer_enterprise_id": "uuid",
    "seller_enterprise_id": "uuid",
    "max_rounds": 10,
    "current_round": 5,
    "final_agreed_value": 50200.00,
    "merkle_root": "a1b2c3...",
    "anchor_tx_id": "ALGO-TX-...",
    "offers": [
        {
            "round": 1,
            "agent_role": "buyer",
            "action": "counter",
            "value": 48000.0,
            "confidence": 0.75,
            "strategy_tag": "anchor",
            "timestamp": "2026-03-31T10:30:05Z"
        }
    ],
    "escrow": {
        "escrow_id": "uuid",
        "status": "DEPLOYED",
        "app_id": 12345678,
        "deploy_tx_id": "ALGO-TX-..."
    }
}
```

---

### 10.5 Escrow

#### `POST /v1/escrow/{escrow_id}/fund`

Fund a deployed escrow.

| Field | Value |
|---|---|
| **Method** | `POST` |
| **Auth** | `Bearer <jwt>` (buyer enterprise) |

**Request:**
```json
{
    "funder_mnemonic": "word1 word2 ... word25"
}
```

> **Note:** In production, this would use wallet-connect signing rather than mnemonic. For the hackathon/testnet deployment, mnemonic-based signing is acceptable.

**Response (200):**
```json
{
    "escrow_id": "uuid",
    "status": "FUNDED",
    "tx_id": "ALGO-TX-...",
    "amount_microalgo": 50200000000
}
```

---

#### `POST /v1/escrow/{escrow_id}/release`

Release escrow to seller.

| Field | Value |
|---|---|
| **Method** | `POST` |
| **Auth** | `Bearer <jwt>` (admin or platform) |

**Response (200):**
```json
{
    "escrow_id": "uuid",
    "status": "RELEASED",
    "tx_id": "ALGO-TX-...",
    "merkle_root": "a1b2c3..."
}
```

---

#### `POST /v1/escrow/{escrow_id}/refund`

Refund escrow to buyer.

| Field | Value |
|---|---|
| **Method** | `POST` |
| **Auth** | `Bearer <jwt>` (admin or platform) |

**Request:**
```json
{
    "reason": "Seller failed to deliver within SLA"
}
```

**Response (200):**
```json
{
    "escrow_id": "uuid",
    "status": "REFUNDED",
    "tx_id": "ALGO-TX-...",
    "reason": "Seller failed to deliver within SLA"
}
```

---

#### `GET /v1/escrow/{escrow_id}`

Get escrow status.

| Field | Value |
|---|---|
| **Method** | `GET` |
| **Auth** | `Bearer <jwt>` |

**Response (200):**
```json
{
    "escrow_id": "uuid",
    "session_id": "uuid",
    "status": "FUNDED",
    "app_id": 12345678,
    "amount": 50200.0,
    "deploy_tx_id": "ALGO-TX-...",
    "fund_tx_id": "ALGO-TX-...",
    "release_tx_id": null,
    "refund_tx_id": null,
    "created_at": "2026-03-31T10:35:00Z"
}
```

---

### 10.6 x402 Payment Delivery

#### `POST /v1/deliver/initiate`

Seller creates a 402 payment requirement.

| Field | Value |
|---|---|
| **Method** | `POST` |
| **Auth** | `Bearer <jwt>` (seller enterprise) |

**Request:**
```json
{
    "session_id": "uuid",
    "resource_url": "/v1/deliver/resource/uuid"
}
```

**Response (402):**
```json
{
    "x402_version": "1",
    "network": "testnet",
    "payment": {
        "receiver": "CFZRI425PCKOE7PN...",
        "amount": 100000,
        "note": "x402:cadencia:uuid"
    },
    "resource": "/v1/deliver/resource/uuid"
}
```

---

#### `POST /v1/deliver/submit`

Buyer submits signed payment.

| Field | Value |
|---|---|
| **Method** | `POST` |
| **Auth** | `Bearer <jwt>` (buyer enterprise) |
| **Headers** | `X-PAYMENT: <base64-signed-txn>` |

**Request:**
```json
{
    "session_id": "uuid"
}
```

**Response (200):**
```json
{
    "status": "confirmed",
    "tx_id": "ALGO-TX-...",
    "delivery_id": "uuid"
}
```

---

### 10.7 Audit Trail

#### `GET /v1/audit/{entity_type}/{entity_id}`

Get audit trail for an entity.

| Field | Value |
|---|---|
| **Method** | `GET` |
| **Auth** | `Bearer <jwt>` |

**Response (200):**
```json
{
    "entity_type": "negotiation",
    "entity_id": "uuid",
    "chain_valid": true,
    "entries": [
        {
            "log_id": "uuid",
            "action": "SESSION_CREATED",
            "actor_id": "uuid",
            "prev_hash": "0000...",
            "this_hash": "a1b2...",
            "payload": { ... },
            "timestamp": "2026-03-31T10:30:00Z"
        }
    ]
}
```

---

#### `GET /v1/audit/{session_id}/merkle`

Get Merkle proof for a session.

| Field | Value |
|---|---|
| **Method** | `GET` |
| **Auth** | `Bearer <jwt>` |

**Response (200):**
```json
{
    "session_id": "uuid",
    "merkle_root": "a1b2c3...",
    "leaf_count": 12,
    "anchor_tx_id": "ALGO-TX-...",
    "tree": { ... }
}
```

---

#### `POST /v1/audit/verify`

Verify a Merkle proof.

| Field | Value |
|---|---|
| **Method** | `POST` |
| **Auth** | `Bearer <jwt>` |

**Request:**
```json
{
    "leaf_hash": "x1y2z3...",
    "proof": ["hash1", "hash2", "hash3"],
    "root": "a1b2c3..."
}
```

**Response (200):**
```json
{
    "valid": true,
    "leaf_hash": "x1y2z3...",
    "root": "a1b2c3..."
}
```

---

### 10.8 FX Rates

#### `GET /v1/fx/rate`

Get current FX rate.

| Field | Value |
|---|---|
| **Method** | `GET` |
| **Auth** | `Bearer <jwt>` |

**Query Parameters:**

| Param | Type | Description |
|---|---|---|
| `from` | string | Source currency (default: INR) |
| `to` | string | Target currency (default: USD) |

**Response (200):**
```json
{
    "from": "INR",
    "to": "USD",
    "mid_rate": 0.01193,
    "buy_rate": 0.01190,
    "sell_rate": 0.01196,
    "spread_bps": 25,
    "source": "frankfurter",
    "timestamp": "2026-03-31T10:00:00Z"
}
```

---

#### `POST /v1/fx/convert`

Convert amount between currencies.

| Field | Value |
|---|---|
| **Method** | `POST` |
| **Auth** | `Bearer <jwt>` |

**Request:**
```json
{
    "amount": 5000000.0,
    "from": "INR",
    "to": "USDC"
}
```

**Response (200):**
```json
{
    "input_amount": 5000000.0,
    "input_currency": "INR",
    "output_amount": 59650.0,
    "output_currency": "USDC",
    "rate_used": 0.01193,
    "spread_bps": 25
}
```

---

### 10.9 Compliance

#### `POST /v1/compliance/check`

Run FEMA compliance check.

| Field | Value |
|---|---|
| **Method** | `POST` |
| **Auth** | `Bearer <jwt>` |

**Request:**
```json
{
    "session_id": "uuid",
    "transaction_type": "ODI",
    "amount_usd": 125000.0,
    "purpose_code": "P0103"
}
```

**Response (200):**
```json
{
    "record_id": "uuid",
    "status": "COMPLIANT",
    "transaction_type": "ODI",
    "limit_usd": 250000.0,
    "amount_usd": 125000.0,
    "headroom_usd": 125000.0,
    "purpose_code": "P0103",
    "purpose_description": "Export of goods — merchandise"
}
```

---

### 10.10 Treasury Analytics

#### `GET /v1/treasury/dashboard`

Get treasury dashboard data.

| Field | Value |
|---|---|
| **Method** | `GET` |
| **Auth** | `Bearer <jwt>` |

**Response (200):**
```json
{
    "enterprise_id": "uuid",
    "metrics": {
        "total_sessions": 47,
        "agreed_sessions": 32,
        "success_rate": 0.68,
        "total_value_traded": 1520000.0,
        "avg_session_value": 47500.0,
        "active_escrows": 3,
        "total_escrow_value": 142500.0
    },
    "recent_sessions": [ ... ],
    "compliance_summary": {
        "compliant": 30,
        "warning": 2,
        "non_compliant": 0
    }
}
```

---

### 10.11 Framework

#### `GET /v1/framework/protocols`

List available negotiation protocols.

| Field | Value |
|---|---|
| **Method** | `GET` |
| **Auth** | `Bearer <jwt>` |

**Response (200):**
```json
{
    "protocols": [
        {
            "id": "DANP-v1",
            "name": "Decentralized Autonomous Negotiation Protocol",
            "actions": ["counter", "accept", "reject"],
            "features": ["multi_round", "deadline_pressure", "concession_tracking"]
        },
        {
            "id": "FixedPrice-v1",
            "name": "Fixed Price Protocol",
            "actions": ["accept", "reject"],
            "features": ["single_round"]
        }
    ]
}
```

---

#### `GET /v1/framework/settlement-providers`

List available settlement providers.

| Field | Value |
|---|---|
| **Method** | `GET` |
| **Auth** | `Bearer <jwt>` |

**Response (200):**
```json
{
    "providers": [
        {
            "id": "x402-algorand",
            "name": "x402 + Algorand Settlement",
            "networks": ["algorand-testnet"],
            "payment_methods": ["escrow", "x402"],
            "features": ["atomic_settlement", "merkle_verification"]
        }
    ]
}
```

---

### 10.12 Capability Handshake

#### `POST /v1/handshake`

Check protocol compatibility between two enterprises.

| Field | Value |
|---|---|
| **Method** | `POST` |
| **Auth** | `Bearer <jwt>` |

**Request:**
```json
{
    "buyer_enterprise_id": "uuid",
    "seller_enterprise_id": "uuid"
}
```

**Response (200):**
```json
{
    "handshake_id": "uuid",
    "compatible": true,
    "shared_protocols": ["DANP-v1"],
    "shared_networks": ["algorand-testnet"],
    "shared_payment_methods": ["escrow", "x402"],
    "buyer_card": { ... },
    "seller_card": { ... }
}
```

---

### 10.13 Health & System

#### `GET /health`

Deep health check.

| Field | Value |
|---|---|
| **Method** | `GET` |
| **Auth** | None |

**Response (200):**
```json
{
    "platform": "cadencia",
    "version": "1.0.0",
    "status": "healthy",
    "services": {
        "database": { "healthy": true, "latency_ms": 2 },
        "redis": { "healthy": true, "latency_ms": 1 },
        "algorand": { "healthy": true, "network": "testnet", "last_round": 45678901 },
        "llm": { "healthy": true, "provider": "groq", "model": "llama-3.3-70b-versatile" },
        "fx": { "healthy": true, "provider": "frankfurter" }
    }
}
```

---

#### `GET /.well-known/agent.json`

Platform-level A2A agent card.

| Field | Value |
|---|---|
| **Method** | `GET` |
| **Auth** | None |

**Response (200):**
```json
{
    "name": "cadencia-platform",
    "description": "B2B Agentic Commerce Marketplace",
    "organization": "Cadencia",
    "protocols": ["DANP-v1", "FixedPrice-v1"],
    "settlement_networks": ["algorand-testnet"],
    "payment_methods": ["escrow", "x402"],
    "capabilities": {
        "autonomous_negotiation": true,
        "multi_party": true,
        "compliance_frameworks": ["FEMA", "RBI"],
        "audit_type": "merkle_hash_chain"
    }
}
```

---

## 11. File-Level Change Manifest

### 11.1 Files to CREATE

| File | Phase | Description |
|---|---|---|
| `blockchain/sdk_client.py` | 1 | Algorand SDK wrapper (singleton) |
| `blockchain/escrow_contract.py` | 1 | Escrow smart contract SDK interaction |
| `blockchain/contracts/teal/escrow_approval.teal` | 1 | Pre-compiled TEAL approval program |
| `blockchain/contracts/teal/escrow_clear.teal` | 1 | Pre-compiled TEAL clear program |
| `scripts/compile_contract.py` | 1 | One-time PyTeal → TEAL compilation (dev only) |
| `core/matchmaking.py` | 5 | Marketplace matchmaking engine |
| `api/routes/marketplace.py` | 5 | Marketplace search & initiation endpoints |
| `api/schemas/marketplace.py` | 5 | Marketplace Pydantic schemas |
| `.env.production` | 7 | Production environment template |
| `Caddyfile` | 7 | HTTPS reverse proxy config |
| `scripts/migrate.py` | 7 | Idempotent DB migration script |
| `docs/DEPLOY.md` | 7 | Deployment runbook |
| `tests/test_sdk_client.py` | 1 | SDK client tests |
| `tests/test_escrow_contract.py` | 1 | Escrow contract tests |
| `tests/test_escrow_manager_sdk.py` | 2 | Rewritten escrow manager tests |
| `tests/test_marketplace.py` | 5 | Marketplace API tests |
| `tests/test_api_hardening.py` | 6 | Rate limiting, CORS, error format tests |

### 11.2 Files to REWRITE

| File | Phase | Reason |
|---|---|---|
| `blockchain/escrow_manager.py` | 2 | Replace 1018-line PyTeal orchestrator with ~200-line SDK version |
| `core/x402_handler.py` | 3 | Remove implicit simulation fallbacks, use SDK client |
| `core/anchor_service.py` | 3 | Use SDK client for on-chain anchor |
| `blockchain/payment_handler.py` | 3 | Use SDK client for payments |

### 11.3 Files to REFACTOR (Modify in Place)

| File | Phase | Changes |
|---|---|---|
| `api/main.py` | 4 | Remove demo bootstrap, rebrand to Cadencia, update CORS |
| `api/routes/auth.py` | 4, 6 | Remove auto-activate, add refresh & API key endpoints |
| `api/routes/enterprises.py` | 4, 5 | Add KYC verification, trade profile management |
| `api/routes/sessions.py` | 5 | Wire marketplace-initiated session creation |
| `api/routes/handshake.py` | 5 | Support marketplace initiation flow |
| `api/middleware.py` | 6 | Add rate limiter, improve error handlers |
| `api/dependencies.py` | 6 | Add API key auth dependency |
| `api/schemas/auth.py` | 6 | Add refresh, API key schemas |
| `api/schemas/enterprise.py` | 5 | Add trade profile fields |
| `a2a_protocol/agent_card.py` | 4, 5 | Rebrand, add trade profile to card |
| `core/webhook_notifier.py` | 4 | Rebrand headers: `X-Cadencia-*` |
| `db/models.py` | 2, 5 | Add `deploy_tx_id`, marketplace columns |
| `framework/settlement/x402_algorand.py` | 3 | Update imports to new SDK client |
| `docker-compose.prod.yml` | 7 | Add Caddy, health checks, volume config |
| `Dockerfile` | 7 | Optimize layers, add TEAL static assets |
| `requirements.txt` | 1 | Remove `pyteal`, ensure `py-algorand-sdk>=2.6.0` |

### 11.4 Files to DELETE

| File | Phase | Reason |
|---|---|---|
| `blockchain/contracts/treasury_escrow.py` | 2 | PyTeal source — replaced by static TEAL |
| `blockchain/contracts/deploy.py` | 2 | PyTeal compilation script — no longer needed |
| `blockchain/contract_client.py` | 2 | PyTeal ABI client — replaced by `escrow_contract.py` |
| `blockchain/simulation.py` | 2 | Folded into SDK client `dry_run()` |
| `blockchain/algo_client.py` | 3 | Replaced by `sdk_client.py` |
| `demo.py` | 4 | CLI demo script — no longer needed |
| `demo_acf.py` | 4 | ACF demo script — no longer needed |
| `api/routes/demo.py` | 4 | Demo route (or gate behind admin flag) |

### 11.5 Data Flow Changes

**Before (PyTeal flow):**
```
Session AGREED
  → EscrowManager.trigger_escrow()
    → contract_client.deploy_new_escrow()
      → PyTeal compile at runtime
      → ApplicationCreateTxn
    → FALLBACK: 0-ALGO proof tx
    → FALLBACK: SIM- reference
  → DB persist
```

**After (SDK flow):**
```
Session AGREED
  → EscrowManager.trigger_escrow()
    → EscrowContract.deploy()
      → Load pre-compiled TEAL from disk
      → algod.compile() → bytecode
      → ApplicationCreateTxn via algosdk
      → submit_and_wait()
    → NO FALLBACKS — failure is an error
  → DB persist
  → AuditLogger.append()
```

**Before (x402 flow):**
```
X-PAYMENT header received
  → Decode signed txn
  → IF starts with "SIM-": accept as valid
  → ELSE: submit to Algorand
```

**After (x402 flow):**
```
X-PAYMENT header received
  → IF X402_SIMULATION_MODE=true: return simulated result
  → ELSE: decode → verify receiver → submit via SDK client → confirm
  → NO implicit SIM- acceptance
```

---

## 12. Data Flow Diagrams

### 12.1 Complete User Journey (Production)

```
┌──────────────────────────────────────────────────────────────────┐
│                        USER JOURNEY                              │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. REGISTER                                                     │
│     POST /v1/auth/register                                       │
│     → Enterprise created (kyc_status=PENDING)                    │
│     → User account created                                       │
│                                                                  │
│  2. KYC VERIFICATION                                             │
│     POST /v1/enterprises/{id}/verify-kyc                         │
│     → PAN/GST validated → kyc_status=ACTIVE                     │
│                                                                  │
│  3. CONFIGURE AGENT                                              │
│     PUT /v1/enterprises/{id}/agent-config                        │
│     → Intrinsic value, risk factor, margins saved                │
│                                                                  │
│  4. DISCOVER COUNTERPARTIES                                      │
│     GET /v1/marketplace/search?role=seller&commodity=steel       │
│     → Ranked list of matching sellers                            │
│                                                                  │
│  5. INITIATE TRADE                                               │
│     POST /v1/marketplace/initiate                                │
│     → Capability handshake → Session created                     │
│                                                                  │
│  6. AUTONOMOUS NEGOTIATION                                       │
│     POST /v1/sessions/{id}/auto-negotiate                        │
│     → SSE stream of rounds → AGREED / WALKAWAY                  │
│                                                                  │
│  7. ESCROW (if AGREED)                                           │
│     [Auto] EscrowManager.trigger_escrow()                        │
│     → Smart contract deployed on Algorand                        │
│     POST /v1/escrow/{id}/fund → Buyer funds escrow              │
│     POST /v1/escrow/{id}/release → Seller receives funds        │
│                                                                  │
│  8. AUDIT VERIFICATION                                           │
│     GET /v1/audit/negotiation/{session_id}                       │
│     → SHA-256 hash chain + Merkle proof + on-chain anchor        │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

### 12.2 Escrow Lifecycle (Post-Migration)

```
AGREED ──→ deploy() ──→ DEPLOYED ──→ fund() ──→ FUNDED
                                                  │
                                         ┌────────┴────────┐
                                         │                 │
                                    release()          refund()
                                         │                 │
                                         ▼                 ▼
                                     RELEASED          REFUNDED
                                         │                 │
                                    [optional]        [optional]
                                         │                 │
                                      delete()          delete()
```

### 12.3 Phase Dependency Graph

```
Phase 1 (SDK Layer)
    │
    ├──→ Phase 2 (Escrow Rewrite) ──→ Phase 3 (Payment Refactor)
    │                                       │
    │                                       ▼
    └──────────────────────────────→ Phase 4 (Cleanup & Rebrand)
                                           │
                                           ▼
                                    Phase 5 (Marketplace)
                                           │
                                           ▼
                                    Phase 6 (API Hardening)
                                           │
                                           ▼
                                    Phase 7 (Deployment)
```

---

> **Estimated effort:** Phases 1–3 (blockchain migration): ~2–3 days. Phase 4 (cleanup): ~1 day. Phase 5 (marketplace): ~2 days. Phase 6 (hardening): ~1 day. Phase 7 (deployment): ~1 day. **Total: ~7–9 days for a focused sprint.**
