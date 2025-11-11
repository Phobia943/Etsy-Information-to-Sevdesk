"""
CSV Exporter for sevDesk-compatible data export.

Exports Etsy data as CSV files that can be manually imported into sevDesk.
Designed for users without sevDesk Pro API access (49€/month).

CSV Format:
- UTF-8 with BOM (Excel-compatible)
- Semicolon separator (German Excel)
- Comma as decimal separator
- Date format: DD.MM.YYYY
"""

import codecs
import csv
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.core.logging import get_logger

logger = get_logger(__name__)


class SevDeskCSVExporter:
    """
    Exports Etsy data as sevDesk-compatible CSV files.

    Supports:
    - Invoices (Rechnungen) from orders
    - Credit notes (Gutschriften) from refunds
    - Expense vouchers (Ausgabenbelege) for Etsy fees
    """

    def __init__(self, output_dir: Path):
        """
        Initialize CSV exporter.

        Args:
            output_dir: Directory where CSV files will be saved
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _format_decimal(self, value: Any) -> str:
        """
        Format decimal value for German Excel (comma as decimal separator).

        Args:
            value: Numeric value to format

        Returns:
            Formatted string with comma as decimal separator
        """
        if value is None:
            return "0,00"

        if isinstance(value, str):
            value = Decimal(value)
        elif not isinstance(value, Decimal):
            value = Decimal(str(value))

        # Format with 2 decimals and replace dot with comma
        return f"{value:.2f}".replace(".", ",")

    def _format_date(self, date: datetime) -> str:
        """
        Format date for German format (DD.MM.YYYY).

        Args:
            date: Datetime object to format

        Returns:
            Formatted date string
        """
        if date is None:
            return ""
        return date.strftime("%d.%m.%Y")

    def _write_csv(
        self,
        filename: str,
        headers: List[str],
        rows: List[List[str]]
    ) -> Path:
        """
        Write data to CSV file with German Excel compatibility.

        Args:
            filename: Name of the CSV file
            headers: Column headers
            rows: Data rows

        Returns:
            Path to created CSV file
        """
        filepath = self.output_dir / filename

        # Write with UTF-8 BOM for Excel compatibility
        with codecs.open(filepath, 'w', 'utf-8-sig') as f:
            writer = csv.writer(f, delimiter=';', quoting=csv.QUOTE_MINIMAL)
            writer.writerow(headers)
            writer.writerows(rows)

        logger.info(f"CSV exported: {filepath} ({len(rows)} rows)")
        return filepath

    def export_invoices(self, orders: List[Dict[str, Any]]) -> Path:
        """
        Export orders as invoice CSV.

        CSV columns:
        - Rechnungsnr: Invoice number (generated from Etsy order ID)
        - Datum: Invoice date
        - Faelligkeitsdatum: Due date (same as invoice date)
        - Kundenname: Customer name
        - Kundenland: Customer country code
        - Position: Item description
        - Menge: Quantity
        - Einzelpreis: Unit price (net)
        - Netto: Net amount
        - Steuersatz: Tax rate (%)
        - Steuer: Tax amount
        - Brutto: Gross amount
        - Waehrung: Currency code

        Args:
            orders: List of order dictionaries with order data

        Returns:
            Path to created CSV file
        """
        headers = [
            "Rechnungsnr",
            "Datum",
            "Faelligkeitsdatum",
            "Kundenname",
            "Kundenland",
            "Position",
            "Menge",
            "Einzelpreis",
            "Netto",
            "Steuersatz",
            "Steuer",
            "Brutto",
            "Waehrung"
        ]

        rows = []

        for order in orders:
            # Extract order details
            order_id = order.get("etsy_order_id", order.get("receipt_id", "UNKNOWN"))
            invoice_number = f"R-{order_id}"

            raw_data = order.get("raw_data", {})
            buyer_name = raw_data.get("buyer_user_name", "Etsy Kunde")
            buyer_country = order.get("buyer_country", raw_data.get("country_iso", "DE"))

            # Get date
            order_date = order.get("etsy_created_at")
            if isinstance(order_date, str):
                order_date = datetime.fromisoformat(order_date.replace("Z", "+00:00"))
            elif not isinstance(order_date, datetime):
                order_date = datetime.now()

            date_str = self._format_date(order_date)

            # Get currency
            currency = order.get("currency", "EUR")

            # Get totals
            total_gross = Decimal(str(order.get("total_amount", 0)))
            total_tax = Decimal(str(order.get("tax_amount", 0)))
            total_net = total_gross - total_tax

            # Calculate tax rate
            if total_net > 0:
                tax_rate = (total_tax / total_net * 100).quantize(Decimal("0.1"))
            else:
                tax_rate = Decimal("0")

            # Extract line items if available
            transactions = raw_data.get("transactions", [])

            if transactions:
                # Multiple line items
                for transaction in transactions:
                    item_title = transaction.get("title", "Produkt")
                    quantity = transaction.get("quantity", 1)

                    # Get price info
                    price_data = transaction.get("price", {})
                    if isinstance(price_data, dict):
                        item_gross = Decimal(str(price_data.get("amount", 0))) / Decimal("100")
                        item_divisor = Decimal(str(price_data.get("divisor", 100)))
                        item_gross = item_gross / item_divisor
                    else:
                        item_gross = Decimal(str(price_data))

                    # Calculate item tax
                    item_tax = (item_gross * tax_rate / (Decimal("100") + tax_rate)).quantize(Decimal("0.01"))
                    item_net = item_gross - item_tax
                    item_unit_price = item_net / Decimal(str(quantity))

                    rows.append([
                        invoice_number,
                        date_str,
                        date_str,  # Due date = invoice date
                        buyer_name,
                        buyer_country,
                        item_title,
                        str(quantity),
                        self._format_decimal(item_unit_price),
                        self._format_decimal(item_net),
                        f"{tax_rate}%",
                        self._format_decimal(item_tax),
                        self._format_decimal(item_gross),
                        currency
                    ])

                # Add shipping if present
                shipping_cost = raw_data.get("total_shipping_cost")
                if shipping_cost:
                    if isinstance(shipping_cost, dict):
                        ship_gross = Decimal(str(shipping_cost.get("amount", 0))) / Decimal("100")
                        ship_divisor = Decimal(str(shipping_cost.get("divisor", 100)))
                        ship_gross = ship_gross / ship_divisor
                    else:
                        ship_gross = Decimal(str(shipping_cost))

                    if ship_gross > 0:
                        ship_tax = (ship_gross * tax_rate / (Decimal("100") + tax_rate)).quantize(Decimal("0.01"))
                        ship_net = ship_gross - ship_tax

                        rows.append([
                            invoice_number,
                            date_str,
                            date_str,
                            buyer_name,
                            buyer_country,
                            "Versand",
                            "1",
                            self._format_decimal(ship_net),
                            self._format_decimal(ship_net),
                            f"{tax_rate}%",
                            self._format_decimal(ship_tax),
                            self._format_decimal(ship_gross),
                            currency
                        ])
            else:
                # Single line for entire order
                rows.append([
                    invoice_number,
                    date_str,
                    date_str,
                    buyer_name,
                    buyer_country,
                    "Etsy Bestellung",
                    "1",
                    self._format_decimal(total_net),
                    self._format_decimal(total_net),
                    f"{tax_rate}%",
                    self._format_decimal(total_tax),
                    self._format_decimal(total_gross),
                    currency
                ])

        return self._write_csv("rechnungen.csv", headers, rows)

    def export_credit_notes(self, refunds: List[Dict[str, Any]]) -> Path:
        """
        Export refunds as credit note CSV.

        CSV columns: Same as invoices but with negative amounts

        Args:
            refunds: List of refund dictionaries

        Returns:
            Path to created CSV file
        """
        headers = [
            "Gutschriftsnr",
            "Datum",
            "Rechnungsnr",
            "Kundenname",
            "Kundenland",
            "Position",
            "Menge",
            "Einzelpreis",
            "Netto",
            "Steuersatz",
            "Steuer",
            "Brutto",
            "Waehrung"
        ]

        rows = []

        for refund in refunds:
            refund_id = refund.get("etsy_refund_id", "UNKNOWN")
            credit_number = f"GS-{refund_id}"

            order_id = refund.get("etsy_order_id", "")
            invoice_number = f"R-{order_id}" if order_id else ""

            raw_data = refund.get("raw_data", {})

            # Get date
            refund_date = refund.get("created_at", datetime.now())
            if isinstance(refund_date, str):
                refund_date = datetime.fromisoformat(refund_date.replace("Z", "+00:00"))
            date_str = self._format_date(refund_date)

            # Get amounts (negative for refunds)
            amount = -abs(Decimal(str(refund.get("amount", 0))))
            currency = refund.get("currency", "EUR")

            # Assume 19% tax for refunds (adjust as needed)
            tax_rate = Decimal("19")
            amount_gross = amount
            amount_tax = (amount_gross * tax_rate / (Decimal("100") + tax_rate)).quantize(Decimal("0.01"))
            amount_net = amount_gross - amount_tax

            rows.append([
                credit_number,
                date_str,
                invoice_number,
                "Etsy Kunde",
                "DE",
                "Rückerstattung",
                "1",
                self._format_decimal(amount_net),
                self._format_decimal(amount_net),
                f"{tax_rate}%",
                self._format_decimal(amount_tax),
                self._format_decimal(amount_gross),
                currency
            ])

        return self._write_csv("gutschriften.csv", headers, rows)

    def export_fees(self, fees: List[Dict[str, Any]]) -> Path:
        """
        Export Etsy fees as expense voucher CSV.

        CSV columns:
        - Belegnummer: Voucher number
        - Datum: Fee date
        - Periode: Period (YYYY-MM)
        - Beschreibung: Fee description
        - Typ: Fee type
        - Betrag: Amount (negative = expense)
        - Waehrung: Currency
        - Kategorie: Expense category

        Args:
            fees: List of fee dictionaries

        Returns:
            Path to created CSV file
        """
        headers = [
            "Belegnummer",
            "Datum",
            "Periode",
            "Beschreibung",
            "Typ",
            "Betrag",
            "Waehrung",
            "Kategorie"
        ]

        rows = []

        for fee in fees:
            fee_id = fee.get("id", "")
            period = fee.get("period", datetime.now().strftime("%Y-%m"))
            fee_type = fee.get("fee_type", "Gebühr")

            # Parse period to get date
            try:
                period_date = datetime.strptime(period, "%Y-%m")
                date_str = self._format_date(period_date)
            except:
                date_str = self._format_date(datetime.now())

            # Get amount (negative for expenses)
            amount = -abs(Decimal(str(fee.get("amount", 0))))
            currency = fee.get("currency", "EUR")

            voucher_number = f"GB-{period}-{fee_id}"
            description = f"Etsy {fee_type} {period}"

            rows.append([
                voucher_number,
                date_str,
                period,
                description,
                fee_type,
                self._format_decimal(amount),
                currency,
                "Plattformgebühren"
            ])

        return self._write_csv("gebuehren.csv", headers, rows)

    def create_import_guide(
        self,
        stats: Dict[str, Any],
        timestamp: datetime
    ) -> Path:
        """
        Create import guide markdown file with step-by-step instructions.

        Args:
            stats: Statistics about exported data
            timestamp: Export timestamp

        Returns:
            Path to created guide file
        """
        guide_content = f"""# sevDesk Import-Anleitung

