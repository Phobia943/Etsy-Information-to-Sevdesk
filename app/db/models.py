"""
Database models for Etsy-sevDesk synchronization.

All models use SQLAlchemy 2.0 declarative base with type hints.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import String, Integer, Boolean, DateTime, Text, Numeric, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class IntegrationState(Base):
    """
    Key-value store for integration state (last sync timestamps, etc.).
    """

    __tablename__ = "integration_state"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class Order(Base, TimestampMixin):
    """
    Etsy orders (receipts).

    Stores raw Etsy order data and mapping to sevDesk invoice.
    """

    __tablename__ = "orders"

    etsy_order_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    raw_data: Mapped[dict] = mapped_column(JSONB, nullable=False, comment="Raw Etsy API response")
    status: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    buyer_country: Mapped[str] = mapped_column(String(2), nullable=False, index=True)
    buyer_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    total_amount: Mapped[Numeric] = mapped_column(Numeric(10, 2), nullable=False)
    tax_amount: Mapped[Numeric] = mapped_column(Numeric(10, 2), nullable=False)
    etsy_created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    etsy_updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)

    __table_args__ = (
        Index("idx_orders_created", "etsy_created_at"),
        Index("idx_orders_status_created", "status", "etsy_created_at"),
    )


class Invoice(Base, TimestampMixin):
    """
    Mapping between Etsy orders and sevDesk invoices.
    """

    __tablename__ = "invoices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    etsy_order_id: Mapped[str] = mapped_column(
        String(100), nullable=False, unique=True, index=True
    )
    sevdesk_invoice_id: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    sevdesk_invoice_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    state: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    total_net: Mapped[Numeric] = mapped_column(Numeric(10, 2), nullable=False)
    total_gross: Mapped[Numeric] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    invoice_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class Refund(Base, TimestampMixin):
    """
    Etsy refunds and their sevDesk credit notes.
    """

    __tablename__ = "refunds"

    etsy_refund_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    etsy_order_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    raw_data: Mapped[dict] = mapped_column(JSONB, nullable=False)
    sevdesk_credit_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    amount: Mapped[Numeric] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)


class Payout(Base, TimestampMixin):
    """
    Etsy payouts (bank transfers).
    """

    __tablename__ = "payouts"

    etsy_payout_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    raw_data: Mapped[dict] = mapped_column(JSONB, nullable=False)
    amount: Mapped[Numeric] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    period_start: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    payout_date: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    sevdesk_payment_batch_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)


class Fee(Base, TimestampMixin):
    """
    Etsy fees and charges (monthly aggregated).
    """

    __tablename__ = "fees"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    period: Mapped[str] = mapped_column(String(7), nullable=False, index=True, comment="YYYY-MM")
    fee_type: Mapped[str] = mapped_column(String(50), nullable=False)
    amount: Mapped[Numeric] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    document_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    sevdesk_voucher_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)


class Customer(Base, TimestampMixin):
    """
    Customer data with sevDesk contact mapping.

    Email is hashed if HASH_CUSTOMER_EMAILS is enabled.
    """

    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    sevdesk_contact_id: Mapped[str] = mapped_column(String(100), nullable=False)
    last_order_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class AuditLog(Base):
    """
    Audit trail for all operations (GoBD compliance).

    Logs all creates/updates/deletes with full context.
    """

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, index=True, comment="Operation timestamp"
    )
    event: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(100), nullable=False)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    metadata: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    user: Mapped[str] = mapped_column(String(100), nullable=False, default="system")

    __table_args__ = (
        Index("idx_audit_timestamp", "timestamp"),
        Index("idx_audit_entity", "entity_type", "entity_id"),
    )
