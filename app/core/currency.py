"""
Currency conversion and exchange rate management.

Supports multiple exchange rate providers (ECB, Fixer.io, manual).
Ensures accurate EUR conversions for accounting purposes.
"""

import json
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

import httpx

from app.core.config import settings
from app.core.logging import get_logger
from app.core.time import now

logger = get_logger(__name__)


class ExchangeRateProvider:
    """Base class for exchange rate providers."""

    async def get_rate(self, from_currency: str, to_currency: str, date: Optional[datetime] = None) -> Decimal:
        """
        Get exchange rate from one currency to another.

        Args:
            from_currency: Source currency (ISO 4217)
            to_currency: Target currency (ISO 4217)
            date: Date for historical rate (defaults to today)

        Returns:
            Exchange rate as Decimal

        Raises:
            NotImplementedError: Must be implemented by subclass
        """
        raise NotImplementedError


class ECBProvider(ExchangeRateProvider):
    """
    European Central Bank exchange rate provider.

    Uses ECB's public API for EUR-based exchange rates.
    Free to use, no API key required.
    """

    BASE_URL = "https://www.ecb.europa.eu/stats/eurofxref"
    CACHE_DURATION = timedelta(hours=24)

    def __init__(self) -> None:
        self.cache: dict[str, tuple[datetime, dict[str, Decimal]]] = {}

    async def get_rate(
        self, from_currency: str, to_currency: str, date: Optional[datetime] = None
    ) -> Decimal:
        """Get exchange rate from ECB."""
        # ECB provides rates relative to EUR
        if from_currency == to_currency:
            return Decimal("1.0")

        rates = await self._fetch_rates(date)

        # Convert currencies
        if from_currency == "EUR":
            if to_currency not in rates:
                raise ValueError(f"Currency {to_currency} not supported by ECB")
            return rates[to_currency]

        if to_currency == "EUR":
            if from_currency not in rates:
                raise ValueError(f"Currency {from_currency} not supported by ECB")
            return Decimal("1.0") / rates[from_currency]

        # Convert via EUR: from -> EUR -> to
        if from_currency not in rates or to_currency not in rates:
            raise ValueError(f"Currency pair {from_currency}/{to_currency} not supported by ECB")

        from_eur_rate = rates[from_currency]
        to_eur_rate = rates[to_currency]

        # Rate = (1 / from_eur_rate) * to_eur_rate
        return to_eur_rate / from_eur_rate

    async def _fetch_rates(self, date: Optional[datetime] = None) -> dict[str, Decimal]:
        """Fetch exchange rates from ECB (with caching)."""
        cache_key = "daily" if date is None else date.strftime("%Y-%m-%d")

        # Check cache
        if cache_key in self.cache:
            cached_time, cached_rates = self.cache[cache_key]
            if now() - cached_time < self.CACHE_DURATION:
                return cached_rates

        # Fetch from ECB
        # TODO: Verify exact ECB API endpoint and XML parsing logic
        # Current implementation uses daily rates endpoint
        url = f"{self.BASE_URL}/eurofxref-daily.xml"

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url)
                response.raise_for_status()

                # Parse XML (simplified - in production use proper XML parser)
                # ECB XML format: <Cube currency="USD" rate="1.0823"/>
                rates: dict[str, Decimal] = {}
                import xml.etree.ElementTree as ET

                root = ET.fromstring(response.text)

                # Navigate to Cube elements
                for cube in root.findall(".//{http://www.ecb.int/vocabulary/2002-08-01/eurofxref}Cube[@currency]"):
                    currency = cube.get("currency")
                    rate = cube.get("rate")
                    if currency and rate:
                        rates[currency] = Decimal(rate)

                # Cache the result
                self.cache[cache_key] = (now(), rates)

                logger.info(f"Fetched exchange rates from ECB: {len(rates)} currencies")
                return rates

        except Exception as e:
            logger.error(f"Failed to fetch ECB rates: {e}")
            # Fallback to cache if available
            if cache_key in self.cache:
                logger.warning("Using stale ECB rate cache due to fetch error")
                return self.cache[cache_key][1]
            raise


class FixerProvider(ExchangeRateProvider):
    """
    Fixer.io exchange rate provider.

    Requires API key (paid service).
    """

    BASE_URL = "https://api.fixer.io"

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    async def get_rate(
        self, from_currency: str, to_currency: str, date: Optional[datetime] = None
    ) -> Decimal:
        """Get exchange rate from Fixer.io."""
        if from_currency == to_currency:
            return Decimal("1.0")

        # TODO: Implement Fixer.io API integration
        # For now, raise not implemented
        raise NotImplementedError("Fixer.io provider not yet implemented")


