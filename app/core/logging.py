"""
Structured logging configuration with JSON output and PII masking.

Provides GoBD-compliant logging with audit trail capabilities.
"""

import logging
import re
import sys
from typing import Any

from pythonjsonlogger import jsonlogger

from app.core.config import settings


class PIIMaskingFormatter(jsonlogger.JsonFormatter):
    """
    JSON formatter with PII (Personally Identifiable Information) masking.

    Masks email addresses and other sensitive data in log messages if configured.
    """

    EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")
    CREDIT_CARD_PATTERN = re.compile(r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b")

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.mask_pii = settings.mask_customer_data_in_logs
        super().__init__(*args, **kwargs)

    def format(self, record: logging.LogRecord) -> str:
        """Format log record with PII masking if enabled."""
        if self.mask_pii and hasattr(record, "msg"):
            record.msg = self._mask_sensitive_data(str(record.msg))

            # Also mask in extra fields
            if hasattr(record, "__dict__"):
                for key, value in record.__dict__.items():
                    if isinstance(value, str):
                        record.__dict__[key] = self._mask_sensitive_data(value)

        return super().format(record)

    def _mask_sensitive_data(self, text: str) -> str:
        """Mask sensitive data patterns in text."""
        # Mask email addresses
        text = self.EMAIL_PATTERN.sub(lambda m: self._mask_email(m.group(0)), text)

        # Mask credit card numbers
        text = self.CREDIT_CARD_PATTERN.sub("****-****-****-****", text)

        return text

    @staticmethod
    def _mask_email(email: str) -> str:
        """Mask email address keeping first 2 chars and domain."""
        parts = email.split("@")
        if len(parts) == 2:
            username, domain = parts
            if len(username) > 2:
                masked_username = username[:2] + "*" * (len(username) - 2)
            else:
                masked_username = "*" * len(username)
            return f"{masked_username}@{domain}"
        return "***@***.***"


class TextFormatter(logging.Formatter):
    """
    Simple text formatter for development/console output.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.mask_pii = settings.mask_customer_data_in_logs
        super().__init__(*args, **kwargs)

    def format(self, record: logging.LogRecord) -> str:
        """Format log record with optional PII masking."""
        if self.mask_pii and hasattr(record, "msg"):
            pii_formatter = PIIMaskingFormatter()
            record.msg = pii_formatter._mask_sensitive_data(str(record.msg))

        return super().format(record)


def setup_logging() -> None:
    """
    Configure application-wide logging.

    Sets up structured JSON logging for production or text logging for development.
    Respects LOG_LEVEL and LOG_FORMAT from settings.
    """
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)

    # Root logger configuration
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)

    # Choose formatter based on settings
    if settings.log_format == "json":
        formatter = PIIMaskingFormatter(
            fmt="%(asctime)s %(name)s %(levelname)s %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    else:
        formatter = TextFormatter(
            fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # Reduce noise from third-party libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

    # In development, show SQL queries
    if settings.is_development and settings.debug:
        logging.getLogger("sqlalchemy.engine").setLevel(logging.INFO)

    root_logger.info(
        "Logging configured",
        extra={
            "log_level": settings.log_level,
            "log_format": settings.log_format,
            "environment": settings.app_env,
        },
    )


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for a specific module.

    Args:
        name: Logger name (usually __name__)

    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)


# Audit logging helper
class AuditLogger:
    """
    Specialized logger for GoBD-compliant audit trails.

    Logs all financial transactions and changes with full context.
    """

    def __init__(self, logger_name: str = "audit") -> None:
        self.logger = logging.getLogger(logger_name)

    def log_invoice_created(
        self,
        etsy_order_id: str,
        sevdesk_invoice_id: str,
        amount: float,
        currency: str,
        **kwargs: Any,
    ) -> None:
        """Log invoice creation."""
        self.logger.info(
            "Invoice created",
            extra={
                "event": "invoice_created",
                "etsy_order_id": etsy_order_id,
                "sevdesk_invoice_id": sevdesk_invoice_id,
                "amount": amount,
                "currency": currency,
                **kwargs,
            },
        )

    def log_refund_processed(
        self,
        etsy_refund_id: str,
        sevdesk_credit_id: str,
        amount: float,
        currency: str,
        **kwargs: Any,
    ) -> None:
        """Log refund processing."""
        self.logger.info(
            "Refund processed",
            extra={
                "event": "refund_processed",
                "etsy_refund_id": etsy_refund_id,
                "sevdesk_credit_id": sevdesk_credit_id,
                "amount": amount,
                "currency": currency,
                **kwargs,
            },
        )

    def log_payout_received(
        self,
        etsy_payout_id: str,
        amount: float,
        currency: str,
        **kwargs: Any,
    ) -> None:
        """Log payout received."""
        self.logger.info(
            "Payout received",
            extra={
                "event": "payout_received",
                "etsy_payout_id": etsy_payout_id,
                "amount": amount,
                "currency": currency,
                **kwargs,
            },
        )

    def log_fee_voucher_created(
        self,
        period: str,
        amount: float,
        currency: str,
        voucher_id: str,
        **kwargs: Any,
    ) -> None:
        """Log fee voucher creation."""
        self.logger.info(
            "Fee voucher created",
            extra={
                "event": "fee_voucher_created",
                "period": period,
                "amount": amount,
                "currency": currency,
                "voucher_id": voucher_id,
                **kwargs,
            },
        )

    def log_error(self, event: str, error: Exception, **kwargs: Any) -> None:
        """Log error with context."""
        self.logger.error(
            f"Error in {event}",
            extra={
                "event": event,
                "error_type": type(error).__name__,
                "error_message": str(error),
                **kwargs,
            },
            exc_info=True,
        )


# Global audit logger instance
audit_logger = AuditLogger()
