"""
Rule Engine — Pure Function implementation.

This module contains ZERO I/O, ZERO DB calls, ZERO side effects.
All inputs are plain Python values; the function returns a plain dataclass.
This makes the entire rule engine fully unit-testable without any fixtures.

evaluate_rule(rule_json, competitor_prices, cost, min_margin) → RuleResult

Evaluation order (mandated by AGENTS.md)
-----------------------------------------
  Step 1  Determine reference price from competitor_prices list
          according to rule scope (ALL_MAPPED → use minimum; PRIMARY_ONLY → use first)
  Step 2  Compute raw_price from the rule strategy (type + adjustment)
  Step 3  Compute defensive_floor = cost + effective_min_margin_amount
  Step 4  Apply floor: recommended_price = max(raw_price, defensive_floor)
  Step 5  Apply ceiling (if set): recommended_price = min(recommended_price, ceiling)

Rule `condition` JSONB schema (canonical)
-----------------------------------------
{
    "type": "BEAT_LOWEST",          // BEAT_LOWEST | MATCH_LOWEST | FIXED_PRICE | PERCENTAGE_MARKUP
    "adjustment": {
        "mode": "FIXED",            // FIXED | PERCENTAGE
        "value": -10                // negative = undercut
    },
    "constraints": {
        "min_margin_amount": 500,   // per-rule override; falls back to product-level value
        "min_margin_rate": null,    // 0.0–1.0 ratio; used if min_margin_amount is null
        "price_ceiling": null       // absolute upper bound
    },
    "scope": {
        "competitor_filter": "ALL_MAPPED"   // ALL_MAPPED | PRIMARY_ONLY
    }
}

Sample conditions (JSONB examples for documentation / tests)
--------------------------------------------------------------
See SAMPLES dict at the bottom of this module.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum
from typing import Any


# ── Public types ──────────────────────────────────────────────────────────────

class RuleType(StrEnum):
    BEAT_LOWEST        = "BEAT_LOWEST"
    MATCH_LOWEST       = "MATCH_LOWEST"
    FIXED_PRICE        = "FIXED_PRICE"
    PERCENTAGE_MARKUP  = "PERCENTAGE_MARKUP"


class AdjustmentMode(StrEnum):
    FIXED      = "FIXED"
    PERCENTAGE = "PERCENTAGE"


class CompetitorFilter(StrEnum):
    ALL_MAPPED    = "ALL_MAPPED"
    PRIMARY_ONLY  = "PRIMARY_ONLY"


@dataclass(frozen=True)
class RuleResult:
    """
    Output of evaluate_rule().  All prices are integer yen (¥).

    Attributes
    ----------
    recommended_price   Final price to recommend (after floor + ceiling).
    raw_price           Price before floor / ceiling constraints.
    defensive_floor     cost + effective_min_margin_amount.
    floor_applied       True when raw_price was raised to defensive_floor.
    ceiling_applied     True when price was capped at price_ceiling.
    reference_price     The competitor price used as the basis for calculation.
    explanation         Human-readable trace string for audit log `details`.
    """

    recommended_price: int
    raw_price: int
    defensive_floor: int
    floor_applied: bool
    ceiling_applied: bool
    reference_price: int | None
    explanation: str


@dataclass
class _ParsedCondition:
    """Internal parsed representation of a JSONB condition dict."""

    rule_type:           RuleType
    adj_mode:            AdjustmentMode | None
    adj_value:           Decimal | None
    min_margin_amount:   Decimal | None   # per-rule override
    min_margin_rate:     Decimal | None   # per-rule override
    price_ceiling:       int | None
    competitor_filter:   CompetitorFilter
    fixed_price:         int | None       # only for FIXED_PRICE type


# ── Internal helpers ──────────────────────────────────────────────────────────

def _to_decimal(v: Any) -> Decimal | None:
    if v is None:
        return None
    return Decimal(str(v))


def _parse(condition: dict[str, Any]) -> _ParsedCondition:
    """
    Parse and validate a raw JSONB condition dict.
    Raises ValueError with a descriptive message on schema violations.
    """
    rule_type_raw = condition.get("type")
    if rule_type_raw not in RuleType.__members__:
        valid = list(RuleType.__members__.keys())
        raise ValueError(f"Unknown rule type {rule_type_raw!r}. Valid: {valid}")
    rule_type = RuleType(rule_type_raw)

    adj = condition.get("adjustment") or {}
    adj_mode_raw = adj.get("mode")
    adj_mode = AdjustmentMode(adj_mode_raw) if adj_mode_raw else None
    adj_value = _to_decimal(adj.get("value"))

    constraints = condition.get("constraints") or {}
    min_margin_amount = _to_decimal(constraints.get("min_margin_amount"))
    min_margin_rate   = _to_decimal(constraints.get("min_margin_rate"))

    ceiling_raw = constraints.get("price_ceiling")
    price_ceiling = int(ceiling_raw) if ceiling_raw is not None else None

    scope = condition.get("scope") or {}
    filter_raw = scope.get("competitor_filter", CompetitorFilter.ALL_MAPPED)
    competitor_filter = CompetitorFilter(filter_raw)

    # FIXED_PRICE stores its price inside adjustment.value
    fixed_price = int(adj_value) if rule_type == RuleType.FIXED_PRICE and adj_value is not None else None

    return _ParsedCondition(
        rule_type=rule_type,
        adj_mode=adj_mode,
        adj_value=adj_value,
        min_margin_amount=min_margin_amount,
        min_margin_rate=min_margin_rate,
        price_ceiling=price_ceiling,
        competitor_filter=competitor_filter,
        fixed_price=fixed_price,
    )


def _select_reference_price(
    competitor_prices: list[int],
    competitor_filter: CompetitorFilter,
) -> int | None:
    """
    Select the single reference price from the competitor prices list.

    ALL_MAPPED   → minimum price among all mapped competitors
    PRIMARY_ONLY → first element (caller must pass primary competitor first)
    """
    if not competitor_prices:
        return None
    if competitor_filter == CompetitorFilter.ALL_MAPPED:
        return min(competitor_prices)
    # PRIMARY_ONLY
    return competitor_prices[0]


def _compute_raw_price(
    parsed: _ParsedCondition,
    reference_price: int | None,
    cost: Decimal,
) -> int:
    """
    Compute the raw (pre-constraint) recommended price from the rule strategy.
    """
    if parsed.rule_type == RuleType.FIXED_PRICE:
        if parsed.fixed_price is None:
            raise ValueError("FIXED_PRICE rule must specify adjustment.value")
        return parsed.fixed_price

    if parsed.rule_type == RuleType.PERCENTAGE_MARKUP:
        if parsed.adj_value is None:
            raise ValueError("PERCENTAGE_MARKUP rule must specify adjustment.value")
        rate = parsed.adj_value  # e.g. 0.20 = 20% markup
        raw = cost * (Decimal("1") + rate)
        return int(raw.to_integral_value(rounding=ROUND_HALF_UP))

    # BEAT_LOWEST and MATCH_LOWEST both need a reference_price
    if reference_price is None:
        raise ValueError(
            f"Rule type {parsed.rule_type} requires at least one competitor price"
        )

    if parsed.rule_type == RuleType.MATCH_LOWEST:
        return reference_price

    # BEAT_LOWEST — apply adjustment
    if parsed.adj_mode == AdjustmentMode.FIXED:
        adj = int(parsed.adj_value or 0)
        return reference_price + adj  # adj is typically negative (undercut)

    if parsed.adj_mode == AdjustmentMode.PERCENTAGE:
        rate = parsed.adj_value or Decimal("0")
        delta = reference_price * rate
        raw = Decimal(reference_price) + delta
        return int(raw.to_integral_value(rounding=ROUND_HALF_UP))

    raise ValueError(
        f"BEAT_LOWEST rule requires adjustment.mode; got {parsed.adj_mode!r}"
    )


def _compute_effective_floor(
    parsed: _ParsedCondition,
    cost: Decimal,
    product_min_margin_amount: Decimal,
    product_min_margin_rate: Decimal | None,
) -> int:
    """
    Determine the defensive price floor.

    Priority:
      1. Per-rule min_margin_amount override
      2. Per-rule min_margin_rate override  (cost × rate)
      3. Product-level min_margin_amount (passed by caller)
      4. Product-level min_margin_rate (passed by caller)
    """
    # Per-rule overrides take precedence
    if parsed.min_margin_amount is not None:
        floor = cost + parsed.min_margin_amount
        return int(floor.to_integral_value(rounding=ROUND_HALF_UP))

    if parsed.min_margin_rate is not None:
        floor = cost * (Decimal("1") + parsed.min_margin_rate)
        return int(floor.to_integral_value(rounding=ROUND_HALF_UP))

    # Fall back to product-level values
    if product_min_margin_rate is not None:
        floor = cost * (Decimal("1") + product_min_margin_rate)
        return int(floor.to_integral_value(rounding=ROUND_HALF_UP))

    floor = cost + product_min_margin_amount
    return int(floor.to_integral_value(rounding=ROUND_HALF_UP))


# ── Public API ────────────────────────────────────────────────────────────────

def evaluate_rule(
    rule_condition: dict[str, Any],
    competitor_prices: list[int],
    cost: Decimal | int | float,
    min_margin_amount: Decimal | int | float,
    min_margin_rate: Decimal | int | float | None = None,
) -> RuleResult:
    """
    Evaluate a pricing rule and return a RuleResult.

    This is a PURE FUNCTION — no I/O, no DB calls, no side effects.
    Safe to call from simulation endpoints, unit tests, and workers alike.

    Parameters
    ----------
    rule_condition      : The `condition` JSONB dict from a PricingRule row.
    competitor_prices   : List of current competitor prices in ¥ (integer).
                          For PRIMARY_ONLY scope, put the primary competitor first.
    cost                : Product cost in ¥ (Decimal recommended).
    min_margin_amount   : Product-level minimum margin in ¥.
    min_margin_rate     : Product-level minimum margin as a ratio (optional).

    Returns
    -------
    RuleResult dataclass (frozen) — see class docstring.

    Raises
    ------
    ValueError  If condition schema is invalid or required prices are missing.
    """
    cost_d = Decimal(str(cost))
    margin_d = Decimal(str(min_margin_amount))
    rate_d = Decimal(str(min_margin_rate)) if min_margin_rate is not None else None

    parsed = _parse(rule_condition)
    reference_price = _select_reference_price(competitor_prices, parsed.competitor_filter)
    raw_price = _compute_raw_price(parsed, reference_price, cost_d)
    defensive_floor = _compute_effective_floor(parsed, cost_d, margin_d, rate_d)

    # ── Apply floor ────────────────────────────────────────────────────────────
    floor_applied = raw_price < defensive_floor
    price_after_floor = max(raw_price, defensive_floor)

    # ── Apply ceiling ──────────────────────────────────────────────────────────
    ceiling_applied = False
    if parsed.price_ceiling is not None and price_after_floor > parsed.price_ceiling:
        recommended = parsed.price_ceiling
        ceiling_applied = True
    else:
        recommended = price_after_floor

    # ── Build explanation (stored in audit_logs.details) ──────────────────────
    parts = [
        f"rule_type={parsed.rule_type}",
        f"reference_price={reference_price}",
        f"raw_price={raw_price}",
        f"defensive_floor={defensive_floor}",
        f"floor_applied={floor_applied}",
        f"ceiling_applied={ceiling_applied}",
        f"recommended_price={recommended}",
    ]
    explanation = " | ".join(parts)

    return RuleResult(
        recommended_price=recommended,
        raw_price=raw_price,
        defensive_floor=defensive_floor,
        floor_applied=floor_applied,
        ceiling_applied=ceiling_applied,
        reference_price=reference_price,
        explanation=explanation,
    )


# ── Sample JSONB conditions (for docs, tests, and simulation UI) ───────────────

SAMPLES: dict[str, dict[str, Any]] = {
    # ── Sample 1: 最安値より10円安く。ただし最低マージン500円を確保 ────────────
    "beat_lowest_fixed_10yen": {
        "type": "BEAT_LOWEST",
        "adjustment": {"mode": "FIXED", "value": -10},
        "constraints": {"min_margin_amount": 500, "min_margin_rate": None, "price_ceiling": None},
        "scope": {"competitor_filter": "ALL_MAPPED"},
    },

    # ── Sample 2: 最安値に一致させる（価格追随）────────────────────────────────
    "match_lowest": {
        "type": "MATCH_LOWEST",
        "adjustment": {},
        "constraints": {"min_margin_amount": None, "min_margin_rate": None, "price_ceiling": None},
        "scope": {"competitor_filter": "ALL_MAPPED"},
    },

    # ── Sample 3: 最安値より2%安く、上限9,800円 ──────────────────────────────
    "beat_lowest_pct_with_ceiling": {
        "type": "BEAT_LOWEST",
        "adjustment": {"mode": "PERCENTAGE", "value": -0.02},
        "constraints": {"min_margin_amount": 300, "min_margin_rate": None, "price_ceiling": 9800},
        "scope": {"competitor_filter": "ALL_MAPPED"},
    },

    # ── Sample 4: 固定価格 4,980円（ルール発動条件に関わらず） ────────────────
    "fixed_price_4980": {
        "type": "FIXED_PRICE",
        "adjustment": {"mode": "FIXED", "value": 4980},
        "constraints": {"min_margin_amount": None, "min_margin_rate": None, "price_ceiling": None},
        "scope": {"competitor_filter": "ALL_MAPPED"},
    },

    # ── Sample 5: 原価マークアップ 20%（仕入れ×1.2） ─────────────────────────
    "percentage_markup_20pct": {
        "type": "PERCENTAGE_MARKUP",
        "adjustment": {"mode": "PERCENTAGE", "value": 0.20},
        "constraints": {"min_margin_amount": None, "min_margin_rate": 0.15, "price_ceiling": None},
        "scope": {"competitor_filter": "ALL_MAPPED"},
    },

    # ── Sample 6: メイン競合のみ追随（PRIMARY_ONLY）──────────────────────────
    "beat_primary_only": {
        "type": "BEAT_LOWEST",
        "adjustment": {"mode": "FIXED", "value": -5},
        "constraints": {"min_margin_amount": 200, "min_margin_rate": None, "price_ceiling": None},
        "scope": {"competitor_filter": "PRIMARY_ONLY"},
    },
}
