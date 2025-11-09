"""
Idempotency mechanisms for ensuring operations are safely retryable.

Critical for GoBD compliance and avoiding duplicate invoices/payments.
"""

import hashlib
import json
from datetime import datetime, timedelta
from functools import wraps
from typing import Any, Callable, Optional, TypeVar, ParamSpec

from app.core.logging import get_logger
from app.core.time import now

logger = get_logger(__name__)

P = ParamSpec("P")
T = TypeVar("T")


class IdempotencyError(Exception):
    """Raised when idempotency check fails."""

    pass


class IdempotencyStore:
    """
    Storage for idempotency keys and operation results.

    In production, this should use Redis or database storage.
    For now, implements in-memory storage with TTL.
    """

    def __init__(self, ttl_hours: int = 24) -> None:
        """
        Initialize idempotency store.

        Args:
            ttl_hours: Time-to-live for idempotency keys in hours
        """
        self.ttl_hours = ttl_hours
        self._store: dict[str, tuple[datetime, Any]] = {}

    def get(self, key: str) -> Optional[Any]:
        """
        Get result for idempotency key if exists and not expired.

        Args:
            key: Idempotency key

        Returns:
            Stored result or None if not found/expired
        """
        if key not in self._store:
            return None

        stored_time, result = self._store[key]

        # Check if expired
        if now() - stored_time > timedelta(hours=self.ttl_hours):
            del self._store[key]
            return None

        logger.debug(f"Idempotency hit for key: {key[:16]}...")
        return result

    def set(self, key: str, result: Any) -> None:
        """
        Store result for idempotency key.

        Args:
            key: Idempotency key
            result: Operation result to store
        """
        self._store[key] = (now(), result)
        logger.debug(f"Idempotency key stored: {key[:16]}...")

    def delete(self, key: str) -> None:
        """
        Delete idempotency key.

        Args:
            key: Idempotency key to delete
        """
        if key in self._store:
            del self._store[key]

    def cleanup_expired(self) -> int:
        """
        Remove expired keys from store.

        Returns:
            Number of keys removed
        """
        expired_keys = []
        cutoff = now() - timedelta(hours=self.ttl_hours)

        for key, (stored_time, _) in self._store.items():
            if stored_time < cutoff:
                expired_keys.append(key)

        for key in expired_keys:
            del self._store[key]

        if expired_keys:
            logger.info(f"Cleaned up {len(expired_keys)} expired idempotency keys")

        return len(expired_keys)


# Global idempotency store
_idempotency_store = IdempotencyStore()


def get_idempotency_store() -> IdempotencyStore:
    """Get global idempotency store instance."""
    return _idempotency_store


def generate_idempotency_key(prefix: str, *args: Any, **kwargs: Any) -> str:
    """
    Generate idempotency key from function arguments.

    Creates a deterministic hash from arguments.

    Args:
        prefix: Key prefix (e.g., "create_invoice")
        *args: Positional arguments
        **kwargs: Keyword arguments

    Returns:
        Idempotency key (SHA256 hash)

    Examples:
        >>> generate_idempotency_key("create_invoice", order_id=12345)
        "create_invoice:a1b2c3d4..."
    """
    # Create deterministic representation of arguments
    key_data = {
        "prefix": prefix,
        "args": args,
        "kwargs": kwargs,
    }

    # Serialize to JSON (sorted keys for determinism)
    json_str = json.dumps(key_data, sort_keys=True, default=str)

    # Generate hash
    hash_digest = hashlib.sha256(json_str.encode()).hexdigest()

    return f"{prefix}:{hash_digest[:16]}"


