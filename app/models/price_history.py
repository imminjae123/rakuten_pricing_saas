"""
PriceHistory model — append-only time-series price snapshots.

Design principles (from AGENTS.md)
-----------------------------------
- NEVER UPDATE: price history rows are immutable snapshots.
  A PostgreSQL trigger enforces this at the DB level (see RLS migration).
- product_type discriminates between MY (own product) and COMPETITOR rows,
  allowing a single table to store both streams.
- recommended_price is only populated for MY-product rows that were produced
  by a rule-engine firing (NULL for raw crawl snapshots).
- rule_id links back to the PricingRule that was applied (nullable).
- source tracks how the snapshot was created:
    CRAWL   — periodic Yahoo! Shopping API batch
    MANUAL  — operator override
    RULE    — rule engine output

Index strategy
--------------
- (product_ref_id, captured_at DESC) — primary time-series access pattern
- (tenant_id, captured_at DESC) — dashboard "all products" feed
- (product_type, product_ref_id) — discriminator + FK lookups
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Index, Integer, Numeric, String, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class PriceHistory(Base):
    """
    Immutable price snapshot row.

    No `updated_at` — snapshots are write-once.
    `captured_at` is set server-side to ensure consistent timezone handling.

    Constraints
    -----------
    - No UPDATE or DELETE allowed (DB trigger raises an exception)
    - tenant_id enables RLS filtering for dashboard / audit queries
    - price must be >= 0
    """

    __tablename__ = "price_histories"
    __table_args__ = (
        # Primary time-series access: "give me price history for product X"
        Index("ix_price_histories_product_time", "product_ref_id", "captured_at"),
        # Dashboard: "give me all recent events for tenant Y"
        Index("ix_price_histories_tenant_time", "tenant_id", "captured_at"),
        # Rule-engine lookup: "which rows resulted from rule Z?"
        Index("ix_price_histories_rule_id", "rule_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    # RLS anchor — even though CompetitorProduct rows are shared, history is
    # always scoped to the tenant that triggered the crawl.
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    # Polymorphic FK — points to either my_products.id or competitor_products.id
    product_ref_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        comment="FK to my_products.id or competitor_products.id",
    )
    product_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="MY | COMPETITOR",
    )

    # Raw crawled price from Yahoo! Shopping API (¥, integer)
    price: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Crawled market price (¥)"
    )
    # Only populated for RULE-sourced MY-product rows
    recommended_price: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="Rule-engine output price (¥)"
    )

    source: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default=text("'CRAWL'"),
        comment="CRAWL | MANUAL | RULE",
    )

    # Nullable FK to the rule that produced this recommendation
    rule_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("pricing_rules.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Server-side timestamp — do NOT rely on application-layer clock
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    # Flag set when this snapshot established a new all-time low
    is_all_time_low: Mapped[bool] = mapped_column(
        "is_all_time_low",
        # Boolean type
        type_=__import__("sqlalchemy").Boolean,
        server_default=text("false"),
        nullable=False,
    )

    def __repr__(self) -> str:
        return (
            f"<PriceHistory id={self.id} "
            f"product={self.product_ref_id} price={self.price} "
            f"captured_at={self.captured_at}>"
        )
