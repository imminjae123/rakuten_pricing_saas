"""
Yahoo! Japan Shopping API v3 — HTTP client and response schemas.

Endpoint
--------
GET https://shopping.yahooapis.jp/ShoppingWebService/V3/itemSearch

Authentication
--------------
Pass ``appid=<YAHOO_CLIENT_ID>`` as a query parameter.
No OAuth is required for read-only item search.

Response structure (abridged)
------------------------------
{
    "hits": [
        {
            "name":    "商品名",
            "price":   12800,
            "url":     "https://store.shopping.yahoo.co.jp/...",
            "seller":  {"name": "ショップ名", "url": "..."},
            "image":   {"medium": "https://..."},
            "code":    "abc123-shop:item-code"   // stable item identifier
        },
        ...
    ],
    "totalResultsReturned": 10,
    "totalResultsAvailable": 1234,
    "firstResultsPosition": 1
}

Usage
-----
    from app.services.yahoo import YahooShoppingClient, YahooSearchParams

    async with YahooShoppingClient(client_id="YOUR_ID") as client:
        result = await client.search(YahooSearchParams(query="Nintendo Switch"))
        for item in result.hits:
            print(item.name, item.price)

Error handling
--------------
- httpx.HTTPStatusError is raised (via raise_for_status) for 4xx/5xx responses
  and wrapped in YahooAPIError with the original status code preserved.
- httpx.TimeoutException propagates unchanged — callers should handle it.
"""

from __future__ import annotations

from typing import Any

import httpx
from pydantic import BaseModel, Field, HttpUrl, model_validator


# ── Custom exceptions ─────────────────────────────────────────────────────────

class YahooAPIError(Exception):
    """Raised when the Yahoo! Shopping API returns a non-2xx response."""

    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(f"Yahoo API error {status_code}: {message}")
        self.status_code = status_code
        self.message = message


# ── Pydantic response schemas ─────────────────────────────────────────────────

class YahooSellerSchema(BaseModel):
    """Nested seller object inside a hit."""

    name: str | None = None
    url: str | None = None


class YahooImageSchema(BaseModel):
    """Nested image object inside a hit."""

    medium: str | None = None


class YahooItemHit(BaseModel):
    """
    Single product hit from the Yahoo! Shopping itemSearch response.

    Field mapping from Yahoo! API response:
        name          → item display name
        price         → current price in ¥ (integer)
        url           → product page URL
        code          → stable item identifier (shop:item-code format)
        seller.name   → seller / shop name
        image.medium  → product thumbnail URL
    """

    name: str
    price: int
    url: str
    code: str | None = None
    seller: YahooSellerSchema = Field(default_factory=YahooSellerSchema)
    image: YahooImageSchema = Field(default_factory=YahooImageSchema)

    @property
    def seller_name(self) -> str | None:
        return self.seller.name

    @property
    def image_url(self) -> str | None:
        return self.image.medium


class YahooSearchResponse(BaseModel):
    """
    Top-level response from GET /ShoppingWebService/V3/itemSearch.

    Only the fields used by this service are mapped; the full Yahoo response
    contains additional metadata that is intentionally ignored here.
    """

    hits: list[YahooItemHit] = Field(default_factory=list)
    total_results_returned: int = Field(0, alias="totalResultsReturned")
    total_results_available: int = Field(0, alias="totalResultsAvailable")
    first_results_position: int = Field(1, alias="firstResultsPosition")

    model_config = {"populate_by_name": True}


# ── Request parameter model ───────────────────────────────────────────────────

class YahooSearchParams(BaseModel):
    """
    Query parameters for the Yahoo! Shopping itemSearch endpoint.

    query   : search keyword (required)
    results : number of results to return (1–50, default 10)
    sort    : sort order
              "+price"  — price ascending  (cheapest first)
              "-price"  — price descending (most expensive first)
              "-score"  — relevance (default)
    """

    query: str = Field(..., min_length=1, description="Search keyword")
    results: int = Field(10, ge=1, le=50, description="Number of results (max 50)")
    sort: str = Field("-score", description="Sort order: +price | -price | -score")

    def to_query_params(self, appid: str) -> dict[str, Any]:
        """Serialize to the flat dict expected by httpx params=."""
        return {
            "appid": appid,
            "query": self.query,
            "results": self.results,
            "sort": self.sort,
        }


# ── HTTP client ───────────────────────────────────────────────────────────────

_YAHOO_SEARCH_URL = (
    "https://shopping.yahooapis.jp/ShoppingWebService/V3/itemSearch"
)
_DEFAULT_TIMEOUT = 10.0  # seconds


class YahooShoppingClient:
    """
    Async HTTP client for the Yahoo! Japan Shopping API v3.

    Designed as an async context manager so the underlying httpx.AsyncClient
    is properly opened and closed:

        async with YahooShoppingClient(client_id=YAHOO_CLIENT_ID) as client:
            result = await client.search(params)

    Parameters
    ----------
    client_id : YAHOO_CLIENT_ID value from environment / config.
    timeout   : Request timeout in seconds (default 10).
    """

    def __init__(self, client_id: str, timeout: float = _DEFAULT_TIMEOUT) -> None:
        if not client_id:
            raise ValueError("YAHOO_CLIENT_ID must not be empty")
        self._client_id = client_id
        self._timeout = timeout
        self._http: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "YahooShoppingClient":
        self._http = httpx.AsyncClient(timeout=self._timeout)
        return self

    async def __aexit__(self, *_: object) -> None:
        if self._http is not None:
            await self._http.aclose()
            self._http = None

    async def search(self, params: YahooSearchParams) -> YahooSearchResponse:
        """
        Call the Yahoo! Shopping itemSearch endpoint.

        Parameters
        ----------
        params : YahooSearchParams instance describing the search.

        Returns
        -------
        YahooSearchResponse with a `hits` list of matched products.

        Raises
        ------
        YahooAPIError      : Non-2xx HTTP response from Yahoo API.
        httpx.TimeoutException : Request timed out.
        RuntimeError       : Client used outside of async context manager.
        """
        if self._http is None:
            raise RuntimeError(
                "YahooShoppingClient must be used as an async context manager"
            )

        query_params = params.to_query_params(appid=self._client_id)

        try:
            response = await self._http.get(_YAHOO_SEARCH_URL, params=query_params)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise YahooAPIError(
                status_code=exc.response.status_code,
                message=exc.response.text[:300],
            ) from exc

        return YahooSearchResponse.model_validate(response.json())


# ── Convenience function (non-context-manager usage) ─────────────────────────

async def search_yahoo_items(
    client_id: str,
    query: str,
    results: int = 10,
    sort: str = "-score",
) -> YahooSearchResponse:
    """
    One-shot helper: open a client, search, close.

    Suitable for scripts and background tasks that do not need to reuse the
    underlying connection.  For high-throughput use-cases, prefer the
    YahooShoppingClient context manager directly.

    Parameters
    ----------
    client_id : YAHOO_CLIENT_ID.
    query     : Search keyword.
    results   : Number of results (1–50).
    sort      : Sort order string.

    Returns
    -------
    YahooSearchResponse
    """
    params = YahooSearchParams(query=query, results=results, sort=sort)
    async with YahooShoppingClient(client_id=client_id) as client:
        return await client.search(params)