class ManualProvider(ExchangeRateProvider):
    """
    Manual exchange rate provider.

    Uses static rates from configuration.
    Useful for testing or when using fixed rates.
    """

    def __init__(self, rates: dict[str, float]) -> None:
        self.rates = {k: Decimal(str(v)) for k, v in rates.items()}

    async def get_rate(
        self, from_currency: str, to_currency: str, date: Optional[datetime] = None
    ) -> Decimal:
        """Get exchange rate from manual configuration."""
        if from_currency == to_currency:
            return Decimal("1.0")

        # Rates are stored relative to EUR
        if from_currency == "EUR":
            if to_currency not in self.rates:
                raise ValueError(f"Currency {to_currency} not configured in manual rates")
            return self.rates[to_currency]

        if to_currency == "EUR":
            if from_currency not in self.rates:
                raise ValueError(f"Currency {from_currency} not configured in manual rates")
            return Decimal("1.0") / self.rates[from_currency]

        # Convert via EUR
        if from_currency not in self.rates or to_currency not in self.rates:
            raise ValueError(f"Currency pair {from_currency}/{to_currency} not configured")

        return self.rates[to_currency] / self.rates[from_currency]


# Global provider instance
_provider: Optional[ExchangeRateProvider] = None


def get_exchange_rate_provider() -> ExchangeRateProvider:
    """
    Get configured exchange rate provider.

    Returns:
        Exchange rate provider instance
    """
    global _provider

    if _provider is None:
        if settings.exchange_rate_provider == "ecb":
            _provider = ECBProvider()
        elif settings.exchange_rate_provider == "fixer":
            if not settings.fixer_api_key:
                raise ValueError("Fixer API key not configured")
            _provider = FixerProvider(settings.fixer_api_key)
        elif settings.exchange_rate_provider == "manual":
            if not settings.manual_exchange_rates:
                raise ValueError("Manual exchange rates not configured")
            _provider = ManualProvider(settings.manual_exchange_rates)
        else:
            raise ValueError(f"Unknown exchange rate provider: {settings.exchange_rate_provider}")

    return _provider


async def convert_currency(
    amount: Decimal,
    from_currency: str,
    to_currency: str,
    date: Optional[datetime] = None,
) -> Decimal:
    """
    Convert amount from one currency to another.

    Args:
        amount: Amount to convert
        from_currency: Source currency (ISO 4217)
        to_currency: Target currency (ISO 4217)
        date: Date for exchange rate (defaults to today)

    Returns:
        Converted amount rounded to 2 decimals

    Examples:
        >>> await convert_currency(Decimal("100.00"), "USD", "EUR")
        Decimal("92.45")
    """
    if from_currency == to_currency:
        return amount

    provider = get_exchange_rate_provider()
    rate = await provider.get_rate(from_currency, to_currency, date)

    converted = amount * rate
    return converted.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def round_currency(amount: Decimal, decimals: int = 2) -> Decimal:
    """
    Round currency amount to specified decimals (default 2 for EUR).

    Uses ROUND_HALF_UP (commercial rounding).

    Args:
        amount: Amount to round
        decimals: Number of decimal places

    Returns:
        Rounded amount
    """
    if decimals == 2:
        quantize_to = Decimal("0.01")
    elif decimals == 3:
        quantize_to = Decimal("0.001")
    elif decimals == 4:
        quantize_to = Decimal("0.0001")
    else:
        quantize_to = Decimal(10) ** -decimals

    return amount.quantize(quantize_to, rounding=ROUND_HALF_UP)


def format_currency(amount: Decimal, currency: str = "EUR", locale: str = "de_DE") -> str:
    """
    Format currency amount for display.

    Args:
        amount: Amount to format
        currency: Currency code (ISO 4217)
        locale: Locale for formatting

    Returns:
        Formatted currency string (e.g., "1.234,56 €")
    """
    from babel.numbers import format_currency as babel_format_currency

    return babel_format_currency(amount, currency, locale=locale)


def calculate_net_from_gross(gross: Decimal, tax_rate: Decimal) -> Decimal:
    """
    Calculate net amount from gross amount and tax rate.

    Args:
        gross: Gross amount (including tax)
        tax_rate: Tax rate as percentage (e.g., 19 for 19%)

    Returns:
        Net amount (rounded to 2 decimals)

    Examples:
        >>> calculate_net_from_gross(Decimal("119.00"), Decimal("19"))
        Decimal("100.00")
    """
    divisor = Decimal("1") + (tax_rate / Decimal("100"))
    net = gross / divisor
    return round_currency(net)


def calculate_gross_from_net(net: Decimal, tax_rate: Decimal) -> Decimal:
    """
    Calculate gross amount from net amount and tax rate.

    Args:
        net: Net amount (excluding tax)
        tax_rate: Tax rate as percentage (e.g., 19 for 19%)

    Returns:
        Gross amount (rounded to 2 decimals)

    Examples:
        >>> calculate_gross_from_net(Decimal("100.00"), Decimal("19"))
        Decimal("119.00")
    """
    multiplier = Decimal("1") + (tax_rate / Decimal("100"))
    gross = net * multiplier
    return round_currency(gross)


def calculate_tax_amount(net: Decimal, tax_rate: Decimal) -> Decimal:
    """
    Calculate tax amount from net and tax rate.

    Args:
        net: Net amount
        tax_rate: Tax rate as percentage

    Returns:
        Tax amount (rounded to 2 decimals)
    """
    tax = net * (tax_rate / Decimal("100"))
    return round_currency(tax)
