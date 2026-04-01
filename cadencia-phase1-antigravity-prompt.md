# Cadencia Phase 1 — Antigravity Implementation Prompt
**Project:** Cadencia B2B Agentic Commerce Marketplace  
**Task:** Phase 1 — Clean Code Foundation (SDK Layer + Simulation Removal + Demo Scaffolding Cleanup)  
**Audience:** Antigravity AI Coding Agent  
**Goal:** Produce a production-grade, fully refactorable backend with zero hardcoded simulations, zero PyTeal runtime dependencies, and zero demo scaffolding in the main app path.

---

## Context

You are working on the backend of **Cadencia** — a B2B agentic commerce marketplace built on FastAPI, PostgreSQL, Redis, and the Algorand blockchain. The current codebase (`a2a-treasury` Python backend) was built as a hackathon prototype. It works but it is full of simulation fallbacks, PyTeal runtime compilation, hardcoded demo credentials, and auto-seeding logic that masks real failures.

**Your mission for Phase 1 is not to add features. It is to clean the foundation so the codebase is ready to be fully refactored into a proper functional B2B SaaS agentic marketplace.** Every change you make must be deliberate, traceable, and preserve the existing working API surface for the frontend (`a2a-treasury-ui`).

Read this entire prompt before writing a single line of code. Execute tasks in the exact order given. Do not skip steps. Do not add features beyond what is described. Do not break existing test coverage without immediately providing a replacement.

---

## The Three Problems You Are Solving

### Problem 1 — PyTeal Runtime Compilation
The current escrow flow compiles PyTeal smart contracts **at runtime** during every escrow deployment. This means:
- The PyTeal library must be present in production
- A version mismatch crashes the deployment
- There is no ARC-4 ABI compliance
- The system has a 3-level fallback chain: (1) real contract → (2) 0-ALGO proof transaction → (3) `SIM-` reference string

After Phase 1, there is **one path and one path only**: pre-compiled static TEAL loaded from disk, deployed via `py-algorand-sdk`. No fallbacks. Failures are real errors.

### Problem 2 — Simulation Tokens Leaking Into Production
The `X402SIMULATIONMODE` env var defaults to `false`, but `SIM-X402-ALGO-` prefixed tokens are still accepted as valid payment proof. The anchor service has its own `ALGORANDSIMULATION` flag with `SIM-ANCHOR-` tokens. These must be fully gated — when simulation mode is off, simulation tokens are **rejected**, not silently accepted.

### Problem 3 — Demo Scaffolding Running in Production
`DEMOMODE=true` and `AUTOACTIVATEENTERPRISES=true` are currently default. The app auto-seeds demo accounts at startup. `apiroutes/demo.py` runs freely. `demo.py` and `demoacf.py` CLI scripts exist at project root. These must be removed from the main application path and either deleted or gated behind an explicit `ADMIN_DEMO_ENABLED=true` flag.

---

## Phase 1 Task List — Execute in This Order

### TASK 1.1 — One-Time PyTeal Compilation (Run Locally, Not in Production)

**Purpose:** Extract the pre-compiled TEAL from the existing `treasuryescrow.py` PyTeal source. This is a one-time dev operation. The output files become permanent static assets.

**Step 1:** Create `scripts/compile_contract.py`:

```python
# scripts/compile_contract.py
# ONE-TIME UTILITY — run locally, not in production
# Output: blockchain/contracts/teal/escrow_approval.teal
#         blockchain/contracts/teal/escrow_clear.teal

from blockchain.contracts.treasury_escrow import approval_program, clear_program
from pyteal import compileTeal, Mode
from pathlib import Path

OUT_DIR = Path(__file__).parent.parent / "blockchain" / "contracts" / "teal"
OUT_DIR.mkdir(parents=True, exist_ok=True)

with open(OUT_DIR / "escrow_approval.teal", "w") as f:
    f.write(compileTeal(approval_program(), mode=Mode.Application, version=10))

with open(OUT_DIR / "escrow_clear.teal", "w") as f:
    f.write(compileTeal(clear_program(), mode=Mode.Application, version=10))

print(f"TEAL files written to {OUT_DIR}")
```

**Step 2:** Run it **once** from your local dev environment:
```bash
python scripts/compile_contract.py
```

