"""
Pydantic v2 schemas for Pricing Rule endpoints.

GET    /api/v1/rules               — list rules for tenant (all roles)
POST   /api/v1/rules               — create rule (OWNER, MANAGER)
GET    /api/v1/rules/{id}          — rule detail (all roles)
PUT    /api/v1/rules/{id}          — full replace (OWNER, MANAGER)
PATCH  /api/v1/rules/{id}          — partial update (OWNER, MANAGER)
DELETE /api/v1/rules/{id}          — soft-delete (OWNER)
POST   /api/v1/rules/simulate      — stateless simulation (all roles)
POST   /api/v1/rules/{id}/simulate — simulate saved rule with override prices (all roles)

Design note: simulate endpoints are STATELESS — they never write to DB.
They call evaluate_rule() directly and return the RuleResult.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, model_validator


# ── Condition sub-schemas (for documentation + validation) ────────────────────

class AdjustmentSchema(BaseModel):
    mode: str | None = Field(None, pattern="^(FIXED|PERCENTAGE)$")
    value: float | None = None


class ConstraintsSchema(BaseModel):
    min_margin_amount: float | None = Field(None, ge=0)
    min_margin_rate: float | None = Field(None, ge=0, le=1)
    price_ceiling: int | None = Field(None, ge=0)


class ScopeSchema(BaseModel):
    competitor_filter: str = Field(
        "ALL_MAPPED", pattern="^(ALL_MAPPED|PRIMARY_ONLY)$"
    )


class RuleConditionSchema(BaseModel):
    """
    Validated JSONB structure for PricingRule.condition.
    Used in create / update requests to validate the condition before storage.
    """

    type: str = Field(
        ...,
        pattern="^(BEAT_LOWEST|MATCH_LOWEST|FIXED_PRICE|PERCENTAGE_MARKUP)$",
        examples=["BEAT_LOWEST"],
    )
    adjustment: AdjustmentSchema = Field(default_factory=AdjustmentSchema)
    constraints: ConstraintsSchema = Field(default_factory=ConstraintsSchema)
    scope: ScopeSchema = Field(default_factory=ScopeSchema)

    @model_validator(mode="after")
    def validate_beat_lowest_has_adjustment(self) -> "RuleConditionSchema":
        if self.type == "BEAT_LOWEST":
            if self.adjustment.mode is None or self.adjustment.value is None:
                raise ValueError(
                    "BEAT_LOWEST rule requires adjustment.mode and adjustment.value"
                )
        if self.type == "FIXED_PRICE":
            if self.adjustment.value is None:
                raise ValueError("FIXED_PRICE rule requires adjustment.value (the fixed price)")
        if self.type == "PERCENTAGE_MARKUP":
            if self.adjustment.value is None:
                raise ValueError("PERCENTAGE_MARKUP requires adjustment.value (e.g. 0.20 for 20%)")
        return self

    def to_jsonb(self) -> dict[str, Any]:
        """Serialize to the canonical JSONB dict for DB storage."""
        return self.model_dump(mode="json")


# ── Rule CRUD schemas ─────────────────────────────────────────────────────────

class PricingRuleCreateRequest(BaseModel):
    """POST /api/v1/rules"""

    name: str = Field(..., min_length=1, max_length=255, examples=["Beat by 10 yen"])
    description: str | None = None
    # NULL = applies to all products of the tenant
    my_product_id: uuid.UUID | None = None
    condition: RuleConditionSchema
    priority: int = Field(100, ge=1, le=9999)


class PricingRuleUpdateRequest(BaseModel):
    """PUT /api/v1/rules/{id} — full replace"""

    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    my_product_id: uuid.UUID | None = None
    condition: RuleConditionSchema
    priority: int = Field(100, ge=1, le=9999)
    is_active: bool = True


class PricingRulePatchRequest(BaseModel):
    """PATCH /api/v1/rules/{id} — partial update"""

    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    my_product_id: uuid.UUID | None = None
    condition: RuleConditionSchema | None = None
    priority: int | None = Field(None, ge=1, le=9999)
    is_active: bool | None = None


class PricingRuleResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    my_product_id: uuid.UUID | None
    name: str
    description: str | None
    condition: dict[str, Any]
    priority: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PricingRuleListResponse(BaseModel):
    items: list[PricingRuleResponse]
    total: int


# ── Simulation schemas ────────────────────────────────────────────────────────

class RuleSimulateRequest(BaseModel):
    """
    POST /api/v1/rules/simulate  — stateless, pass full condition inline
    POST /api/v1/rules/{id}/simulate — use saved rule; override competitor prices

    competitor_prices: list of current competitor prices in ¥ (integer).
    For PRIMARY_ONLY scope, place the primary competitor price first.

    cost / min_margin_amount: product financial data required for floor calc.
    If calling /rules/{id}/simulate these are loaded from the saved product
    when my_product_id is set; they can be overridden here for what-if analysis.
    """

    competitor_prices: list[int] = Field(
        ...,
        min_length=1,
        examples=[[4500, 4800, 5000]],
        description="List of competitor prices in ¥ (integer). Min 1 value required.",
    )
    # Required for /rules/simulate (no saved rule to read from)
    # Optional override for /rules/{id}/simulate
    condition: RuleConditionSchema | None = Field(
        None,
        description="Full condition schema — required for stateless /simulate endpoint",
    )
    cost: float | None = Field(None, ge=0, description="Product cost override (¥)")
    min_margin_amount: float | None = Field(None, ge=0, description="Min margin override (¥)")
    min_margin_rate: float | None = Field(None, ge=0, le=1)


class RuleSimulateResponse(BaseModel):
    """
    Stateless simulation result — never persisted.
    Contains the full audit trail of the calculation for UI display.
    """

    recommended_price: int = Field(..., description="Final price after all constraints (¥)")
    raw_price: int = Field(..., description="Price before floor / ceiling (¥)")
    defensive_floor: int = Field(..., description="cost + effective min_margin (¥)")
    floor_applied: bool = Field(..., description="True if raw_price was raised to floor")
    ceiling_applied: bool = Field(..., description="True if price was capped at ceiling")
    reference_price: int | None = Field(..., description="Competitor reference price used")
    explanation: str = Field(..., description="Step-by-step calculation trace")

    # Echo back inputs for UI display
    competitor_prices_used: list[int]
    rule_type: str
