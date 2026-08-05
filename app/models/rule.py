"""
PricingRule model — tenant-scoped business rules stored as JSONB.

JSONB `condition` schema
------------------------
The rule engine (app/domain/rule_engine.py) interprets the following
top-level keys:

{
    "type": "BEAT_LOWEST",          // rule strategy identifier
    "adjustment": {
        "mode": "FIXED",            // FIXED | PERCENTAGE
        "value": -10                // negative = undercut, positive = markup
    },
    "constraints": {
        "min_margin_amount": 500,   // override per-rule (optional)
        "min_margin_rate": null,    // ratio e.g. 0.15
        "price_ceiling": null       // never recommend above this
    },
    "scope": {
        "competitor_filter": "ALL_MAPPED" // ALL_MAPPED | PRIMARY_ONLY
    }
}

Supported `type` values (extensible — add without DB migration):
  BEAT_LOWEST        — undercut the minimum mapped competitor price
  MATCH_LOWEST       — match the minimum mapped competitor price
  FIXED_PRICE        — always recommend a constant price
  PERCENTAGE_MARKUP  — cost × (1 + rate)

Rule evaluation order (from AGENTS.md):
  1. Compute recommended_price from `condition`
  2. Check minimum margin floor (cost + min_margin_amount)
  3. Apply defensive price floor — never go below floor

Simulation endpoint (F-6): POST /rules/{id}/simulate
  accepts a hypothetical competitor_price and returns recommended_price
  WITHOUT persisting anything.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.tenant import Tenant
    from app.models.product import MyProduct


class PricingRule(Base, TimestampMixin):
    """
    A named pricing rule scoped to a tenant and optionally a specific product.

    Constraints
    -----------
    - `condition` is JSONB — never flatten to columns (AGENTS.md requirement)
    - `name` is unique per tenant
    - `priority` controls evaluation order when multiple rules match
      (lower number = higher priority)
    - `is_active` allows disabling without deletion
    - RLS: tenant_id = current_setting('app.current_tenant_id')::uuid

    Audit
    -----
    Every INSERT or UPDATE on this table must produce an Audit_Log row
    in the same transaction (enforced at the service layer).
    """

    __tablename__ = "pricing_rules"
    __table_args__ = (
        Index("uq_pricing_rules_tenant_name", "tenant_id", "name", unique=True),
        Index("ix_pricing_rules_tenant_id", "tenant_id"),
        Index("ix_pricing_rules_my_product_id", "my_product_id"),
        # GIN index for JSONB condition — enables @> / ? operators
        Index(
            "ix_pricing_rules_condition_gin",
            "condition",
            postgresql_using="gin",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    # NULL means the rule applies to ALL products of this tenant
    my_product_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("my_products.id", ondelete="SET NULL"),
        nullable=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Core JSONB rule payload ────────────────────────────────────────────────
    # See module docstring for the expected schema.
    condition: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        comment="Rule strategy + adjustment + constraints — see module docstring",
    )

    priority: Mapped[int] = mapped_column(
        Integer,
        server_default=text("100"),
        nullable=False,
        comment="Evaluation order — lower = higher priority",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, server_default=text("true"), nullable=False
    )

    # ── Relationships ──────────────────────────────────────────────────────────
    tenant: Mapped[Tenant] = relationship(
        "Tenant", back_populates="pricing_rules", lazy="raise"
    )
    my_product: Mapped[MyProduct | None] = relationship(
        "MyProduct", back_populates="pricing_rules", lazy="raise"
    )

    def __repr__(self) -> str:
        return f"<PricingRule id={self.id} name={self.name!r} priority={self.priority}>"