**Step 3:** Verify both files exist and are non-empty:
- `blockchain/contracts/teal/escrow_approval.teal`
- `blockchain/contracts/teal/escrow_clear.teal`

**Step 4:** Commit both `.teal` files to version control. They are now static assets.

**Step 5:** Do NOT run this script again. Do NOT call it from `main.py` or any application startup code. It is a dev-only utility.

---

### TASK 1.2 — Create `blockchain/sdk_client.py`

**Purpose:** A single clean entry point for all Algorand interactions. Replaces both `blockchain/algo_client.py` and `blockchain/simulation.py`. No PyTeal dependency.

**Create this file exactly:**

```python
# blockchain/sdk_client.py
# Single entry point for all Algorand interactions.
# No PyTeal. Uses pre-compiled TEAL + py-algorand-sdk only.

from algosdk.v2client.algod import AlgodClient
from algosdk.v2client.indexer import IndexerClient
from algosdk import transaction, account, mnemonic, encoding
from pathlib import Path
from typing import Optional
import os
import logging

logger = logging.getLogger(__name__)

TEAL_DIR = Path(__file__).parent / "contracts" / "teal"


class AlgorandSDKClient:
    """
    Clean Algorand SDK wrapper. Single source of truth for all on-chain operations.
    No simulation fallbacks in this class — callers handle simulation via env flags.
    """

    def __init__(self):
        self.algod_address = os.getenv("ALGORAND_ALGOD_ADDRESS", "https://testnet-api.algonode.cloud")
        self.algod_token = os.getenv("ALGORAND_ALGOD_TOKEN", "")
        self.indexer_address = os.getenv("ALGORAND_INDEXER_ADDRESS", "https://testnet-idx.algonode.cloud")
        self.network = os.getenv("ALGORAND_NETWORK", "testnet")
        self.algod = AlgodClient(self.algod_token, self.algod_address)
        self.indexer = IndexerClient("", self.indexer_address)
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
        import base64
        result = self.algod.compile(source)
        return base64.b64decode(result["result"])

    def submit_and_wait(
        self,
        signed_txn: transaction.SignedTransaction,
        wait_rounds: int = 4,
    ) -> dict:
        txid = self.algod.send_transaction(signed_txn)
        result = transaction.wait_for_confirmation(self.algod, txid, wait_rounds)
        return {"txid": txid, "confirmed_round": result["confirmed-round"]}

    def submit_group_and_wait(
        self,
        signed_txns: list,
        wait_rounds: int = 4,
    ) -> dict:
        txid = self.algod.send_transactions(signed_txns)
        result = transaction.wait_for_confirmation(self.algod, txid, wait_rounds)
        return {"txid": txid, "confirmed_round": result["confirmed-round"]}

    def get_account_info(self, address: str) -> dict:
        return self.algod.account_info(address)

    def get_application_info(self, app_id: int) -> dict:
        return self.algod.application_info(app_id)

    def dry_run(self, signed_txn: transaction.SignedTransaction) -> dict:
        dr_request = transaction.create_dryrun(self.algod, [signed_txn])
        return self.algod.dryrun(dr_request)

    def health_check(self) -> dict:
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


# Singleton
_client: Optional[AlgorandSDKClient] = None


def get_algorand_client() -> AlgorandSDKClient:
    global _client
    if _client is None:
        _client = AlgorandSDKClient()
    return _client
```

**Write tests:** Create `tests/test_sdk_client.py` covering:
- `health_check()` returns expected structure
- `compile_teal()` with a minimal valid TEAL program
- `get_suggested_params()` returns a `SuggestedParams` object
- Mock `AlgodClient` in all tests — do not hit the network in unit tests

---

### TASK 1.3 — Create `blockchain/escrow_contract.py`

**Purpose:** Replaces `blockchain/contract_client.py` with clean SDK-native contract interaction. No PyTeal. Uses pre-compiled TEAL via `AlgorandSDKClient`.

**Create this file exactly:**

