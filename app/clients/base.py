"""
Base HTTP client with retry logic, rate limiting, and error handling.
"""

import asyncio
from typing import Any, Optional
from urllib.parse import urljoin

import httpx
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class APIError(Exception):
    """Base exception for API errors."""

    def __init__(self, message: str, status_code: Optional[int] = None, response: Optional[dict] = None):
        super().__init__(message)
        self.status_code = status_code
        self.response = response


class RateLimitError(APIError):
    """Raised when API rate limit is exceeded."""

    pass


class AuthenticationError(APIError):
    """Raised when authentication fails."""

    pass


class BaseAPIClient:
    """
    Base class for API clients with common functionality.

    Features:
    - Automatic retry with exponential backoff
    - Rate limiting
    - Request/response logging
    - Error handling
    """

    def __init__(
        self,
        base_url: str,
        timeout: int = 30,
        rate_limit: int = 10,
    ):
        """
        Initialize API client.

        Args:
            base_url: Base URL for API
            timeout: Request timeout in seconds
            rate_limit: Maximum requests per second
        """
        self.base_url = base_url
        self.timeout = timeout
        self.rate_limit = rate_limit
        self._client: Optional[httpx.AsyncClient] = None
        self._rate_limiter = asyncio.Semaphore(rate_limit)
        self._last_request_time = 0.0

    async def __aenter__(self) -> "BaseAPIClient":
        """Async context manager entry."""
        await self._ensure_client()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.close()

    async def _ensure_client(self) -> None:
        """Ensure HTTP client is initialized."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout),
                follow_redirects=True,
            )

    async def close(self) -> None:
        """Close HTTP client."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def _rate_limit_wait(self) -> None:
        """Apply rate limiting."""
        current_time = asyncio.get_event_loop().time()
        time_since_last = current_time - self._last_request_time
        min_interval = 1.0 / self.rate_limit

        if time_since_last < min_interval:
            await asyncio.sleep(min_interval - time_since_last)

        self._last_request_time = asyncio.get_event_loop().time()

    @retry(
        stop=stop_after_attempt(settings.max_retry_attempts),
        wait=wait_exponential(multiplier=settings.retry_backoff_multiplier, max=settings.retry_max_wait),
        retry=retry_if_exception_type((httpx.NetworkError, httpx.TimeoutException)),
    )
    async def request(
        self,
        method: str,
        endpoint: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        Make HTTP request with retry and error handling.

        Args:
            method: HTTP method
            endpoint: API endpoint
            **kwargs: Additional arguments for httpx.request

        Returns:
            Response JSON data

        Raises:
            APIError: On API error
            RateLimitError: On rate limit exceeded
            AuthenticationError: On authentication failure
        """
        await self._ensure_client()
        await self._rate_limit_wait()

        url = urljoin(self.base_url, endpoint)

        logger.debug(f"{method} {url}", extra={"params": kwargs.get("params")})

        try:
            assert self._client is not None
            response = await self._client.request(method, url, **kwargs)

            # Handle rate limiting
            if response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", 60))
                logger.warning(f"Rate limit exceeded, waiting {retry_after}s")
                await asyncio.sleep(retry_after)
                raise RateLimitError("Rate limit exceeded", status_code=429)

            # Handle authentication errors
            if response.status_code in (401, 403):
                raise AuthenticationError(
                    f"Authentication failed: {response.text}",
                    status_code=response.status_code,
                )

            # Raise for other HTTP errors
            response.raise_for_status()

            # Parse JSON response
            return response.json()

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error: {e.response.status_code} - {e.response.text}")
            raise APIError(
                f"HTTP {e.response.status_code}: {e.response.text}",
                status_code=e.response.status_code,
                response=e.response.json() if e.response.text else None,
            )

        except httpx.RequestError as e:
            logger.error(f"Request error: {e}")
            raise APIError(f"Request failed: {e}")

    async def get(self, endpoint: str, **kwargs: Any) -> dict[str, Any]:
        """Make GET request."""
        return await self.request("GET", endpoint, **kwargs)

    async def post(self, endpoint: str, **kwargs: Any) -> dict[str, Any]:
        """Make POST request."""
        return await self.request("POST", endpoint, **kwargs)

    async def put(self, endpoint: str, **kwargs: Any) -> dict[str, Any]:
        """Make PUT request."""
        return await self.request("PUT", endpoint, **kwargs)

    async def patch(self, endpoint: str, **kwargs: Any) -> dict[str, Any]:
        """Make PATCH request."""
        return await self.request("PATCH", endpoint, **kwargs)

    async def delete(self, endpoint: str, **kwargs: Any) -> dict[str, Any]:
        """Make DELETE request."""
        return await self.request("DELETE", endpoint, **kwargs)
