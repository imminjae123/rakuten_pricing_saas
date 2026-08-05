"""
MyProduct and CompetitorProduct models.

Security note — My_Products
----------------------------
`cost` and `min_margin_amount` / `min_margin_rate` are the most sensitive
columns in the system.  They MUST:
  1. Never appear in API response schemas sent to VIEWER-role users.
  2. Be covered by PostgreSQL RLS so cross-tenant reads are impossible
     at the DB layer even if application logic has a bug.

CompetitorProduct
-----------------
Stores a snapshot of a competitor item's metadata as discovered on
Rakuten Ichiba.  The `rakuten_item_code` is the stable identifier used
for API polling.  Price snapshots are written to Price_Histories (append-only).
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.tenant import Tenant
    from app.models.mapping import ProductMapping
    from app.models.rule import PricingRule
    from app.models.price_history import PriceHistory


class MyProduct(Base, TimestampMixin):
    """
    Seller's own product — registered for price monitoring.

    Sensitive columns
    -----------------
    cost                : purchase/manufacturing cost (¥)
    min_margin_amount   : minimum acceptable profit margin in ¥
    min_margin_rate     : minimum acceptable margin as a ratio (0.0–1.0)
                          optional; rule engine uses whichever is set.
    defensive_price     : pre-computed floor = cost + min_margin_amount
                          (maintained by app layer, NOT a generated column
                           so we can unit-test the rule engine independently)

    Constraints
    -----------
    - sku is unique per tenant
    - cost >= 0, min_margin_amount >= 0
    - RLS policy: tenant_id = current_setting('app.current_tenant_id')::uuid
    """

    __tablename__ = "my_products"
    __table_args__ = (
        Index("uq_my_products_tenant_sku", "tenant_id", "sku", unique=True),
        Index("ix_my_products_tenant_id", "tenant_id"),
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
    # Human-readable identifiers
    sku: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    rakuten_item_code: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Seller's own Rakuten item code (not competitor code)",
    )

    # ── Sensitive financial columns ────────────────────────────────────────────
    cost: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, comment="Purchase/manufacturing cost (¥)"
    )
    min_margin_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        server_default=text("0"),
        comment="Minimum profit floor in ¥ — used by rule engine",
    )
    min_margin_rate: Mapped[Decimal | None] = mapped_column(
        Numeric(6, 4),
        nullable=True,
        comment="Optional margin floor as a ratio e.g. 0.15 = 15%",
    )
    # Cached defensive floor: cost + min_margin_amount
    # Updated by the service layer whenever cost or min_margin_amount changes.
    defensive_price: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        server_default=text("0"),
        comment="Pre-computed price floor = cost + min_margin_amount",
    )

    # Current recommended selling price (set by rule engine)
    current_price: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2), nullable=True, comment="Last rule-engine recommended price"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, server_default=text("true"), nullable=False
    )

    # ── Relationships ──────────────────────────────────────────────────────────
    tenant: Mapped[Tenant] = relationship(
        "Tenant", back_populates="my_products", lazy="raise"
    )
    mappings: Mapped[list[ProductMapping]] = relationship(
        "ProductMapping", back_populates="my_product", lazy="raise"
    )
    pricing_rules: Mapped[list[PricingRule]] = relationship(
        "PricingRule", back_populates="my_product", lazy="raise"
    )
    price_histories: Mapped[list[PriceHistory]] = relationship(
        "PriceHistory",
        primaryjoin="and_(PriceHistory.product_ref_id == MyProduct.id, "
                    "PriceHistory.product_type == 'MY')",
        foreign_keys="[PriceHistory.product_ref_id]",
        lazy="raise",
        viewonly=True,
    )

    def __repr__(self) -> str:
        return f"<MyProduct id={self.id} sku={self.sku!r}>"


class CompetitorProduct(Base, TimestampMixin):
    """
    A competitor item on Rakuten Ichiba being monitored.

    `rakuten_item_code` is the stable Rakuten identifier used for
    IchibaItem/Search API calls.  One competitor product can be mapped
    to multiple MyProducts via ProductMapping (N:M bridge).

    Constraints
    -----------
    - rakuten_item_code is globally unique (same item is the same item
      regardless of which tenant is watching it).  Cross-tenant sharing
      of the row is intentional — only price history rows are tenant-scoped.
    """

    __tablename__ = "competitor_products"
    __table_args__ = (
        Index("ix_competitor_products_item_code", "rakuten_item_code", unique=True),
        Index("ix_competitor_products_shop_code", "shop_code"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    rakuten_item_code: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
        comment="Rakuten Ichiba item code — stable polling key",
    )
    shop_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    shop_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    item_name: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    item_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    # Latest known price — mirrored for quick reads; full history in Price_Histories
    latest_price: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="Most recent crawled price (¥)"
    )
    # All-time low price recorded in Price_Histories
    all_time_low_price: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="Triggers LINE notification when updated"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, server_default=text("true"), nullable=False
    )

    # ── Relationships ──────────────────────────────────────────────────────────
    mappings: Mapped[list[ProductMapping]] = relationship(
        "ProductMapping", back_populates="competitor_product", lazy="raise"
    )
    price_histories: Mapped[list[PriceHistory]] = relationship(
        "PriceHistory",
        primaryjoin="and_(PriceHistory.product_ref_id == CompetitorProduct.id, "
                    "PriceHistory.product_type == 'COMPETITOR')",
        foreign_keys="[PriceHistory.product_ref_id]",
        lazy="raise",
        viewonly=True,
    )

    def __repr__(self) -> str:
        return f"<CompetitorProduct id={self.id} item_code={self.rakuten_item_code!r}>"