```python
# blockchain/escrow_contract.py
# EscrowContract — manages TreasuryEscrow smart contract lifecycle.
# No PyTeal. Uses pre-compiled TEAL from disk + py-algorand-sdk ARC-4 ABI calls.

from algosdk import transaction, account, mnemonic, encoding
from blockchain.sdk_client import get_algorand_client
from typing import Optional
import os
import logging

logger = logging.getLogger(__name__)


class EscrowContract:
    """
    Manages the TreasuryEscrow smart contract lifecycle via the Algorand SDK.
    All methods interact directly with the pre-compiled TEAL approval program.
    ARC-4 ABI method signatures match the compiled contract.
    """

    # ARC-4 ABI method selectors (4-byte selectors from method signatures)
    METHOD_FUND = b"fund(pay)void"
    METHOD_RELEASE = b"release(string)void"
    METHOD_REFUND = b"refund(string)void"

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
            self._creator_address = account.address_from_private_key(self.creator_sk)
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
        Returns: {app_id, app_address, txid}
        Raises on failure — no fallback.
        """
        sp = self.client.get_suggested_params()
        approval_compiled = self.client.compile_teal(self.client.approval_teal)
        clear_compiled = self.client.compile_teal(self.client.clear_teal)

        global_schema = transaction.StateSchema(num_uints=3, num_byte_slices=3)
        local_schema = transaction.StateSchema(num_uints=0, num_byte_slices=0)

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

        txid = result["txid"]
        app_id = self.client.algod.pending_transaction_info(txid)["application-index"]
        app_address = encoding.encode_address(
            encoding.checksum(b"appID" + app_id.to_bytes(8, "big"))
        )

        logger.info("Escrow deployed app_id=%d session=%s", app_id, session_id)
        return {"app_id": app_id, "app_address": app_address, "txid": txid}

    def fund(self, app_id: int, funder_sk: str, amount_microalgo: int) -> dict:
        """
        Fund the escrow. Atomic group: PaymentTxn to app_address + AppCallTxn(fund).
        """
        sp = self.client.get_suggested_params()
        funder_address = account.address_from_private_key(funder_sk)
        app_address = encoding.encode_address(
            encoding.checksum(b"appID" + app_id.to_bytes(8, "big"))
        )

        pay_txn = transaction.PaymentTxn(
            sender=funder_address, sp=sp, receiver=app_address, amt=amount_microalgo
        )
        app_txn = transaction.ApplicationCallTxn(
            sender=funder_address,
            sp=sp,
            index=app_id,
            on_complete=transaction.OnComplete.NoOpOC,
            app_args=[b"fund"],
        )

        gid = transaction.calculate_group_id([pay_txn, app_txn])
        pay_txn.group = gid
        app_txn.group = gid

        signed_pay = pay_txn.sign(funder_sk)
        signed_app = app_txn.sign(funder_sk)

        result = self.client.submit_group_and_wait([signed_pay, signed_app])
        logger.info("Escrow funded app_id=%d amount=%d", app_id, amount_microalgo)
        return result

    def release(self, app_id: int, merkle_root: str) -> dict:
        """
        Release escrow funds to seller. Includes Merkle root for audit trail.
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
        logger.info("Escrow released app_id=%d", app_id)
        return result

    def refund(self, app_id: int, reason: str) -> dict:
        """
        Refund escrow funds to buyer.
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
        logger.info("Escrow refunded app_id=%d reason=%s", app_id, reason)
        return result

    def delete(self, app_id: int) -> dict:
        """
        Delete escrow application — cleanup after settlement.
        """
        sp = self.client.get_suggested_params()
        txn = transaction.ApplicationDeleteTxn(
            sender=self.creator_address, sp=sp, index=app_id
        )
        signed = txn.sign(self.creator_sk)
        return self.client.submit_and_wait(signed)
```

**Write tests:** Create `tests/test_escrow_contract.py` covering:
- `deploy()` produces correct `ApplicationCreateTxn` structure
- `fund()` builds a proper atomic group with matching group IDs
- `release()` and `refund()` produce `ApplicationCallTxn` with correct `app_args`
- All Algorand calls are mocked — no network calls in unit tests

---

### TASK 1.4 — Rewrite `blockchain/escrow_manager.py`

**Purpose:** Replace the current 1018-line file with a clean ~200-line version. Eliminate the 3-level fallback chain. The only execution path is `EscrowContract` from Task 1.3.

**Rules for the rewrite:**
1. The public method signatures (`trigger_escrow`, `fund_escrow`, `release_escrow`, `refund_escrow`) must remain unchanged — `agents/neutral_agent.py` calls these and must not require changes.
2. Remove ALL references to `SIM-`, simulation references, and fallback proof transactions.
3. Failure to deploy a real contract is an exception, not a fallback condition.
4. Add `deploy_txid` field to the `EscrowContract` DB model if not already present (see Task 1.5).

