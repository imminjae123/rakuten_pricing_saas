"""
Pydantic v2 schemas for Price History and Audit Log endpoints.

GET /api/v1/histories/products/{product_id}     — price history for one product
GET /api/v1/histories/competitor/{competitor_id} — competitor price timeline
GET /api/v1/histories/recommendations            — recommended price timeline for tenant

GET /api/v1/audit-logs                           — tenant audit log (all roles, read-only)
GET /api/v1/audit-logs/{id}                      — single audit entry

Access control
--------------
All history and audit endpoints are read-only.
VIEWER role can read, but MyProduct-related histories that expose cost data
are filtered in the service layer before returning.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# ── Price History ─────────────────────────────────────────────────────────────

class PriceHistoryItem(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    product_ref_id: uuid.UUID
    product_type: str  # MY | COMPETITOR
    price: int
    recommended_price: int | None
    source: str  # CRAWL | MANUAL | RULE
    rule_id: uuid.UUID | None
    is_all_time_low: bool
    captured_at: datetime

    model_config = {"from_attributes": True}


class PriceHistoryListResponse(BaseModel):
    items: list[PriceHistoryItem]
    total: int
    # Pagination cursors (cursor-based for time-series efficiency)
    next_cursor: str | None = Field(None, description="ISO8601 timestamp cursor for next page")
    has_more: bool


class PriceHistoryQueryParams(BaseModel):
    """
    Query parameters for GET /api/v1/histories/products/{product_id}

    cursor    : captured_at timestamp to paginate from (ISO8601)
    limit     : max records per page (default 50, max 200)
    source    : filter by CRAWL | MANUAL | RULE
    from_date : inclusive start timestamp
    to_date   : inclusive end timestamp
    """

    cursor: datetime | None = None
    limit: int = Field(50, ge=1, le=200)
    source: str | None = Field(None, pattern="^(CRAWL|MANUAL|RULE)$")
    from_date: datetime | None = None
    to_date: datetime | None = None


# ── Recommended Price Timeline ────────────────────────────────────────────────

class RecommendationTimelineItem(BaseModel):
    """
    Single entry in the rule-engine recommendation timeline.
    Combines PriceHistory (RULE source) with rule metadata for UI display.
    """

    history_id: uuid.UUID
    my_product_id: uuid.UUID
    product_name: str
    sku: str
    recommended_price: int
    reference_competitor_price: int | None
    rule_id: uuid.UUID | None
    rule_name: str | None
    floor_applied: bool | None
    captured_at: datetime


class RecommendationTimelineResponse(BaseModel):
    items: list[RecommendationTimelineItem]
    total: int
    next_cursor: str | None
    has_more: bool


# ── Audit Log ─────────────────────────────────────────────────────────────────

class AuditLogItem(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    actor_user_id: uuid.UUID | None
    actor_email: str | None = Field(None, description="Joined from users table for display")
    entity_type: str
    entity_id: uuid.UUID | None
    action: str
    details: dict[str, Any]
    occurred_at: datetime

    model_config = {"from_attributes": True}


class AuditLogListResponse(BaseModel):
    items: list[AuditLogItem]
    total: int
    next_cursor: str | None
    has_more: bool


class AuditLogQueryParams(BaseModel):
    """
    GET /api/v1/audit-logs query parameters.

    cursor      : occurred_at timestamp cursor for pagination
    limit       : max 200 per page
    entity_type : filter by PRICING_RULE | MY_PRODUCT | PRICE_RECOMMENDATION etc.
    action      : filter by RULE_CREATED | RULE_FIRED | ALL_TIME_LOW etc.
    actor_user_id : filter by operator
    from_date / to_date : time range filter
    """

    cursor: datetime | None = None
    limit: int = Field(50, ge=1, le=200)
    entity_type: str | None = None
    action: str | None = None
    actor_user_id: uuid.UUID | None = None
    from_date: datetime | None = None
    to_date: datetime | None = None
