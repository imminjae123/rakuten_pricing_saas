"""
Tenant model.

One row per Rakuten seller shop.  All other tenant-scoped tables carry
a `tenant_id` FK pointing here.  PostgreSQL RLS policies use
    current_setting('app.current_tenant_id')::uuid
to filter every query automatically.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.product import MyProduct
    from app.models.rule import PricingRule


class Tenant(Base, TimestampMixin):
    """
    Represents one B2B customer (Rakuten seller shop).

    Constraints
    -----------
    - shop_code is unique globally (each shop has exactly one tenant record)
    - is_active allows soft-suspension without data deletion
    """

    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    shop_name: Mapped[str] = mapped_column(String(255), nullable=False)
    # Rakuten shop identifier — used to scope API calls
    shop_code: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    rakuten_shop_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # Subscription / active flag — no hard delete
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"), nullable=False)
    # Contact info
    contact_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # LINE User ID for push notifications (owner-level)
    line_user_id: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # ── Relationships ──────────────────────────────────────────────────────────
    users: Mapped[list[User]] = relationship("User", back_populates="tenant", lazy="raise")
    my_products: Mapped[list[MyProduct]] = relationship(
        "MyProduct", back_populates="tenant", lazy="raise"
    )
    pricing_rules: Mapped[list[PricingRule]] = relationship(
        "PricingRule", back_populates="tenant", lazy="raise"
    )

    def __repr__(self) -> str:
        return f"<Tenant id={self.id} shop_code={self.shop_code!r}>"