## Export generiert am: {timestamp.strftime("%d.%m.%Y %H:%M:%S")}

Diese Anleitung hilft dir beim manuellen Import der exportierten CSV-Dateien in sevDesk.

---

## Übersicht

Diese CSV-Dateien wurden für dich erstellt:

"""

        if stats.get("invoices_count", 0) > 0:
            guide_content += f"""
### 📄 Rechnungen: `rechnungen.csv`
- **{stats['invoices_count']} Rechnungen** aus Etsy-Bestellungen
- **Gesamtbetrag:** {self._format_decimal(stats.get('invoices_total', 0))} EUR (brutto)
"""

        if stats.get("credit_notes_count", 0) > 0:
            guide_content += f"""
### 📝 Gutschriften: `gutschriften.csv`
- **{stats['credit_notes_count']} Gutschriften** für Rückerstattungen
- **Gesamtbetrag:** {self._format_decimal(stats.get('credit_notes_total', 0))} EUR (brutto)
"""

        if stats.get("fees_count", 0) > 0:
            guide_content += f"""
### 💰 Gebühren: `gebuehren.csv`
- **{stats['fees_count']} Gebührenpositionen** von Etsy
- **Gesamtbetrag:** {self._format_decimal(stats.get('fees_total', 0))} EUR
"""

        guide_content += """