**Rewrite `blockchain/escrow_manager.py` with this structure:**

```python
# blockchain/escrow_manager.py
# Manages the full escrow lifecycle for agreed negotiation sessions.
# Uses Algorand SDK exclusively. No PyTeal, no simulation fallbacks.
# Failure to deploy is an error, not a fallback condition.

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

    def __init__(self):
        self.contract = EscrowContract()
        self.audit = AuditLogger()
        self.merkle = MerkleService()

    async def trigger_escrow(self, session_id: str) -> dict:
        """
        Full pipeline: validate session → deploy contract → persist → audit.
        Called automatically when a session reaches AGREED state.
        Raises ValueError if session is not in AGREED state.
        Raises RuntimeError if contract deployment fails.
        """
        session_factory = get_session_factory()
        async with session_factory() as db:
            session = await db.get(Negotiation, session_id)
            if not session or session.status != "AGREED":
                raise ValueError(f"Session {session_id} not in AGREED state")

            # Idempotency check
            existing = await db.execute(
                select(EscrowModel).where(EscrowModel.session_id == session_id)
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
                deploy_txid=deploy_result["txid"],
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
                    "txid": deploy_result["txid"],
                },
                db=db,
            )

            return {
                "status": "deployed",
                "escrow_id": escrow_record.escrow_id,
                "app_id": deploy_result["app_id"],
                "txid": deploy_result["txid"],
            }

    async def fund_escrow(self, escrow_id: str, funder_mnemonic: str) -> dict:
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
            escrow.fund_txid = result["txid"]
            await db.commit()
            return {"status": "funded", "txid": result["txid"]}

    async def release_escrow(self, escrow_id: str) -> dict:
        """Release escrow to seller with Merkle root verification."""
        session_factory = get_session_factory()
        async with session_factory() as db:
            escrow = await db.get(EscrowModel, escrow_id)
            if not escrow or escrow.status != "FUNDED":
                raise ValueError(f"Escrow {escrow_id} not releasable")
            merkle_info = await self.merkle.get_session_merkle(escrow.session_id, db)
            merkle_root = merkle_info.get("merkle_root", "no-merkle")
            result = self.contract.release(app_id=escrow.app_id, merkle_root=merkle_root)
            escrow.status = "RELEASED"
            escrow.release_txid = result["txid"]
            await db.commit()
            return {"status": "released", "txid": result["txid"]}

    async def refund_escrow(self, escrow_id: str, reason: str) -> dict:
        """Refund escrow to buyer."""
        session_factory = get_session_factory()
        async with session_factory() as db:
            escrow = await db.get(EscrowModel, escrow_id)
            if not escrow or escrow.status not in ("DEPLOYED", "FUNDED"):
                raise ValueError(f"Escrow {escrow_id} not refundable")
            result = self.contract.refund(app_id=escrow.app_id, reason=reason)
            escrow.status = "REFUNDED"
            escrow.refund_txid = result["txid"]
            await db.commit()
            return {"status": "refunded", "txid": result["txid"]}

    def _build_payload(self, session: Negotiation) -> dict:
        return {
            "buyer_address": session.buyer_wallet_address,
            "seller_address": session.seller_wallet_address,
            "amount_usdc": float(session.final_agreed_value),
            "amount_microalgo": int(session.final_agreed_value * 1_000_000),
        }
```

**Write tests:** Create `tests/test_escrow_manager_sdk.py` covering:
- `trigger_escrow` raises `ValueError` on non-AGREED session
- `trigger_escrow` calls `EscrowContract.deploy` on a valid AGREED session
- `trigger_escrow` is idempotent (second call returns `already_deployed`)
- `fund_escrow`, `release_escrow`, `refund_escrow` enforce status preconditions
- All DB and blockchain calls are mocked

---

### TASK 1.5 — DB Model: Add `deploy_txid` Column

In `db/models.py`, locate the `EscrowContract` ORM model and add the `deploy_txid` column if it is not already present:

```python
# In db/models.py — EscrowContract model
deploy_txid = Column(String(128), nullable=True)
```

Then create an Alembic migration (or add to the startup auto-migration logic if that is how this codebase handles schema changes) to add the column to the `escrow_contracts` table.

---

