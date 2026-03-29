"""
blockchain/contracts/deploy.py — Deploy TreasuryEscrow to Algorand TestNet.

Usage:
    python -m blockchain.contracts.deploy

Compiles the Puya contract, deploys to TestNet, opts into USDC ASA,
and saves deployment info to blockchain/contracts/deployment.json.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# ─── Environment ────────────────────────────────────────────────────────────────
ALGORAND_ALGOD_ADDRESS = os.getenv(
    "ALGORAND_ALGOD_ADDRESS", "https://testnet-api.algonode.cloud"
)
ALGORAND_ALGOD_TOKEN = os.getenv("ALGORAND_ALGOD_TOKEN", "")
ALGORAND_NETWORK = os.getenv("ALGORAND_NETWORK", "testnet")
DEPLOYER_MNEMONIC = os.getenv("ALGORAND_ESCROW_CREATOR_MNEMONIC", "")
USDC_ASSET_ID = int(os.getenv("ALGORAND_USDC_ASSET_ID", "10458941"))

CONTRACTS_DIR = Path(__file__).parent
DEPLOYMENT_JSON = CONTRACTS_DIR / "deployment.json"


def compile_contract() -> tuple[bytes, bytes]:
    """
    Compile the TreasuryEscrow Puya contract.
    Returns (approval_program_bytes, clear_state_program_bytes).
    """
    contract_path = CONTRACTS_DIR / "treasury_escrow.py"
    if not contract_path.exists():
        raise FileNotFoundError(f"Contract source not found: {contract_path}")

    print(f"📝 Compiling {contract_path.name} with Puya compiler...")

    # Try AlgoKit compile first
    try:
        result = subprocess.run(
            ["algokit", "compile", "py", str(contract_path)],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode == 0:
            print("✅ Compilation successful via algokit compile")
            # Read compiled TEAL files from output directory
            output_dir = CONTRACTS_DIR / "artifacts" / "TreasuryEscrow"
            approval_teal = output_dir / "approval.teal"
            clear_teal = output_dir / "clear.teal"
            if approval_teal.exists() and clear_teal.exists():
                return approval_teal.read_bytes(), clear_teal.read_bytes()
        else:
            print(f"⚠️  algokit compile returned code {result.returncode}")
            if result.stderr:
                print(f"   stderr: {result.stderr[:500]}")
    except FileNotFoundError:
        print("⚠️  algokit CLI not found, trying puyapy directly...")
    except subprocess.TimeoutExpired:
        print("⚠️  Compilation timed out")

    # Fallback: try puyapy directly
    try:
        result = subprocess.run(
            ["puyapy", str(contract_path)],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode == 0:
            print("✅ Compilation successful via puyapy")
            output_dir = CONTRACTS_DIR / "out"
            for teal_dir in [
                output_dir,
                CONTRACTS_DIR / "artifacts" / "TreasuryEscrow",
                CONTRACTS_DIR,
            ]:
                approval = teal_dir / "TreasuryEscrow.approval.teal"
                clear = teal_dir / "TreasuryEscrow.clear.teal"
                if approval.exists() and clear.exists():
                    return approval.read_bytes(), clear.read_bytes()
        print(f"⚠️  puyapy error: {result.stderr[:500] if result.stderr else 'unknown'}")
    except FileNotFoundError:
        print("⚠️  puyapy not found")
    except subprocess.TimeoutExpired:
        print("⚠️  puyapy compilation timed out")

    raise RuntimeError(
        "Failed to compile contract. Ensure 'algokit' or 'puyapy' is installed:\n"
        "  pip install algokit-utils algorand-python\n"
        "  OR\n"
        "  pipx install algokit"
    )


def deploy() -> dict:
    """
    Full deployment flow:
    1. Compile the contract
    2. Deploy to Algorand TestNet
    3. Opt contract into USDC ASA
    4. Save deployment info to deployment.json
    """
    from algosdk import account, mnemonic
    from algosdk.transaction import (
        ApplicationCreateTxn,
        OnComplete,
        StateSchema,
        wait_for_confirmation,
    )
    from algosdk.v2client import algod

    if not DEPLOYER_MNEMONIC:
        raise ValueError(
            "ALGORAND_ESCROW_CREATOR_MNEMONIC not set. "
            "Export it in your environment or .env file."
        )

    # ─── Setup client + deployer account ────────────────────────────────────
    client = algod.AlgodClient(
        algod_token=ALGORAND_ALGOD_TOKEN or "",
        algod_address=ALGORAND_ALGOD_ADDRESS,
    )
    deployer_private_key = mnemonic.to_private_key(DEPLOYER_MNEMONIC)
    deployer_address = account.address_from_private_key(deployer_private_key)

    print(f"🔑 Deployer address: {deployer_address}")
    print(f"🌐 Network: {ALGORAND_NETWORK}")

    # ─── Compile ────────────────────────────────────────────────────────────
    approval_bytes, clear_bytes = compile_contract()

    # Compile TEAL to bytecode
    approval_compiled = client.compile(approval_bytes.decode("utf-8"))
    approval_program = _decode_compiled(approval_compiled["result"])

    clear_compiled = client.compile(clear_bytes.decode("utf-8"))
    clear_program = _decode_compiled(clear_compiled["result"])

    # ─── Deploy application ─────────────────────────────────────────────────
    sp = client.suggested_params()

    # Global state: 9 keys (3 bytes + 6 uint64 = need ints: 6, bytes: 3)
    # Actually: buyer_address(bytes), seller_address(bytes), platform_address(bytes),
    #           session_id(bytes), merkle_root(bytes) = 5 bytes
    #           agreed_amount_usdc(uint), status(uint), fx_rate_locked(uint),
    #           funded_at_round(uint) = 4 uints
    global_schema = StateSchema(num_uints=4, num_byte_slices=5)
    local_schema = StateSchema(num_uints=0, num_byte_slices=0)

    txn = ApplicationCreateTxn(
        sender=deployer_address,
        sp=sp,
        on_complete=OnComplete.NoOpOC,
        approval_program=approval_program,
        clear_program=clear_program,
        global_schema=global_schema,
        local_schema=local_schema,
    )

    signed_txn = txn.sign(deployer_private_key)
    tx_id = client.send_transaction(signed_txn)
    print(f"📤 Deploy transaction sent: {tx_id}")

    # Wait for confirmation
    result = wait_for_confirmation(client, tx_id, 10)
    app_id = result["application-index"]
    app_address = _get_application_address(app_id)

    print(f"✅ Contract deployed!")
    print(f"   App ID:      {app_id}")
    print(f"   App Address: {app_address}")

    # ─── Opt contract into USDC ASA ─────────────────────────────────────────
    print(f"💰 Opting contract into USDC ASA (ID: {USDC_ASSET_ID})...")

    # Fund the contract with min balance for ASA opt-in (0.2 ALGO)
    from algosdk.transaction import PaymentTxn

    sp = client.suggested_params()
    fund_txn = PaymentTxn(
        sender=deployer_address,
        sp=sp,
        receiver=app_address,
        amt=200_000,  # 0.2 ALGO for MBR
    )
    signed_fund = fund_txn.sign(deployer_private_key)
    fund_tx_id = client.send_transaction(signed_fund)
    wait_for_confirmation(client, fund_tx_id, 10)
    print(f"   Funded contract with 0.2 ALGO for MBR: {fund_tx_id}")

    # Call opt_in_to_usdc ABI method
    from algosdk.transaction import ApplicationCallTxn
    from algosdk.abi import Method

    opt_in_method = Method.from_signature("opt_in_to_usdc()void")
    from algosdk.atomic_transaction_composer import (
        AtomicTransactionComposer,
        AccountTransactionSigner,
    )

    atc = AtomicTransactionComposer()
    signer = AccountTransactionSigner(deployer_private_key)
    sp = client.suggested_params()
    sp.flat_fee = True
    sp.fee = 2000  # cover inner txn fee

    atc.add_method_call(
        app_id=app_id,
        method=opt_in_method,
        sender=deployer_address,
        sp=sp,
        signer=signer,
    )
    atc_result = atc.execute(client, 10)
    print(f"   USDC opt-in tx: {atc_result.tx_ids[0]}")
    print(f"✅ Contract opted into USDC ASA")

    # ─── Save deployment info ───────────────────────────────────────────────
    deployment_info = {
        "app_id": app_id,
        "app_address": app_address,
        "network": ALGORAND_NETWORK,
        "usdc_asset_id": USDC_ASSET_ID,
        "deployer_address": deployer_address,
        "deploy_tx_id": tx_id,
        "opt_in_tx_id": atc_result.tx_ids[0],
        "deployed_at": datetime.now(timezone.utc).isoformat(),
    }

    DEPLOYMENT_JSON.write_text(json.dumps(deployment_info, indent=2))
    print(f"\n📄 Deployment info saved to: {DEPLOYMENT_JSON}")
    print(json.dumps(deployment_info, indent=2))

    return deployment_info


def _decode_compiled(compiled_b64: str) -> bytes:
    """Decode base64-encoded compiled TEAL bytecode."""
    import base64

    return base64.b64decode(compiled_b64)


def _get_application_address(app_id: int) -> str:
    """Derive the Algorand application account address from app_id."""
    from algosdk.logic import get_application_address

    return get_application_address(app_id)


if __name__ == "__main__":
    try:
        info = deploy()
        print(f"\n🎉 Deployment complete! App ID: {info['app_id']}")
    except Exception as e:
        print(f"\n❌ Deployment failed: {e}")
        sys.exit(1)
