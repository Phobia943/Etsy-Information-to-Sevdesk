"""
Etsy Open API v3 client with OAuth2 support.

TODO: Verify exact Etsy API v3 endpoints and scopes from official documentation:
https://developers.etsy.com/documentation/reference
"""

from datetime import datetime
from typing import Any, Optional

from app.clients.base import BaseAPIClient, AuthenticationError
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class EtsyClient(BaseAPIClient):
    """
    Etsy Open API v3 client.

    Handles OAuth2 authentication, pagination, and Etsy-specific error handling.
    """

    def __init__(self) -> None:
        super().__init__(
            base_url=settings.etsy_api_base_url,
            timeout=settings.etsy_api_timeout,
            rate_limit=settings.etsy_rate_limit,
        )
        self.shop_id = settings.etsy_shop_id
        self.client_id = settings.etsy_client_id
        self.client_secret = settings.etsy_client_secret
        self.refresh_token = settings.etsy_refresh_token
        self.access_token: Optional[str] = None

    async def _ensure_authenticated(self) -> None:
        """
        Ensure we have a valid access token.

        Uses OAuth2 refresh token flow to obtain access token.
        """
        if self.access_token is None:
            await self._refresh_access_token()

    async def _refresh_access_token(self) -> None:
        """
        Refresh OAuth2 access token using refresh token.

        TODO: Verify exact token endpoint and parameters from Etsy docs
        """
        logger.info("Refreshing Etsy access token")

        # TODO: Implement proper OAuth2 token refresh
        # Placeholder implementation - replace with actual Etsy OAuth2 flow
        # token_url = "https://api.etsy.com/v3/public/oauth/token"
        # payload = {
        #     "grant_type": "refresh_token",
        #     "refresh_token": self.refresh_token,
        #     "client_id": self.client_id,
        #     "client_secret": self.client_secret,
        # }
        # response = await self.post(token_url, data=payload)
        # self.access_token = response["access_token"]

        # For now, use refresh token as placeholder
        self.access_token = self.refresh_token
        logger.info("Access token refreshed")

    async def _get_headers(self) -> dict[str, str]:
        """Get headers with authentication."""
        await self._ensure_authenticated()
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
            "x-api-key": self.client_id,
        }

    async def get_shop(self) -> dict[str, Any]:
        """
        Get shop information.

        Returns:
            Shop data from Etsy API
        """
        headers = await self._get_headers()
        return await self.get(f"/application/shops/{self.shop_id}", headers=headers)

    async def get_orders(
        self,
        limit: int = 100,
        offset: int = 0,
        min_created: Optional[datetime] = None,
        max_created: Optional[datetime] = None,
    ) -> dict[str, Any]:
        """
        Get shop orders with pagination.

        TODO: Verify exact endpoint and parameters from Etsy API docs

        Args:
            limit: Number of results per page
            offset: Pagination offset
            min_created: Minimum creation date
            max_created: Maximum creation date

        Returns:
            Orders data with pagination info
        """
        headers = await self._get_headers()
        params: dict[str, Any] = {
            "limit": limit,
            "offset": offset,
        }

        if min_created:
            params["min_created"] = int(min_created.timestamp())
        if max_created:
            params["max_created"] = int(max_created.timestamp())

        endpoint = f"/application/shops/{self.shop_id}/receipts"
        return await self.get(endpoint, headers=headers, params=params)

    async def get_order_by_id(self, order_id: str) -> dict[str, Any]:
        """
        Get specific order by ID.

        Args:
            order_id: Etsy receipt/order ID

        Returns:
            Order data
        """
        headers = await self._get_headers()
        endpoint = f"/application/shops/{self.shop_id}/receipts/{order_id}"
        return await self.get(endpoint, headers=headers)

    async def get_transactions(self, order_id: str) -> dict[str, Any]:
        """
        Get transactions (line items) for an order.

        Args:
            order_id: Etsy receipt/order ID

        Returns:
            Transaction data
        """
        headers = await self._get_headers()
        endpoint = f"/application/shops/{self.shop_id}/receipts/{order_id}/transactions"
        return await self.get(endpoint, headers=headers)

    async def get_payment_account_ledger_entries(
        self,
        limit: int = 100,
        offset: int = 0,
        min_created: Optional[datetime] = None,
        max_created: Optional[datetime] = None,
    ) -> dict[str, Any]:
        """
        Get payment account ledger entries (fees, charges, payouts).

        TODO: Verify exact endpoint for fees/charges/payouts

        Args:
            limit: Number of results per page
            offset: Pagination offset
            min_created: Minimum creation date
            max_created: Maximum creation date

        Returns:
            Ledger entries data
        """
        headers = await self._get_headers()
        params: dict[str, Any] = {
            "limit": limit,
            "offset": offset,
        }

        if min_created:
            params["min_created"] = int(min_created.timestamp())
        if max_created:
            params["max_created"] = int(max_created.timestamp())

        # TODO: Replace with actual endpoint for ledger entries
        endpoint = f"/application/shops/{self.shop_id}/payment-account/ledger-entries"
        return await self.get(endpoint, headers=headers, params=params)

    async def get_refunds(
        self,
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, Any]:
        """
        Get shop refunds.

        TODO: Verify refunds endpoint

        Args:
            limit: Number of results per page
            offset: Pagination offset

        Returns:
            Refunds data
        """
        headers = await self._get_headers()
        params = {
            "limit": limit,
            "offset": offset,
        }

        # TODO: Verify actual refunds endpoint
        endpoint = f"/application/shops/{self.shop_id}/refunds"
        return await self.get(endpoint, headers=headers, params=params)

    async def paginate_all(
        self,
        fetch_func: Any,
        batch_size: int = 100,
        max_results: Optional[int] = None,
    ) -> list[dict[str, Any]]:
        """
        Paginate through all results for a given fetch function.

        Args:
            fetch_func: Async function that accepts limit/offset parameters
            batch_size: Results per page
            max_results: Maximum total results to fetch

        Returns:
            List of all results
        """
        all_results = []
        offset = 0

        while True:
            response = await fetch_func(limit=batch_size, offset=offset)

            # Extract results (adjust based on Etsy API response structure)
            results = response.get("results", [])
            all_results.extend(results)

            # Check if we've reached the end or max_results
            if not results or len(results) < batch_size:
                break

            if max_results and len(all_results) >= max_results:
                all_results = all_results[:max_results]
                break

            offset += batch_size

        logger.info(f"Paginated {len(all_results)} total results")
        return all_results
