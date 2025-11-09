"""
Unit tests for currency utilities.
"""

import pytest
from decimal import Decimal

from app.core.currency import (
    round_currency,
    calculate_net_from_gross,
    calculate_gross_from_net,
    calculate_tax_amount,
)


class TestCurrencyRounding:
    """Test currency rounding functions."""

    def test_round_currency_two_decimals(self) -> None:
        """Test rounding to 2 decimal places."""
        assert round_currency(Decimal("10.123")) == Decimal("10.12")
        assert round_currency(Decimal("10.125")) == Decimal("10.13")
        assert round_currency(Decimal("10.999")) == Decimal("11.00")

    def test_round_currency_already_rounded(self) -> None:
        """Test rounding already rounded values."""
        assert round_currency(Decimal("10.00")) == Decimal("10.00")
        assert round_currency(Decimal("10.50")) == Decimal("10.50")


class TestTaxCalculations:
    """Test tax calculation functions."""

    def test_calculate_net_from_gross_19_percent(self) -> None:
        """Test net calculation from gross with 19% tax."""
        gross = Decimal("119.00")
        tax_rate = Decimal("19")
        net = calculate_net_from_gross(gross, tax_rate)

        assert net == Decimal("100.00")

    def test_calculate_net_from_gross_7_percent(self) -> None:
        """Test net calculation from gross with 7% tax."""
        gross = Decimal("107.00")
        tax_rate = Decimal("7")
        net = calculate_net_from_gross(gross, tax_rate)

        assert net == Decimal("100.00")

    def test_calculate_gross_from_net_19_percent(self) -> None:
        """Test gross calculation from net with 19% tax."""
        net = Decimal("100.00")
        tax_rate = Decimal("19")
        gross = calculate_gross_from_net(net, tax_rate)

        assert gross == Decimal("119.00")

    def test_calculate_tax_amount(self) -> None:
        """Test tax amount calculation."""
        net = Decimal("100.00")
        tax_rate = Decimal("19")
        tax = calculate_tax_amount(net, tax_rate)

        assert tax == Decimal("19.00")

    def test_roundtrip_gross_net_gross(self) -> None:
        """Test roundtrip conversion."""
        original_gross = Decimal("119.00")
        tax_rate = Decimal("19")

        net = calculate_net_from_gross(original_gross, tax_rate)
        gross = calculate_gross_from_net(net, tax_rate)

        assert gross == original_gross