### TASK 1.6 — Refactor `core/x402_handler.py`

**Purpose:** Remove implicit `SIM-` token acceptance from the production code path. Simulation is only active when `X402_SIMULATION_MODE=true` is explicitly set.

**Key changes:**

1. Inject `AlgorandSDKClient` via `get_algorand_client()` instead of constructing `AlgodClient` directly.
2. The `verify_and_submit_payment` method must follow this exact logic:

```python
def verify_and_submit_payment(self, x_payment_header: str, expected_receiver: str) -> dict:
    if self.simulation_mode:
        import uuid
        return {"status": "simulated", "txid": f"SIM-X402-{uuid.uuid4().hex[:12]}"}
    
    # Production path — no SIM- tokens accepted
    import base64
    from algosdk import encoding
    raw_bytes = base64.b64decode(x_payment_header)
    signed_txn = encoding.msgpack_decode(raw_bytes)
    
    if signed_txn.transaction.receiver != expected_receiver:
        raise ValueError("Payment receiver mismatch")
    
    result = self.client.submit_and_wait(signed_txn)
    return {"status": "confirmed", "txid": result["txid"]}
```

3. Remove the `demo_cap_micro` cap logic from `build_402_response` or gate it explicitly behind `X402_DEMO_AMOUNT_MICRO` only when `X402_SIMULATION_MODE=true`.
4. Update the `__init__` to use `get_algorand_client()`.

---

### TASK 1.7 — Refactor `core/anchor_service.py`

**Purpose:** Use `AlgorandSDKClient` for on-chain anchor. Remove `SIM-ANCHOR-` token generation when simulation mode is off.

**Key changes:**

```python
def anchor_merkle_root(self, session_id: str, merkle_root: str) -> dict:
    if not self.enabled:
        return {"status": "disabled"}
    
    if self.simulation:
        return {"status": "simulated", "txid": f"SIM-ANCHOR-{session_id[:8]}"}
    
    # Real on-chain anchor
    from algosdk import mnemonic as mn, account, transaction
    note = f"cadencia:anchor:v1:{session_id}:{merkle_root}"
    creator_sk = mn.to_private_key(os.environ["ALGORAND_ESCROW_CREATOR_MNEMONIC"])
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
    return {"status": "anchored", "txid": result["txid"]}
```

**Also update `__init__`:**
```python
def __init__(self):
    self.client = get_algorand_client()
    self.enabled = os.getenv("ANCHOR_ENABLED", "true").lower() == "true"
    self.simulation = os.getenv("ALGORAND_SIMULATION", "false").lower() == "true"
```

---

### TASK 1.8 — Refactor `blockchain/payment_handler.py`

Remove direct `AlgodClient` instantiation. Replace with `get_algorand_client()`:

```python
from blockchain.sdk_client import get_algorand_client
from algosdk import transaction, account, mnemonic

class PaymentHandler:
    def __init__(self):
        self.client = get_algorand_client()

    def send_payment(
        self, sender_mnemonic: str, receiver_address: str, amount_microalgo: int, note: str = ""
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

---

### TASK 1.9 — Refactor `framework/settlement/x402_algorand.py`

Update imports to point to the refactored `X402Handler` and `AlgorandSDKClient`. The class logic itself does not need to change — only the import paths and `__init__` instantiation:

```python
from core.x402_handler import X402Handler
from blockchain.sdk_client import get_algorand_client
```

Ensure `X402AlgorandSettlement.__init__` instantiates `X402Handler()` and `get_algorand_client()` — not the old `AlgoClient` directly.

---

### TASK 1.10 — Remove Demo Scaffolding from Application Path

**Step 1 — Gate or delete `api/routes/demo.py`:**

Add a guard at the top of every route in `api/routes/demo.py`:

```python
import os
if os.getenv("ADMIN_DEMO_ENABLED", "false").lower() != "true":
    from fastapi import APIRouter
    router = APIRouter()
    # All demo routes are disabled unless ADMIN_DEMO_ENABLED=true
