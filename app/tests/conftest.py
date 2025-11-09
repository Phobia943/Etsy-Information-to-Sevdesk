"""
Pytest configuration and fixtures.
"""

import pytest
from decimal import Decimal
from datetime import datetime

from app.core.config import settings


@pytest.fixture
def sample_order_data() -> dict:
    """Sample Etsy order data for testing."""
    return {
        "receipt_id": "12345678",
        "order_id": "12345678",
        "buyer_email": "customer@example.com",
        "name": "John Doe",
        "first_line": "123 Main St",
        "city": "Berlin",
        "zip": "10115",
        "country_iso": "DE",
        "grandtotal": {"amount": 119, "divisor": 100, "currency_code": "EUR"},
        "total_price": {"amount": 119, "divisor": 100, "currency_code": "EUR"},
        "total_tax_cost": {"amount": 19, "divisor": 100, "currency_code": "EUR"},
        "created_timestamp": 1704067200,  # 2024-01-01 00:00:00 UTC
        "updated_timestamp": 1704067200,
        "was_paid": True,
        "transactions": [
            {
                "transaction_id": "987654321",
                "title": "Handmade Product",
                "quantity": 1,
                "price": {"amount": 100, "divisor": 100, "currency_code": "EUR"},
                "listing_id": "111222333",
            }
        ],
    }


@pytest.fixture
def sample_customer_data() -> dict:
    """Sample customer data for testing."""
    return {
        "name": "John Doe",
        "email": "customer@example.com",
        "street": "123 Main St",
        "city": "Berlin",
        "zip": "10115",
        "country_code": "DE",
    }


@pytest.fixture
def sample_tax_config() -> dict:
    """Sample tax configuration."""
    return {
        "domestic": {
            "country": "DE",
            "rules": [
                {
                    "name": "Regelsteuersatz",
                    "rate": 19.0,
                    "code": "19",
                    "sevdesk_tax_id": "1",
                }
            ],
        },
        "oss": {
            "enabled": True,
            "countries": {
                "AT": {"name": "Österreich", "rate": 20.0, "sevdesk_tax_id": "2"},
                "FR": {"name": "Frankreich", "rate": 20.0, "sevdesk_tax_id": "3"},
            },
        },
    }


@pytest.fixture
def dry_run_enabled(monkeypatch) -> None:
    """Enable dry-run mode for tests."""
    monkeypatch.setattr(settings, "dry_run", True)
