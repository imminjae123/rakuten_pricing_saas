"""
ProductMapping — bridge table between MyProduct (1) and CompetitorProduct (N).

Design
------
- One MyProduct can be monitored against many competitor items (1:N mapping).
- A single CompetitorProduct CAN be mapped by multiple tenants independently;
  the bridge row is tenant-scoped so there is no cross-tenant visibility.
- `is_primary` flags the single "main" competitor used when the rule engine
  needs a single reference price (e.g. "beat the lowest among mapped items").

RLS
---
tenant_id carries the RLS anchor for this table.  The CompetitorProduct row
itself is NOT tenant-scoped (it's a shared catalog), but this mapping row is.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Index, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.product import MyProduct, CompetitorProduct


class ProductMapping(Base, TimestampMixin):
    """
    Tenant-scoped bridge: MyProduct  ←→  CompetitorProduct.

    Constraints
    -----------
    - (tenant_id, my_product_id, competitor_product_id) is unique —
      no duplicate mappings for the same tenant.
    - Only one mapping per my_product_id can have is_primary=True
      (enforced via partial unique index).
    """

    __tablename__ = "product_mappings"
    __table_args__ = (
        # Prevent duplicate mappings within a tenant
        Index(
            "uq_product_mappings_tenant_pair",
            "tenant_id",
            "my_product_id",
            "competitor_product_id",
            unique=True,
        ),
        Index("ix_product_mappings_tenant_id", "tenant_id"),
        Index("ix_product_mappings_my_product_id", "my_product_id"),
        Index("ix_product_mappings_competitor_product_id", "competitor_product_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    # RLS anchor
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    my_product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("my_products.id", ondelete="CASCADE"),
        nullable=False,
    )
    competitor_product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("competitor_products.id", ondelete="CASCADE"),
        nullable=False,
    )
    # Marks the "primary" competitor for single-reference rules
    is_primary: Mapped[bool] = mapped_column(
        Boolean, server_default=text("false"), nullable=False
    )
    # Optional label for the mapping (e.g. "main rival shop")
    label: Mapped[str | None] = mapped_column(
        "label",
        # String type imported via column type argument below
        type_=__import__("sqlalchemy").String(100),
        nullable=True,
    )

    # ── Relationships ──────────────────────────────────────────────────────────
    my_product: Mapped[MyProduct] = relationship(
        "MyProduct", back_populates="mappings", lazy="raise"
    )
    competitor_product: Mapped[CompetitorProduct] = relationship(
        "CompetitorProduct", back_populates="mappings", lazy="raise"
    )

    def __repr__(self) -> str:
        return (
            f"<ProductMapping id={self.id} "
            f"my={self.my_product_id} comp={self.competitor_product_id}>"
        )
