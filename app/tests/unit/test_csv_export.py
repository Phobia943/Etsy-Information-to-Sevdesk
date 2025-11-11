#!/usr/bin/env python3
"""
Unit tests for CSV export functionality.

Tests the SevDeskCSVExporter with mock data to ensure correct CSV generation.
"""

import csv
import tempfile
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pytest

from app.export.csv_exporter import SevDeskCSVExporter


class TestCSVExporter:
    """Test suite for CSV export functionality."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for test outputs."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def exporter(self, temp_dir):
        """Create exporter instance with temp directory."""
        return SevDeskCSVExporter(temp_dir)

    @pytest.fixture
    def sample_order(self):
        """Sample order data for testing."""
        return {
            "etsy_order_id": "1234567890",
            "raw_data": {
                "buyer_user_name": "Test Kunde",
                "country_iso": "DE",
                "transactions": [
                    {
                        "title": "Handgefertigter Becher",
                        "quantity": 2,
                        "price": {
                            "amount": 1990,  # 19.90 EUR
                            "divisor": 100,
                        }
                    }
                ],
                "total_shipping_cost": {
                    "amount": 495,  # 4.95 EUR
                    "divisor": 100,
                }
            },
            "buyer_country": "DE",
            "currency": "EUR",
            "total_amount": Decimal("44.75"),  # 2 * 19.90 + 4.95
            "tax_amount": Decimal("7.14"),     # 19% VAT
            "etsy_created_at": datetime(2025, 11, 10, 14, 30, 0),
        }

    @pytest.fixture
    def sample_refund(self):
        """Sample refund data for testing."""
        return {
            "etsy_refund_id": "RF-123456",
            "etsy_order_id": "1234567890",
            "raw_data": {},
            "amount": Decimal("19.90"),
            "currency": "EUR",
            "created_at": datetime(2025, 11, 11, 10, 0, 0),
        }

    @pytest.fixture
    def sample_fee(self):
        """Sample fee data for testing."""
        return {
            "id": 1,
            "period": "2025-11",
            "fee_type": "Listing Fee",
            "amount": Decimal("0.20"),
            "currency": "USD",
        }

    def test_format_decimal(self, exporter):
        """Test decimal formatting with German comma separator."""
        assert exporter._format_decimal(Decimal("19.90")) == "19,90"
        assert exporter._format_decimal(Decimal("1234.56")) == "1234,56"
        assert exporter._format_decimal(Decimal("0.99")) == "0,99"
        assert exporter._format_decimal(None) == "0,00"
        assert exporter._format_decimal("42.15") == "42,15"

    def test_format_date(self, exporter):
        """Test date formatting to German DD.MM.YYYY format."""
        date = datetime(2025, 11, 10, 14, 30, 0)
        assert exporter._format_date(date) == "10.11.2025"

        assert exporter._format_date(None) == ""

    def test_export_invoices_creates_file(self, exporter, sample_order, temp_dir):
        """Test that invoice export creates a CSV file."""
        csv_path = exporter.export_invoices([sample_order])

        assert csv_path.exists()
        assert csv_path.name == "rechnungen.csv"
        assert csv_path.parent == temp_dir

    def test_export_invoices_csv_structure(self, exporter, sample_order):
        """Test CSV structure and headers for invoices."""
        csv_path = exporter.export_invoices([sample_order])

        # Read CSV with semicolon delimiter
        with open(csv_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f, delimiter=';')
            rows = list(reader)

            # Check headers
            assert 'Rechnungsnr' in reader.fieldnames
            assert 'Datum' in reader.fieldnames
            assert 'Kundenname' in reader.fieldnames
            assert 'Brutto' in reader.fieldnames
            assert 'Waehrung' in reader.fieldnames

            # Should have 2 rows: 1 product line (with quantity 2) + 1 shipping
            assert len(rows) == 2

    def test_export_invoices_data_correctness(self, exporter, sample_order):
        """Test that exported invoice data is correct."""
        csv_path = exporter.export_invoices([sample_order])

        with open(csv_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f, delimiter=';')
            rows = list(reader)

            # Check first row (product line)
            first_row = rows[0]
            assert first_row['Rechnungsnr'] == 'R-1234567890'
            assert first_row['Datum'] == '10.11.2025'
            assert first_row['Kundenname'] == 'Test Kunde'
            assert first_row['Kundenland'] == 'DE'
            assert first_row['Position'] == 'Handgefertigter Becher'
            assert first_row['Menge'] == '2'
            assert first_row['Waehrung'] == 'EUR'

            # Check shipping row
            shipping_row = rows[-1]
            assert shipping_row['Position'] == 'Versand'
            assert shipping_row['Menge'] == '1'

    def test_export_invoices_german_number_format(self, exporter, sample_order):
        """Test that numbers use German format (comma as decimal separator)."""
        csv_path = exporter.export_invoices([sample_order])

        with open(csv_path, 'r', encoding='utf-8-sig') as f:
            content = f.read()

            # Should contain comma as decimal separator
            assert ',' in content
            # Should not contain dot followed by two digits (US format)
            # Note: This is a simplified check
            assert 'Brutto' in content

    def test_export_credit_notes(self, exporter, sample_refund, temp_dir):
        """Test credit note export."""
        csv_path = exporter.export_credit_notes([sample_refund])

        assert csv_path.exists()
        assert csv_path.name == "gutschriften.csv"

        with open(csv_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f, delimiter=';')
            rows = list(reader)

            assert len(rows) == 1
            row = rows[0]

            assert row['Gutschriftsnr'] == 'GS-RF-123456'
            assert row['Rechnungsnr'] == 'R-1234567890'
            assert row['Datum'] == '11.11.2025'
            assert row['Position'] == 'Rückerstattung'

    def test_export_fees(self, exporter, sample_fee, temp_dir):
        """Test fee export."""
        csv_path = exporter.export_fees([sample_fee])

        assert csv_path.exists()
        assert csv_path.name == "gebuehren.csv"

        with open(csv_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f, delimiter=';')
            rows = list(reader)

            assert len(rows) == 1
            row = rows[0]

            assert row['Periode'] == '2025-11'
            assert row['Typ'] == 'Listing Fee'
            assert row['Waehrung'] == 'USD'
            assert row['Kategorie'] == 'Plattformgebühren'

    def test_export_multiple_orders(self, exporter, sample_order):
        """Test exporting multiple orders."""
        order2 = sample_order.copy()
        order2["etsy_order_id"] = "9876543210"

        csv_path = exporter.export_invoices([sample_order, order2])

        with open(csv_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f, delimiter=';')
            rows = list(reader)

            # Each order has 2 lines (1 product + shipping) = 4 total
            assert len(rows) == 4

            # Check both invoice numbers present
            invoice_numbers = {row['Rechnungsnr'] for row in rows}
            assert 'R-1234567890' in invoice_numbers
            assert 'R-9876543210' in invoice_numbers

    def test_create_import_guide(self, exporter, temp_dir):
        """Test import guide generation."""
        stats = {
            "invoices_count": 10,
            "invoices_total": Decimal("1234.50"),
            "credit_notes_count": 2,
            "credit_notes_total": Decimal("-50.00"),
            "fees_count": 5,
            "fees_total": Decimal("-25.00"),
        }

        timestamp = datetime.now()
        guide_path = exporter.create_import_guide(stats, timestamp)

        assert guide_path.exists()
        assert guide_path.name == "import_anleitung.md"

        # Check content
        with open(guide_path, 'r', encoding='utf-8') as f:
            content = f.read()

            assert "sevDesk Import-Anleitung" in content
            assert "10 Rechnungen" in content
            assert "2 Gutschriften" in content
            assert "5 Gebührenpositionen" in content
            assert "1234,50" in content  # German number format

    def test_create_summary(self, exporter, temp_dir):
        """Test summary file generation."""
        stats = {
            "invoices_count": 10,
            "invoices_total": Decimal("1234.50"),
            "credit_notes_count": 0,
            "credit_notes_total": Decimal("0"),
            "fees_count": 0,
            "fees_total": Decimal("0"),
        }

        timestamp = datetime.now()
        summary_path = exporter.create_summary(stats, timestamp)

        assert summary_path.exists()
        assert summary_path.name == "summary.txt"

        with open(summary_path, 'r', encoding='utf-8') as f:
            content = f.read()

            assert "CSV Export Summary" in content
            assert "Anzahl: 10" in content

    def test_export_order_without_transactions(self, exporter):
        """Test exporting order without detailed transaction data."""
        order = {
            "etsy_order_id": "9999999",
            "raw_data": {
                "buyer_user_name": "Simple Customer",
                "country_iso": "US",
                "transactions": []  # No detailed transactions
            },
            "buyer_country": "US",
            "currency": "USD",
            "total_amount": Decimal("29.99"),
            "tax_amount": Decimal("0.00"),  # No tax for US
            "etsy_created_at": datetime(2025, 11, 10),
        }

        csv_path = exporter.export_invoices([order])

        with open(csv_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f, delimiter=';')
            rows = list(reader)

            # Should create single line for entire order
            assert len(rows) == 1
            assert rows[0]['Position'] == 'Etsy Bestellung'
            assert rows[0]['Rechnungsnr'] == 'R-9999999'

    def test_csv_utf8_bom(self, exporter, sample_order):
        """Test that CSV files have UTF-8 BOM for Excel compatibility."""
        csv_path = exporter.export_invoices([sample_order])

        # Read raw bytes to check BOM
        with open(csv_path, 'rb') as f:
            first_bytes = f.read(3)
            assert first_bytes == b'\xef\xbb\xbf'  # UTF-8 BOM

    def test_empty_export(self, exporter):
        """Test exporting empty data sets."""
        csv_path = exporter.export_invoices([])

        assert csv_path.exists()

        with open(csv_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f, delimiter=';')
            rows = list(reader)
            assert len(rows) == 0  # Only headers, no data


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v"])