---

## Import-Schritte

### 1. Rechnungen importieren

1. **In sevDesk einloggen**
2. **Navigiere zu:** Verkauf → Rechnungen
3. **Klicke auf:** Import → CSV-Import
4. **Datei auswählen:** `rechnungen.csv`
5. **Felder zuordnen:**
   - Rechnungsnummer → `Rechnungsnr`
   - Datum → `Datum`
   - Fälligkeitsdatum → `Faelligkeitsdatum`
   - Kundenname → `Kundenname`
   - Land → `Kundenland`
   - Position/Artikelname → `Position`
   - Menge → `Menge`
   - Einzelpreis (netto) → `Einzelpreis`
   - Nettobetrag → `Netto`
   - Steuersatz → `Steuersatz`
   - Steuerbetrag → `Steuer`
   - Bruttobetrag → `Brutto`
   - Währung → `Waehrung`
6. **Import starten** und Ergebnis prüfen

**Wichtig:** sevDesk erstellt automatisch Kunden, wenn diese noch nicht existieren.

---

### 2. Gutschriften importieren (optional)

Falls Rückerstattungen vorhanden sind:

1. **Navigiere zu:** Verkauf → Gutschriften
2. **Klicke auf:** Import → CSV-Import
3. **Datei auswählen:** `gutschriften.csv`
4. **Felder zuordnen:** (ähnlich wie Rechnungen)
   - Gutschriftsnummer → `Gutschriftsnr`
   - Zugehörige Rechnung → `Rechnungsnr`
   - Rest analog zu Rechnungen