```

Or, if this is a full SaaS product with no demo endpoints needed, delete `api/routes/demo.py` entirely and remove its import from `api/main.py`.

**Step 2 — Remove auto-seed from `api/main.py` startup:**

Locate the `lifespan` startup function in `api/main.py`. Remove any code that:
- Auto-seeds demo enterprises
- Sets `DEMO_MODE` or `AUTO_ACTIVATE_ENTERPRISES` defaults
- Creates demo user accounts

Replace with a comment:
```python
# Demo seeding removed. Use scripts/seed_demo.py for local dev only.
```

**Step 3 — Move `demo.py` and `demoacf.py` out of the application root:**

```bash
mkdir -p scripts/dev_tools
mv demo.py scripts/dev_tools/demo.py
mv demoacf.py scripts/dev_tools/demoacf.py
```

Add a `README` comment at the top of each:
```python
# DEV TOOL ONLY — not part of the production application
# Run with: python scripts/dev_tools/demo.py
```

**Step 4 — Update `.env` defaults:**

In `.env` (and `.env.example` if it exists), change:
```
DEMO_MODE=false
AUTO_ACTIVATE_ENTERPRISES=false
ADMIN_DEMO_ENABLED=false
```

---

### TASK 1.11 — Update `api/main.py` Health Check

Replace any `A2A Treasury` branding with `Cadencia`. Update the health endpoint to use `get_algorand_client().health_check()`:

```python
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
        },
    }
```

Also update the `.well-known/agent.json` endpoint to use `cadencia` branding. Search for any remaining `A2A Treasury`, `a2a-treasury`, or `ACF` references in API responses and replace with `Cadencia`.

---

### TASK 1.12 — Remove Deprecated Files

After all tasks above are complete and tests pass, delete these files:

```bash
rm blockchain/contracts/treasury_escrow.py    # PyTeal source — replaced by static TEAL
rm blockchain/contracts/deploy.py             # PyTeal compilation script — one-time only, now in scripts/
rm blockchain/contract_client.py              # Replaced by blockchain/escrow_contract.py
rm blockchain/simulation.py                  # Dry-run logic folded into sdk_client.py dryrun()
rm blockchain/algo_client.py                 # Replaced by blockchain/sdk_client.py
```

Remove `pyteal` from `requirements.txt` production dependencies:
```bash
# requirements.txt — remove this line:
pyteal
# Keep py-algorand-sdk>=2.6.0
```

If PyTeal is needed for the one-time compile script, add it to a separate `requirements-dev.txt` only.

---

### TASK 1.13 — Final Verification Checklist

Before marking Phase 1 complete, verify every item in this checklist. Do not proceed to Phase 2 until all items pass.

**Blockchain Layer:**
- [ ] `blockchain/contracts/teal/escrow_approval.teal` exists and is non-empty
- [ ] `blockchain/contracts/teal/escrow_clear.teal` exists and is non-empty
- [ ] `blockchain/sdk_client.py` exists with `AlgorandSDKClient` and `get_algorand_client()` singleton
- [ ] `blockchain/escrow_contract.py` exists with `EscrowContract` class
- [ ] `blockchain/escrow_manager.py` rewritten — no `SIM-` references, no fallback chain, ~200 lines
- [ ] `blockchain/payment_handler.py` uses `get_algorand_client()`
- [ ] All deleted files are gone: `treasury_escrow.py`, `deploy.py`, `contract_client.py`, `simulation.py`, `algo_client.py`

**Core Engine:**
- [ ] `core/x402_handler.py` — `SIM-` tokens only accepted when `X402_SIMULATION_MODE=true`
- [ ] `core/anchor_service.py` — uses `get_algorand_client()`, simulation gated by `ALGORAND_SIMULATION`
- [ ] `framework/settlement/x402_algorand.py` — imports updated

**Application:**
- [ ] `api/main.py` — no demo auto-seed at startup
- [ ] `api/main.py` — health check uses `cadencia` branding
- [ ] `api/routes/demo.py` — gated behind `ADMIN_DEMO_ENABLED=true` or deleted
- [ ] `demo.py` and `demoacf.py` moved to `scripts/dev_tools/`
- [ ] `.env` — `DEMO_MODE=false`, `AUTO_ACTIVATE_ENTERPRISES=false`
- [ ] `pyteal` removed from production `requirements.txt`

**DB:**
- [ ] `escrow_contracts` table has `deploy_txid` column
- [ ] Migration exists for the new column

**Tests:**
- [ ] `tests/test_sdk_client.py` — all pass
- [ ] `tests/test_escrow_contract.py` — all pass
- [ ] `tests/test_escrow_manager_sdk.py` — all pass
- [ ] `tests/test_state_machine.py` — no regressions (escrow trigger is mocked, interface unchanged)
- [ ] `tests/test_x402.py` — updated to test new gated simulation behavior
- [ ] `tests/test_anchor.py` — updated to test new gated simulation behavior
- [ ] Full test suite: `pytest --asyncio-mode=auto` — no failures

**No Regressions:**
- [ ] All 16 existing API routes still respond correctly
- [ ] `agents/neutral_agent.py` requires no import changes (EscrowManager public API is preserved)
- [ ] Frontend (`a2a-treasury-ui`) API contract unchanged — same endpoint paths, same response shapes

---

## What You Must NOT Do

These are hard constraints. Violating any of them breaks the refactor path:

1. **Do NOT add new features.** Phase 1 is cleanup only. No marketplace endpoints, no new agents, no new DB tables except `deploy_txid`.
2. **Do NOT change the public API surface.** All existing endpoint paths, request schemas, and response schemas must remain identical. The frontend must not require changes.
3. **Do NOT change `agents/neutral_agent.py` imports or method calls** — the `EscrowManager` public interface must be preserved exactly.
4. **Do NOT leave any `SIM-` prefix strings in non-simulation code paths.** If a `SIM-` string appears outside an explicit `if self.simulation_mode:` block, it is a bug.
5. **Do NOT call `scripts/compile_contract.py` from application startup.** It is a dev-only utility run once.
6. **Do NOT remove `ALGORAND_SIMULATION` or `X402_SIMULATION_MODE` env vars.** They are valid operational flags for local dev and integration testing — they just must be explicitly set, not defaulted to backdoor paths.
7. **Do NOT delete `tests/test_state_machine.py`** or any existing test file. Add new tests; do not remove existing coverage.

---

## Environment Variables — Final State After Phase 1

After Phase 1, the `.env` file must have these values by default (update `.env.example` accordingly):

```env
# Blockchain
ALGORAND_NETWORK=testnet
ALGORAND_ALGOD_ADDRESS=https://testnet-api.algonode.cloud
ALGORAND_INDEXER_ADDRESS=https://testnet-idx.algonode.cloud
ALGORAND_ALGOD_TOKEN=
ALGORAND_SIMULATION=false         # true = skip on-chain calls (local dev only)
ALGORAND_ESCROW_CREATOR_MNEMONIC= # Required in production