def idempotent(
    key_func: Optional[Callable[..., str]] = None,
    prefix: Optional[str] = None,
    ttl_hours: int = 24,
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """
    Decorator to make a function idempotent.

    Stores function results and returns cached result if called again
    with same arguments within TTL period.

    Args:
        key_func: Custom function to generate idempotency key
        prefix: Key prefix (defaults to function name)
        ttl_hours: Time-to-live for idempotency key

    Returns:
        Decorated function

    Examples:
        >>> @idempotent(prefix="create_invoice")
        >>> def create_invoice(order_id: str) -> str:
        ...     # This will only execute once per order_id within 24h
        ...     return "invoice_id"

        >>> @idempotent(key_func=lambda order: f"inv_{order['id']}")
        >>> def process_order(order: dict) -> str:
        ...     return "result"
    """

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            # Generate idempotency key
            if key_func:
                idempotency_key = key_func(*args, **kwargs)
            else:
                key_prefix = prefix or func.__name__
                idempotency_key = generate_idempotency_key(key_prefix, *args, **kwargs)

            # Check for existing result
            store = get_idempotency_store()
            cached_result = store.get(idempotency_key)

            if cached_result is not None:
                logger.info(
                    f"Returning cached result for idempotent operation: {func.__name__}",
                    extra={"idempotency_key": idempotency_key[:32]},
                )
                return cached_result

            # Execute function
            logger.debug(
                f"Executing idempotent operation: {func.__name__}",
                extra={"idempotency_key": idempotency_key[:32]},
            )
            result = func(*args, **kwargs)

            # Store result
            store.set(idempotency_key, result)

            return result

        return wrapper

    return decorator


def ensure_idempotent_api_call(
    endpoint: str,
    payload: dict[str, Any],
    existing_id_field: Optional[str] = None,
) -> Optional[str]:
    """
    Generate idempotent header/key for API calls.

    Many APIs support Idempotency-Key header to prevent duplicate operations.

    Args:
        endpoint: API endpoint being called
        payload: Request payload
        existing_id_field: Field in payload containing existing ID (if any)

    Returns:
        Idempotency key or None if operation is update (not create)

    Examples:
        >>> key = ensure_idempotent_api_call(
        ...     "/invoices",
        ...     {"order_id": "12345", "amount": 100}
        ... )
        >>> headers = {"Idempotency-Key": key}
    """
    # If updating existing resource, don't use idempotency key
    if existing_id_field and payload.get(existing_id_field):
        return None

    # Generate key from endpoint + payload
    key_data = f"{endpoint}:{json.dumps(payload, sort_keys=True)}"
    hash_digest = hashlib.sha256(key_data.encode()).hexdigest()

    return f"etsy-sevdesk:{hash_digest[:32]}"


class IdempotentOperation:
    """
    Context manager for idempotent operations with explicit control.

    Use when decorator is not suitable (e.g., async operations, complex flows).

    Examples:
        >>> with IdempotentOperation("create_invoice", order_id="12345") as op:
        ...     if op.should_execute():
        ...         result = create_invoice_in_sevdesk(order_id)
        ...         op.store_result(result)
        ...     else:
        ...         result = op.get_cached_result()
    """

    def __init__(self, prefix: str, *args: Any, **kwargs: Any) -> None:
        """
        Initialize idempotent operation.

        Args:
            prefix: Operation prefix
            *args: Arguments for key generation
            **kwargs: Keyword arguments for key generation
        """
        self.key = generate_idempotency_key(prefix, *args, **kwargs)
        self.store = get_idempotency_store()
        self.cached_result: Optional[Any] = None

    def __enter__(self) -> "IdempotentOperation":
        """Enter context."""
        self.cached_result = self.store.get(self.key)
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit context."""
        pass

    def should_execute(self) -> bool:
        """
        Check if operation should be executed.

        Returns:
            True if should execute, False if cached result exists
        """
        return self.cached_result is None

    def get_cached_result(self) -> Any:
        """
        Get cached result.

        Returns:
            Cached result

        Raises:
            IdempotencyError: If no cached result exists
        """
        if self.cached_result is None:
            raise IdempotencyError(f"No cached result for key: {self.key}")
        return self.cached_result

    def store_result(self, result: Any) -> None:
        """
        Store operation result.

        Args:
            result: Result to store
        """
        self.store.set(self.key, result)
        self.cached_result = result


def cleanup_expired_keys() -> int:
    """
    Cleanup expired idempotency keys.

    Should be called periodically (e.g., via Celery beat task).

    Returns:
        Number of keys removed
    """
    store = get_idempotency_store()
    return store.cleanup_expired()
