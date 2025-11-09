"""
sevDesk API client for creating invoices, vouchers, and managing payments.

TODO: Verify exact sevDesk API v1 endpoints from official documentation:
https://api.sevdesk.de/
"""

from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from app.clients.base import BaseAPIClient
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class SevdeskClient(BaseAPIClient):
    """
    sevDesk API v1 client.

    Handles invoice/voucher creation, contact management, and document uploads.
    """

    def __init__(self) -> None:
        super().__init__(
            base_url=settings.sevdesk_api_base_url,
            timeout=settings.sevdesk_api_timeout,
            rate_limit=settings.sevdesk_rate_limit,
        )
        self.api_token = settings.sevdesk_api_token

    def _get_headers(self) -> dict[str, str]:
        """Get headers with API token authentication."""
        return {
            "Authorization": self.api_token,
            "Content-Type": "application/json",
        }

    async def get_contact_by_email(self, email: str) -> Optional[dict[str, Any]]:
        """
        Find contact by email address.

        Args:
            email: Customer email

        Returns:
            Contact data or None if not found
        """
        headers = self._get_headers()
        params = {"email": email}

        response = await self.get("/Contact", headers=headers, params=params)

        contacts = response.get("objects", [])
        return contacts[0] if contacts else None

    async def create_contact(self, customer_data: dict[str, Any]) -> dict[str, Any]:
        """
        Create new contact in sevDesk.

        Args:
            customer_data: Customer information

        Returns:
            Created contact data
        """
        headers = self._get_headers()
        payload = {
            "name": customer_data.get("name"),
            "customerNumber": customer_data.get("customer_number"),
            "email": customer_data.get("email"),
            "street": customer_data.get("street"),
            "zip": customer_data.get("zip"),
            "city": customer_data.get("city"),
            "country": {
                "id": customer_data.get("country_id", "1"),  # 1 = Germany
                "objectName": "StaticCountry",
            },
            "category": {
                "id": "3",  # 3 = Customer
                "objectName": "Category",
            },
        }

        response = await self.post("/Contact", headers=headers, json=payload)
        return response.get("objects", {})

    async def create_invoice(
        self,
        contact_id: str,
        positions: list[dict[str, Any]],
        invoice_date: datetime,
        delivery_date: datetime,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        Create invoice in sevDesk.

        sevDesk will generate the invoice number according to configured sequence.

        Args:
            contact_id: sevDesk contact ID
            positions: Invoice line items
            invoice_date: Invoice date
            delivery_date: Delivery date
            **kwargs: Additional invoice parameters

        Returns:
            Created invoice data
        """
        headers = self._get_headers()

        # Build invoice payload
        invoice_payload = {
            "invoice": {
                "invoiceNumber": None,  # sevDesk generates this
                "contact": {
                    "id": contact_id,
                    "objectName": "Contact",
                },
                "invoiceDate": invoice_date.strftime("%Y-%m-%d"),
                "deliveryDate": delivery_date.strftime("%Y-%m-%d"),
                "status": "200",  # 200 = Open
                "invoiceType": "RE",  # RE = Invoice
                "currency": kwargs.get("currency", settings.base_currency),
                "taxType": "default",
                "taxText": kwargs.get("tax_text", "Umsatzsteuer"),
                "taxRate": kwargs.get("tax_rate", settings.default_tax_rate_domestic),
                "header": kwargs.get("header", "Rechnung"),
                "headText": kwargs.get("head_text", ""),
                "footText": kwargs.get("foot_text", ""),
                "paymentMethod": kwargs.get("payment_method"),
            },
            "invoicePosSave": positions,
        }

        if settings.dry_run:
            logger.info("DRY RUN: Would create invoice", extra={"payload": invoice_payload})
            return {"objects": {"id": "dry-run-invoice-id"}}

        response = await self.post("/Invoice/Factory/saveInvoice", headers=headers, json=invoice_payload)
        return response.get("objects", {})

    async def create_voucher(
        self,
        supplier_name: str,
        voucher_date: datetime,
        amount: Decimal,
        positions: list[dict[str, Any]],
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        Create voucher (expense) in sevDesk.

        Used for Etsy fees and charges.

        Args:
            supplier_name: Supplier name (e.g., "Etsy")
            voucher_date: Voucher date
            amount: Total amount
            positions: Voucher line items
            **kwargs: Additional voucher parameters

        Returns:
            Created voucher data
        """
        headers = self._get_headers()

        voucher_payload = {
            "voucher": {
                "voucherDate": voucher_date.strftime("%Y-%m-%d"),
                "supplier": {
                    "name": supplier_name,
                },
                "supplierName": supplier_name,
                "description": kwargs.get("description", ""),
                "payDate": kwargs.get("pay_date", voucher_date).strftime("%Y-%m-%d"),
                "status": "100",  # 100 = Paid
                "taxType": "default",
                "currency": kwargs.get("currency", settings.base_currency),
                "voucherType": "VOU",  # VOU = Voucher
            },
            "voucherPosSave": positions,
        }

        if settings.dry_run:
            logger.info("DRY RUN: Would create voucher", extra={"payload": voucher_payload})
            return {"objects": {"id": "dry-run-voucher-id"}}

        response = await self.post("/Voucher/Factory/saveVoucher", headers=headers, json=voucher_payload)
        return response.get("objects", {})

    async def upload_document(
        self,
        object_type: str,
        object_id: str,
        file_content: bytes,
        filename: str,
    ) -> dict[str, Any]:
        """
        Upload document to sevDesk object (invoice, voucher, etc.).

        Args:
            object_type: Object type (Invoice, Voucher, etc.)
            object_id: Object ID
            file_content: File content as bytes
            filename: Filename

        Returns:
            Upload response
        """
        headers = {
            "Authorization": self.api_token,
        }

        files = {
            "file": (filename, file_content),
        }

        data = {
            "object": f'{{"id": "{object_id}", "objectName": "{object_type}"}}',
        }

        if settings.dry_run:
            logger.info(f"DRY RUN: Would upload document {filename} to {object_type}/{object_id}")
            return {"objects": {"id": "dry-run-document-id"}}

        # TODO: Verify exact document upload endpoint
        endpoint = "/Document"
        response = await self.post(endpoint, headers=headers, files=files, data=data)
        return response.get("objects", {})

    async def book_invoice(self, invoice_id: str, book_date: Optional[datetime] = None) -> dict[str, Any]:
        """
        Book (finalize) an invoice in sevDesk.

        This generates the final invoice number and makes it immutable.

        Args:
            invoice_id: sevDesk invoice ID
            book_date: Booking date (defaults to today)

        Returns:
            Booking response
        """
        headers = self._get_headers()

        if book_date is None:
            from app.core.time import now
            book_date = now()

        payload = {
            "id": invoice_id,
            "date": book_date.strftime("%Y-%m-%d"),
        }

        if settings.dry_run:
            logger.info(f"DRY RUN: Would book invoice {invoice_id}")
            return {"objects": {"invoiceNumber": "DRY-2025-0001"}}

        response = await self.put(f"/Invoice/{invoice_id}/bookAmount", headers=headers, json=payload)
        return response.get("objects", {})

    async def create_invoice_payment(
        self,
        invoice_id: str,
        amount: Decimal,
        payment_date: datetime,
    ) -> dict[str, Any]:
        """
        Record payment for an invoice.

        Args:
            invoice_id: sevDesk invoice ID
            amount: Payment amount
            payment_date: Payment date

        Returns:
            Payment response
        """
        headers = self._get_headers()

        payload = {
            "invoice": {
                "id": invoice_id,
                "objectName": "Invoice",
            },
            "amount": str(amount),
            "paymentDate": payment_date.strftime("%Y-%m-%d"),
        }

        if settings.dry_run:
            logger.info(f"DRY RUN: Would create payment for invoice {invoice_id}: {amount}")
            return {"objects": {"id": "dry-run-payment-id"}}

        response = await self.post("/InvoicePayment", headers=headers, json=payload)
        return response.get("objects", {})
