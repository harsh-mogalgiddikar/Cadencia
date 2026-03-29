"""
tests/test_valuation.py — Tests for Layer 1 Valuation Engine.

Uses the PRD reference scenario:
  Mumbai Imports Ltd (Buyer): intrinsic=92000, risk=0.12, margin=0.08, ceiling=96000
  Ravi Exports Pvt Ltd (Seller): intrinsic=87000, risk=0.06, margin=0.05
"""
from __future__ import annotations

import pytest

from core.valuation import (
    build_valuation_snapshot,
    compute_opening_anchor,
    compute_reservation_price,
    compute_target_price,
    compute_utility_for_offer,
    compute_utility_score,
)


# ─── Buyer config (PRD reference) ──────────────────────────────────────────
BUYER_INTRINSIC = 92000.0
BUYER_RISK = 0.12
BUYER_MARGIN = 0.08
BUYER_CURVE = {"1": 0.06, "2": 0.04, "3": 0.025, "4": 0.015, "5": 0.008}

# ─── Seller config (PRD reference) ─────────────────────────────────────────
SELLER_INTRINSIC = 87000.0
SELLER_RISK = 0.06
SELLER_MARGIN = 0.05
SELLER_CURVE = {"1": 0.05, "2": 0.035, "3": 0.02, "4": 0.01, "5": 0.005}


class TestReservationPrice:
    def test_buyer_reservation_price(self):
        result = compute_reservation_price(BUYER_INTRINSIC, BUYER_RISK, "buyer")
        assert result == pytest.approx(103040.0)

    def test_seller_reservation_price(self):
        result = compute_reservation_price(SELLER_INTRINSIC, SELLER_RISK, "seller")
        assert result == pytest.approx(81780.0)

    def test_invalid_role_raises(self):
        with pytest.raises(ValueError, match="Invalid agent_role"):
            compute_reservation_price(100, 0.1, "invalid")


class TestTargetPrice:
    def test_buyer_target_price(self):
        result = compute_target_price(BUYER_INTRINSIC, BUYER_MARGIN, "buyer")
        assert result == pytest.approx(84640.0)

    def test_seller_target_price(self):
        result = compute_target_price(SELLER_INTRINSIC, SELLER_MARGIN, "seller")
        assert result == pytest.approx(91350.0)


class TestUtilityScore:
    def test_buyer_utility_at_target(self):
        reservation = compute_reservation_price(BUYER_INTRINSIC, BUYER_RISK, "buyer")
        target = compute_target_price(BUYER_INTRINSIC, BUYER_MARGIN, "buyer")
        result = compute_utility_score(target, reservation, target, "buyer")
        assert result == pytest.approx(1.0)

    def test_buyer_utility_at_reservation(self):
        reservation = compute_reservation_price(BUYER_INTRINSIC, BUYER_RISK, "buyer")
        target = compute_target_price(BUYER_INTRINSIC, BUYER_MARGIN, "buyer")
        result = compute_utility_score(reservation, reservation, target, "buyer")
        assert result == pytest.approx(0.0)

    def test_seller_utility_at_target(self):
        reservation = compute_reservation_price(SELLER_INTRINSIC, SELLER_RISK, "seller")
        target = compute_target_price(SELLER_INTRINSIC, SELLER_MARGIN, "seller")
        result = compute_utility_score(target, reservation, target, "seller")
        assert result == pytest.approx(1.0)

    def test_seller_utility_at_reservation(self):
        reservation = compute_reservation_price(SELLER_INTRINSIC, SELLER_RISK, "seller")
        target = compute_target_price(SELLER_INTRINSIC, SELLER_MARGIN, "seller")
        result = compute_utility_score(reservation, reservation, target, "seller")
        assert result == pytest.approx(0.0)

    def test_utility_clamped_to_zero(self):
        # Buyer offer above reservation → utility < 0, should clamp to 0
        result = compute_utility_score(110000.0, 103040.0, 84640.0, "buyer")
        assert result == 0.0

    def test_utility_clamped_to_one(self):
        # Buyer offer way below target → utility > 1, should clamp to 1
        result = compute_utility_score(50000.0, 103040.0, 84640.0, "buyer")
        assert result == 1.0


class TestOpeningAnchor:
    def test_buyer_anchor_below_target(self):
        target = compute_target_price(BUYER_INTRINSIC, BUYER_MARGIN, "buyer")
        anchor = compute_opening_anchor(target, BUYER_CURVE, "buyer")
        # anchor should be below target for buyer
        assert anchor < target

    def test_seller_anchor_above_target(self):
        target = compute_target_price(SELLER_INTRINSIC, SELLER_MARGIN, "seller")
        anchor = compute_opening_anchor(target, SELLER_CURVE, "seller")
        # anchor should be above target for seller
        assert anchor > target

    def test_seller_anchor_value(self):
        target = compute_target_price(SELLER_INTRINSIC, SELLER_MARGIN, "seller")
        anchor = compute_opening_anchor(target, SELLER_CURVE, "seller")
        # seller: anchor = target * (1 + 0.05) = 91350 * 1.05 ≈ 95917.5
        assert anchor == pytest.approx(91350.0 * 1.05, rel=0.001)


class TestValuationSnapshot:
    def test_buyer_snapshot(self):
        config = {
            "intrinsic_value": BUYER_INTRINSIC,
            "risk_factor": BUYER_RISK,
            "negotiation_margin": BUYER_MARGIN,
            "concession_curve": BUYER_CURVE,
            "budget_ceiling": 96000.0,
            "max_exposure": 100000.0,
            "agent_role": "buyer",
        }
        snapshot = build_valuation_snapshot(config)
        assert snapshot["reservation_price"] == pytest.approx(103040.0)
        assert snapshot["target_price"] == pytest.approx(84640.0)
        assert snapshot["utility_score_at_reservation"] == 0.0
        assert snapshot["utility_score_at_target"] == 1.0
        assert snapshot["budget_ceiling"] == pytest.approx(96000.0)
        assert snapshot["agent_role"] == "buyer"
        assert "computed_at" in snapshot

    def test_seller_snapshot(self):
        config = {
            "intrinsic_value": SELLER_INTRINSIC,
            "risk_factor": SELLER_RISK,
            "negotiation_margin": SELLER_MARGIN,
            "concession_curve": SELLER_CURVE,
            "budget_ceiling": None,
            "max_exposure": 100000.0,
            "agent_role": "seller",
        }
        snapshot = build_valuation_snapshot(config)
        assert snapshot["reservation_price"] == pytest.approx(81780.0)
        assert snapshot["target_price"] == pytest.approx(91350.0)
        assert snapshot["budget_ceiling"] is None


class TestUtilityForOffer:
    def test_convenience_function(self):
        config = {
            "intrinsic_value": BUYER_INTRINSIC,
            "risk_factor": BUYER_RISK,
            "negotiation_margin": BUYER_MARGIN,
            "concession_curve": BUYER_CURVE,
            "budget_ceiling": 96000.0,
            "max_exposure": 100000.0,
            "agent_role": "buyer",
        }
        snapshot = build_valuation_snapshot(config)
        # Offer at target → utility = 1.0
        utility = compute_utility_for_offer(84640.0, snapshot)
        assert utility == pytest.approx(1.0)
