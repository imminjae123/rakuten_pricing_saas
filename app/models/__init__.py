"""
app/models/__init__.py

Centralised import so Alembic env.py and the rest of the application
only need to do:

    from app.models import Base, Tenant, User, ...

Import order matters for SQLAlchemy mapper configuration — Base must
be imported first, then all concrete models so their table metadata
is registered before any engine / migration tooling inspects Base.metadata.
"""

from app.models.base import Base, TimestampMixin  # noqa: F401
from app.models.tenant import Tenant  # noqa: F401
from app.models.user import User, UserRole  # noqa: F401
from app.models.product import MyProduct, CompetitorProduct  # noqa: F401
from app.models.mapping import ProductMapping  # noqa: F401
from app.models.rule import PricingRule  # noqa: F401
from app.models.price_history import PriceHistory  # noqa: F401
from app.models.audit_log import AuditLog  # noqa: F401

__all__ = [
    "Base",
    "TimestampMixin",
    "Tenant",
    "User",
    "UserRole",
    "MyProduct",
    "CompetitorProduct",
    "ProductMapping",
    "PricingRule",
    "PriceHistory",
    "AuditLog",
]