5. **Import starten**

---

### 3. Gebühren importieren (optional)

Falls Etsy-Gebühren vorhanden sind:

1. **Navigiere zu:** Einkauf → Ausgaben
2. **Klicke auf:** Neu → Ausgabenbeleg
3. **Datei auswählen:** `gebuehren.csv`
4. **Felder zuordnen:**
   - Belegnummer → `Belegnummer`
   - Datum → `Datum`
   - Beschreibung → `Beschreibung`
   - Betrag → `Betrag`
   - Währung → `Waehrung`
   - Kategorie → `Kategorie`
5. **Import starten**

**Tipp:** Lege vorher eine Kategorie "Plattformgebühren" oder "Etsy Gebühren" an.

---

## Häufige Probleme

### Problem: "Ungültiges Datumsformat"
**Lösung:** Stelle sicher, dass sevDesk auf deutsches Format (DD.MM.YYYY) eingestellt ist.

### Problem: "Kundennummer fehlt"
**Lösung:** sevDesk erstellt automatisch neue Kunden. Du kannst die Kundennummern später anpassen.

### Problem: "Währung nicht erkannt"
**Lösung:** Überprüfe, ob die Währungen in sevDesk aktiviert sind (Einstellungen → Währungen).

### Problem: Excel zeigt falsche Zeichen
**Lösung:** Die CSV-Dateien sind UTF-8 mit BOM codiert. Öffne sie direkt in sevDesk, nicht in Excel.

---

## Nach dem Import

Nach erfolgreichem Import:

1. **Prüfe die importierten Rechnungen** auf Vollständigkeit
2. **Kontrolliere die Kundendaten** und ergänze fehlende Adressen
3. **Prüfe die Steuersätze** (bei EU-Kunden OSS-Regelung beachten)
4. **Versende die Rechnungen** an Kunden (falls noch nicht geschehen)
5. **Buche Zahlungseingänge** nach Erhalt

---

## Support

Bei Problemen:

1. **sevDesk Hilfe:** https://hilfe.sevdesk.de
2. **CSV-Format prüfen:** Öffne die CSV in einem Texteditor (nicht Excel!)
3. **Import-Log prüfen:** sevDesk zeigt Fehler beim Import an

---

**Export erstellt mit Etsy-SevDesk-Sync Tool**
https://github.com/yourusername/etsy-sevdesk-sync
"""

        guide_path = self.output_dir / "import_anleitung.md"
        with open(guide_path, "w", encoding="utf-8") as f:
            f.write(guide_content)

        logger.info(f"Import guide created: {guide_path}")
        return guide_path

    def create_summary(
        self,
        stats: Dict[str, Any],
        timestamp: datetime
    ) -> Path:
        """
        Create summary text file with export statistics.

        Args:
            stats: Export statistics
            timestamp: Export timestamp

        Returns:
            Path to created summary file
        """
        summary_content = f"""Etsy-SevDesk CSV Export Summary
{"=" * 50}

Export Timestamp: {timestamp.strftime("%Y-%m-%d %H:%M:%S")}
Export Directory: {self.output_dir.absolute()}

FILES CREATED:
{"=" * 50}

"""

        if stats.get("invoices_count", 0) > 0:
            summary_content += f"""
Rechnungen (rechnungen.csv):
  - Anzahl: {stats['invoices_count']}
  - Gesamt (brutto): {self._format_decimal(stats.get('invoices_total', 0))} EUR
"""

        if stats.get("credit_notes_count", 0) > 0:
            summary_content += f"""
Gutschriften (gutschriften.csv):
  - Anzahl: {stats['credit_notes_count']}
  - Gesamt (brutto): {self._format_decimal(stats.get('credit_notes_total', 0))} EUR
"""

        if stats.get("fees_count", 0) > 0:
            summary_content += f"""
Gebühren (gebuehren.csv):
  - Anzahl: {stats['fees_count']}
  - Gesamt: {self._format_decimal(stats.get('fees_total', 0))} EUR
"""

        summary_content += f"""

NEXT STEPS:
{"=" * 50}

1. Öffne import_anleitung.md für detaillierte Import-Schritte
2. Importiere die CSV-Dateien in sevDesk
3. Prüfe die importierten Daten auf Vollständigkeit

CSV-Format: UTF-8 mit BOM, Semikolon-getrennt, deutsche Zahlen- und Datumsformate
"""

        summary_path = self.output_dir / "summary.txt"
        with open(summary_path, "w", encoding="utf-8") as f:
            f.write(summary_content)

        logger.info(f"Summary created: {summary_path}")
        return summary_path
