"""
blockchain/contracts/treasury_escrow.py — TreasuryEscrow Algorand Smart Contract

Algorand Python (Puya compiler) smart contract for trustless escrow.
Replaces the previous multisig-based approach with on-chain enforcement
of fund / release / refund / dispute logic.

Compile with: algokit compile py treasury_escrow.py
"""

from algopy import (
    ARC4Contract,
    Account,
    Asset,
    Bytes,
    Global,
    GlobalState,
    Txn,
    UInt64,
    arc4,
    gtxn,
    itxn,
    log,
    op,
    subroutine,
)


# ─── Status constants ──────────────────────────────────────────────────────────
STATUS_PENDING = UInt64(0)
STATUS_FUNDED = UInt64(1)
STATUS_RELEASED = UInt64(2)
STATUS_REFUNDED = UInt64(3)
STATUS_DISPUTED = UInt64(4)

# USDC TestNet Asset ID
USDC_ASSET_ID = UInt64(10458941)


class TreasuryEscrow(ARC4Contract):
    """
    Trustless on-chain escrow for A2A Treasury Network.

    Lifecycle: PENDING → FUNDED → RELEASED / REFUNDED / DISPUTED
    All USDC transfers are enforced via inner transactions.
    """

    # ─── Global State ───────────────────────────────────────────────────────
    buyer_address: GlobalState[Bytes]
    seller_address: GlobalState[Bytes]
    platform_address: GlobalState[Bytes]
    session_id: GlobalState[Bytes]
    agreed_amount_usdc: GlobalState[UInt64]
    status: GlobalState[UInt64]
    fx_rate_locked: GlobalState[UInt64]
    funded_at_round: GlobalState[UInt64]
    merkle_root: GlobalState[Bytes]

    # ─── Constructor (bare create) ──────────────────────────────────────────
    @arc4.baremethod(create="require")
    def create(self) -> None:
        """Bare create — initialises state with defaults. Actual params set via init()."""
        self.buyer_address = GlobalState(Bytes(b""))
        self.seller_address = GlobalState(Bytes(b""))
        self.platform_address = GlobalState(Bytes(b""))
        self.session_id = GlobalState(Bytes(b""))
        self.agreed_amount_usdc = GlobalState(UInt64(0))
        self.status = GlobalState(STATUS_PENDING)
        self.fx_rate_locked = GlobalState(UInt64(0))
        self.funded_at_round = GlobalState(UInt64(0))
        self.merkle_root = GlobalState(Bytes(b""))

    # ─── Initialise (called once after create + opt-in) ─────────────────────
    @arc4.abimethod
    def init(
        self,
        buyer: arc4.Address,
        seller: arc4.Address,
        platform: arc4.Address,
        session_id: arc4.DynamicBytes,
        agreed_amount_usdc: arc4.UInt64,
        fx_rate_locked: arc4.UInt64,
    ) -> None:
        """
        Initialise escrow parameters. Only callable by the creator (platform).
        Must be called exactly once after contract creation.
        """
        assert Txn.sender == Global.creator_address, "only creator can init"
        assert self.status.value == STATUS_PENDING, "already initialised / funded"

        self.buyer_address.value = buyer.bytes
        self.seller_address.value = seller.bytes
        self.platform_address.value = platform.bytes
        self.session_id.value = session_id.bytes
        self.agreed_amount_usdc.value = agreed_amount_usdc.native
        self.fx_rate_locked.value = fx_rate_locked.native

    # ─── Opt-in to USDC ASA ────────────────────────────────────────────────
    @arc4.abimethod
    def opt_in_to_usdc(self) -> None:
        """
        Opt the contract account into USDC ASA.
        Only callable by the creator (platform).
        """
        assert Txn.sender == Global.creator_address, "only creator can opt-in"

        itxn.AssetTransfer(
            xfer_asset=Asset(USDC_ASSET_ID),
            asset_receiver=Global.current_application_address,
            asset_amount=0,
            fee=0,
        ).submit()

    # ─── ABI Method: fund ───────────────────────────────────────────────────
    @arc4.abimethod
    def fund(
        self,
        payment: gtxn.AssetTransferTransaction,
        session_id: arc4.DynamicBytes,
    ) -> None:
        """
        Fund the escrow with USDC.

        - Only callable by buyer_address
        - Verifies payment amount == agreed_amount_usdc
        - Verifies receiver is the contract account
        - Sets status = FUNDED, records funded_at_round
        - Emits ARC-28 event: Funded(session_id, amount, buyer)
        """
        self._assert_is_buyer()
        assert self.status.value == STATUS_PENDING, "escrow not in PENDING state"

        # Verify the attached asset transfer
        assert payment.asset_receiver == Global.current_application_address, \
            "payment must be to contract"
        assert payment.xfer_asset == Asset(USDC_ASSET_ID), \
            "payment must be USDC"
        assert payment.asset_amount == self.agreed_amount_usdc.value, \
            "payment amount mismatch"

        # Update state
        self.status.value = STATUS_FUNDED
        self.funded_at_round.value = Global.round

        # ARC-28 event: Funded(session_id, amount, buyer)
        log(
            b"Funded",
            self.session_id.value,
            op.itob(self.agreed_amount_usdc.value),
            Txn.sender.bytes,
        )

    # ─── ABI Method: release ────────────────────────────────────────────────
    @arc4.abimethod
    def release(self, merkle_root: arc4.DynamicBytes) -> None:
        """
        Release escrowed USDC to the seller.

        - Only callable by platform_address OR buyer_address
        - Requires status == FUNDED
        - Inner txn sends USDC to seller
        - Sets status = RELEASED, stores merkle_root
        - Emits ARC-28 event: Released(session_id, amount, seller, merkle_root)
        """
        self._assert_is_funded()
        assert (
            Txn.sender.bytes == self.platform_address.value
            or Txn.sender.bytes == self.buyer_address.value
        ), "only platform or buyer can release"

        # Inner transaction: send USDC to seller
        itxn.AssetTransfer(
            xfer_asset=Asset(USDC_ASSET_ID),
            asset_receiver=Account(self.seller_address.value),
            asset_amount=self.agreed_amount_usdc.value,
            fee=0,
        ).submit()

        # Update state
        self.status.value = STATUS_RELEASED
        self.merkle_root.value = merkle_root.bytes

        # ARC-28 event: Released(session_id, amount, seller, merkle_root)
        log(
            b"Released",
            self.session_id.value,
            op.itob(self.agreed_amount_usdc.value),
            self.seller_address.value,
            merkle_root.bytes,
        )

    # ─── ABI Method: refund ─────────────────────────────────────────────────
    @arc4.abimethod
    def refund(self, reason: arc4.DynamicBytes) -> None:
        """
        Refund escrowed USDC back to the buyer.

        - Only callable by platform_address
        - Requires status == FUNDED
        - Inner txn returns USDC to buyer
        - Sets status = REFUNDED
        - Emits ARC-28 event: Refunded(session_id, amount, buyer, reason)
        """
        self._assert_is_funded()
        self._assert_is_platform()

        # Inner transaction: return USDC to buyer
        itxn.AssetTransfer(
            xfer_asset=Asset(USDC_ASSET_ID),
            asset_receiver=Account(self.buyer_address.value),
            asset_amount=self.agreed_amount_usdc.value,
            fee=0,
        ).submit()

        # Update state
        self.status.value = STATUS_REFUNDED

        # ARC-28 event: Refunded(session_id, amount, buyer, reason)
        log(
            b"Refunded",
            self.session_id.value,
            op.itob(self.agreed_amount_usdc.value),
            self.buyer_address.value,
            reason.bytes,
        )

    # ─── ABI Method: dispute ────────────────────────────────────────────────
    @arc4.abimethod
    def dispute(self) -> None:
        """
        Flag escrow as DISPUTED for manual platform review.

        - Callable by buyer OR seller
        - Requires status == FUNDED
        - Sets status = DISPUTED
        - Emits ARC-28 event: Disputed(session_id, caller)
        """
        self._assert_is_funded()
        assert (
            Txn.sender.bytes == self.buyer_address.value
            or Txn.sender.bytes == self.seller_address.value
        ), "only buyer or seller can dispute"

        self.status.value = STATUS_DISPUTED

        # ARC-28 event: Disputed(session_id, caller)
        log(
            b"Disputed",
            self.session_id.value,
            Txn.sender.bytes,
        )

    # ─── ABI Method: get_status (read-only) ─────────────────────────────────
    @arc4.abimethod(readonly=True)
    def get_status(self) -> arc4.UInt64:
        """Read-only: return current escrow status as uint64."""
        return arc4.UInt64(self.status.value)

    # ─── ABI Method: get_details (read-only) ────────────────────────────────
    @arc4.abimethod(readonly=True)
    def get_details(
        self,
    ) -> arc4.Tuple[arc4.DynamicBytes, arc4.DynamicBytes, arc4.UInt64, arc4.UInt64]:
        """
        Read-only: return (session_id, merkle_root, agreed_amount_usdc, status).
        """
        return arc4.Tuple(
            (
                arc4.DynamicBytes(self.session_id.value),
                arc4.DynamicBytes(self.merkle_root.value),
                arc4.UInt64(self.agreed_amount_usdc.value),
                arc4.UInt64(self.status.value),
            )
        )

    # ─── Access Control Subroutines ────────────────────────────────────────
    @subroutine
    def _assert_is_buyer(self) -> None:
        """Assert that the transaction sender is the registered buyer."""
        assert Txn.sender.bytes == self.buyer_address.value, "caller is not buyer"

    @subroutine
    def _assert_is_seller(self) -> None:
        """Assert that the transaction sender is the registered seller."""
        assert Txn.sender.bytes == self.seller_address.value, "caller is not seller"

    @subroutine
    def _assert_is_platform(self) -> None:
        """Assert that the transaction sender is the platform address."""
        assert Txn.sender.bytes == self.platform_address.value, "caller is not platform"

    @subroutine
    def _assert_is_funded(self) -> None:
        """Assert that the escrow is currently in FUNDED state."""
        assert self.status.value == STATUS_FUNDED, "escrow is not funded"
