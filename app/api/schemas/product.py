"""
Pydantic v2 schemas for Product and Mapping endpoints.

GET    /api/v1/products                        — list my products (all roles)
POST   /api/v1/products                        — create my product (OWNER, MANAGER)
GET    /api/v1/products/{id}                   — get my product detail (all roles)
PATCH  /api/v1/products/{id}                   — update my product (OWNER, MANAGER)
DELETE /api/v1/products/{id}                   — soft-delete (OWNER)

POST   /api/v1/products/{id}/mappings          — add competitor mapping (OWNER, MANAGER)
GET    /api/v1/products/{id}/mappings          — list mappings for a product (all roles)
DELETE /api/v1/products/{id}/mappings/{map_id} — remove mapping (OWNER, MANAGER)

POST   /api/v1/competitors                     — register competitor product (OWNER, MANAGER)
GET    /api/v1/competitors/{id}                — competitor detail + latest price (all roles)

Security notes
--------------
- MyProductResponse OMITS cost / min_margin_* / defensive_price for VIEWER role.
- MyProductDetailResponse (OWNER / MANAGER only) includes sensitive fields.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


# ── MyProduct — Request schemas ───────────────────────────────────────────────

class MyProductCreateRequest(BaseModel):
    """POST /api/v1/products"""

    sku: str = Field(..., min_length=1, max_length=100, examples=["SKU-001"])
    name: str = Field(..., min_length=1, max_length=500)
    description: str | None = None
    yahoo_item_code: str | None = Field(None, max_length=255)
    cost: Decimal = Field(..., ge=0, decimal_places=2, examples=[3000.00])
    min_margin_amount: Decimal = Field(Decimal("0"), ge=0, decimal_places=2, examples=[500.00])
    min_margin_rate: Decimal | None = Field(None, ge=0, le=1, decimal_places=4, examples=[0.15])


class MyProductUpdateRequest(BaseModel):
    """PATCH /api/v1/products/{id} — all fields optional"""

    name: str | None = Field(None, min_length=1, max_length=500)
    description: str | None = None
    yahoo_item_code: str | None = None
    cost: Decimal | None = Field(None, ge=0, decimal_places=2)
    min_margin_amount: Decimal | None = Field(None, ge=0, decimal_places=2)
    min_margin_rate: Decimal | None = Field(None, ge=0, le=1, decimal_places=4)
    is_active: bool | None = None


# ── MyProduct — Response schemas ──────────────────────────────────────────────

class MyProductResponse(BaseModel):
    """
    Safe response for VIEWER role — sensitive financial fields are EXCLUDED.
    """

    id: uuid.UUID
    tenant_id: uuid.UUID
    sku: str
    name: str
    description: str | None
    yahoo_item_code: str | None
    current_price: Decimal | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class MyProductDetailResponse(MyProductResponse):
    """
    Full response for OWNER / MANAGER — includes sensitive financial fields.
    This schema must NEVER be returned to VIEWER-role requests.
    """

    cost: Decimal
    min_margin_amount: Decimal
    min_margin_rate: Decimal | None
    defensive_price: Decimal


class MyProductListResponse(BaseModel):
    items: list[MyProductResponse]
    total: int
    page: int
    page_size: int


# ── CompetitorProduct ─────────────────────────────────────────────────────────

class CompetitorProductCreateRequest(BaseModel):
    """POST /api/v1/competitors"""

    yahoo_item_code: str = Field(..., min_length=1, max_length=255)
    shop_code: str | None = Field(None, max_length=100)
    shop_name: str | None = Field(None, max_length=255)
    item_name: str | None = Field(None, max_length=1000)
    item_url: str | None = Field(None, max_length=1000)


class CompetitorProductResponse(BaseModel):
    id: uuid.UUID
    yahoo_item_code: str
    shop_code: str | None
    shop_name: str | None
    item_name: str | None
    item_url: str | None
    latest_price: int | None
    all_time_low_price: int | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── ProductMapping ────────────────────────────────────────────────────────────

class ProductMappingCreateRequest(BaseModel):
    """POST /api/v1/products/{id}/mappings"""

    competitor_product_id: uuid.UUID
    is_primary: bool = False
    label: str | None = Field(None, max_length=100)


class ProductMappingResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    my_product_id: uuid.UUID
    competitor_product_id: uuid.UUID
    is_primary: bool
    label: str | None
    # Embedded competitor snapshot for UI convenience
    competitor: CompetitorProductResponse
    created_at: datetime

    model_config = {"from_attributes": True}


class ProductMappingListResponse(BaseModel):
    items: list[ProductMappingResponse]
    total: int
