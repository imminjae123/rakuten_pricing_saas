"""
AuditLog model — immutable append-only audit trail.

Design principles (from AGENTS.md)
-----------------------------------
- NO UPDATE or DELETE endpoints exist for this table — ever.
- NO soft-delete: rows are permanent.
- Every rule change AND every rule-engine firing must produce one audit row
  in the SAME DB transaction as the price recommendation save (atomicity N-2).
- A PostgreSQL trigger prevents UPDATE/DELETE at the DB level.

`details` JSONB schema (examples)
----------------------------------
Rule change:
{
    "action": "RULE_UPDATED",
    "rule_id": "...",
    "before": { ...old condition... },
    "after":  { ...new condition... }
}

Rule-engine firing:
{
    "action": "RULE_FIRED",
    "rule_id": "...",
    "competitor_price": 4500,
    "rule_name": "Beat by 10 yen",
    "recommended_price": 4490,
    "defensive_price_floor": 3500,
    "floor_applied": false
}

All-time low detected:
{
    "action": "ALL_TIME_LOW",
    "competitor_product_id": "...",
    "previous_low": 4800,
    "new_low": 4500
}

Access control
--------------
GET /audit-logs is available to all roles (OWNER, MANAGER, VIEWER).
The RLS policy on this table ensures tenants see only their own logs.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, String, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AuditLog(Base):
    """
    Immutable audit log row.

    No timestamps mixin — only `occurred_at` (write-once, server-set).
    No `updated_at` column by design.

    Constraints
    -----------
    - DB trigger raises on any UPDATE or DELETE attempt
    - tenant_id RLS ensures cross-tenant isolation
    - actor_user_id is nullable for system-initiated events (crawl, scheduler)
    """

    __tablename__ = "audit_logs"
    __table_args__ = (
        # Primary access: chronological per tenant
        Index("ix_audit_logs_tenant_occurred", "tenant_id", "occurred_at"),
        # Filter by actor
        Index("ix_audit_logs_actor_user_id", "actor_user_id"),
        # Filter by entity type + id (e.g. all events for rule X)
        Index("ix_audit_logs_entity", "entity_type", "entity_id"),
        # GIN for JSONB detail queries
        Index(
            "ix_audit_logs_details_gin",
            "details",
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
    # NULL for system-generated events (crawl worker, scheduler)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # What kind of entity was affected
    entity_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="PRICING_RULE | MY_PRODUCT | COMPETITOR_PRODUCT | PRICE_RECOMMENDATION",
    )
    entity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        comment="PK of the affected entity row",
    )

    # High-level action label — quick filtering without parsing JSONB
    action: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="RULE_CREATED | RULE_UPDATED | RULE_FIRED | ALL_TIME_LOW | ...",
    )

    # Full structured context — see module docstring for schema examples
    details: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )

    # Server-side clock — do not trust application timestamps for audit records
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    def __repr__(self) -> str:
        return (
            f"<AuditLog id={self.id} action={self.action!r} "
            f"tenant={self.tenant_id} occurred_at={self.occurred_at}>"
        )
