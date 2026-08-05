"""
SQLAlchemy v2.0 Async — Declarative Base + shared mixins.

All tenant-scoped tables inherit TimestampMixin.
UUID primary keys use server-side gen_random_uuid() so asyncpg
never has to round-trip for a PK before INSERT.
"""

from datetime import datetime

from sqlalchemy import DateTime, func, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""


class TimestampMixin:
    """Adds server-managed created_at / updated_at columns."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


def uuid_pk() -> Mapped[str]:
    """
    UUID v4 primary key column — server-generated via gen_random_uuid().
    Returns a mapped_column descriptor suitable for use as a class-level default.
    """
    return mapped_column(
        "id",
        server_default=text("gen_random_uuid()"),
        primary_key=True,
        nullable=False,
    )