# Payments
X402_SIMULATION_MODE=false        # true = accept SIM- tokens (local dev only)
X402_DEMO_AMOUNT_MICRO=100000

# Anchor
ANCHOR_ENABLED=true
ANCHOR_SIMULATION=false           # alias for ALGORAND_SIMULATION in anchor service

# Demo (all false in production)
DEMO_MODE=false
AUTO_ACTIVATE_ENTERPRISES=false
ADMIN_DEMO_ENABLED=false
```

---

## Commit Structure

Make one commit per completed task. Use this message format:

```
feat(phase1): [TASK X.Y] <short description>

- What was changed
- Why it was changed
- What was removed
```

Example:
```
feat(phase1): [TASK 1.2] Add AlgorandSDKClient singleton

- Created blockchain/sdk_client.py replacing algo_client.py + simulation.py
- Single entry point for all Algorand interactions
- No PyTeal dependency
- Added tests/test_sdk_client.py with full mock coverage
```

Do not bundle multiple tasks into one commit. This makes rollback clean and reviewable.

---

## Definition of Done

Phase 1 is complete when:

1. The entire test suite passes with `pytest --asyncio-mode=auto` and zero failures.
2. A local `docker-compose up` starts the API successfully with `DEMO_MODE=false` and `ALGORAND_SIMULATION=false`.
3. The `/health` endpoint returns `"platform": "cadencia"` and reports Algorand connectivity.
4. No file in the `blockchain/` directory contains a `pyteal` import.
5. No file in the `core/` directory accepts `SIM-` tokens outside an explicit `if self.simulation_mode:` guard.
6. The frontend (`a2a-treasury-ui`) requires zero changes to work with the refactored backend.
7. All 13 tasks in the checklist above are checked off.

When all of the above are confirmed, the backend is clean, production-honest, and fully ready for Phase 2 (Escrow Lifecycle hardening) and the eventual refactor into the full Cadencia B2B SaaS agentic marketplace.
