"""
User model — tenant-scoped staff accounts with RBAC.

Roles (from spec F-2)
---------------------
OWNER   — full control (billing, rules, accounts)
MANAGER — product mapping + rule configuration
VIEWER  — read-only dashboard / reports
"""

from __future__ import annotations

import uuid
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Index, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.tenant import Tenant


class UserRole(StrEnum):
    OWNER = "OWNER"
    MANAGER = "MANAGER"
    VIEWER = "VIEWER"


class User(Base, TimestampMixin):
    """
    Staff account belonging to a single Tenant.

    Constraints
    -----------
    - email is unique per tenant (same email can exist in different tenants)
    - hashed_password must never be returned in API responses
    - RLS: users can only see other users in the same tenant
    """

    __tablename__ = "users"
    __table_args__ = (
        # One email address per tenant (cross-tenant duplicates are OK)
        Index("uq_users_tenant_email", "tenant_id", "email", unique=True),
        # Fast lookup by tenant for admin list endpoints
        Index("ix_users_tenant_id", "tenant_id"),
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
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    # bcrypt hash — never plaintext
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    role: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default=text("'VIEWER'"),
        comment="OWNER | MANAGER | VIEWER",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, server_default=text("true"), nullable=False
    )
    # Per-user LINE User ID for direct push notifications
    line_user_id: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # ── Relationships ──────────────────────────────────────────────────────────
    tenant: Mapped[Tenant] = relationship("Tenant", back_populates="users", lazy="raise")

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email!r} role={self.role}>"
