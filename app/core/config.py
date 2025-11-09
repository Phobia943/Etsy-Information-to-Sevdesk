"""
Configuration management using Pydantic Settings.

Loads configuration from environment variables with validation and type safety.
"""

import json
from pathlib import Path
from typing import Any, Literal, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.

    All settings are loaded from .env file or environment variables.
    See .env.example for all available options.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = Field(default="etsy-sevdesk-sync", description="Application name")
    app_env: Literal["development", "staging", "production"] = Field(
        default="production", description="Environment"
    )
    log_level: str = Field(default="INFO", description="Logging level")
    log_format: Literal["json", "text"] = Field(default="json", description="Log format")
    timezone: str = Field(default="Europe/Berlin", description="Timezone")
    base_currency: str = Field(default="EUR", description="Base currency ISO 4217")
    debug: bool = Field(default=False, description="Debug mode")

    # Database
    database_url: str = Field(
        default="sqlite:///./data/etsy_sevdesk.db",
        description="Database connection URL",
    )
    db_pool_size: int = Field(default=5, description="Database connection pool size")
    db_max_overflow: int = Field(default=10, description="Database max overflow connections")
    db_pool_timeout: int = Field(default=30, description="Database pool timeout in seconds")
    db_pool_recycle: int = Field(default=3600, description="Database pool recycle time")

    # Redis/Celery
    redis_url: str = Field(default="redis://localhost:6379/0", description="Redis URL")
    celery_broker_url: str = Field(
        default="redis://localhost:6379/0", description="Celery broker URL"
    )
    celery_result_backend: str = Field(
        default="redis://localhost:6379/0", description="Celery result backend"
    )

    # Etsy API
    etsy_client_id: str = Field(default="", description="Etsy OAuth2 Client ID")
    etsy_client_secret: str = Field(default="", description="Etsy OAuth2 Client Secret")
    etsy_refresh_token: str = Field(default="", description="Etsy OAuth2 Refresh Token")
    etsy_shop_id: str = Field(default="", description="Etsy Shop ID")
    etsy_api_base_url: str = Field(
        default="https://openapi.etsy.com/v3", description="Etsy API base URL"
    )
    etsy_api_timeout: int = Field(default=30, description="Etsy API timeout in seconds")
    etsy_rate_limit: int = Field(
        default=10, description="Etsy API rate limit (requests per second)"
    )

    # sevDesk API
    sevdesk_api_token: str = Field(default="", description="sevDesk API token")
    sevdesk_api_base_url: str = Field(
        default="https://my.sevdesk.de/api/v1", description="sevDesk API base URL"
    )
    sevdesk_api_timeout: int = Field(default=30, description="sevDesk API timeout in seconds")
    sevdesk_rate_limit: int = Field(
        default=5, description="sevDesk API rate limit (requests per second)"
    )

    # Accounting
    account_chart: Literal["SKR03", "SKR04"] = Field(
        default="SKR03", description="Chart of accounts"
    )
    account_mapping_path: str = Field(
        default="./config/account_mapping_skr03.json",
        description="Path to account mapping file",
    )
    tax_rules_path: str = Field(
        default="./config/tax_rules.json", description="Path to tax rules file"
    )
    kleinunternehmer: bool = Field(
        default=False, description="Kleinunternehmer regulation (no VAT)"
    )
    default_payment_terms: int = Field(
        default=14, description="Default payment terms in days"
    )
    default_tax_rate_domestic: int = Field(
        default=19, description="Default domestic tax rate"
    )
    enable_oss: bool = Field(
        default=True, description="Enable OSS for EU cross-border sales"
    )

    # Features
    feature_use_webhooks: bool = Field(default=False, description="Enable Etsy webhooks")
    feature_apply_payout_payments: bool = Field(
        default=False, description="Auto-apply payout payments via API"
    )
    feature_auto_process_refunds: bool = Field(
        default=True, description="Auto-process refunds as credit notes"
    )
    feature_auto_process_fees: bool = Field(
        default=True, description="Auto-process fee vouchers"
    )
    dry_run: bool = Field(default=False, description="Dry-run mode (no sevDesk writes)")

    # Currency Exchange
    exchange_rate_provider: Literal["ecb", "fixer", "manual"] = Field(
        default="ecb", description="Exchange rate provider"
    )
    fixer_api_key: Optional[str] = Field(default=None, description="Fixer.io API key")
    manual_exchange_rates: Optional[str] = Field(
        default=None, description="Manual exchange rates JSON"
    )

    # Encryption
    encryption_key: str = Field(
        default="",
        description="AES encryption key for sensitive data (base64)",
    )

    # Sync
    initial_sync_start_date: Optional[str] = Field(
        default="2024-01-01", description="Initial sync start date (ISO format)"
    )
    initial_sync_days_back: Optional[int] = Field(
        default=None, description="Initial sync days back"
    )
    sync_interval_minutes: int = Field(default=15, description="Sync interval in minutes")
    sync_batch_size: int = Field(default=100, description="Batch size for API requests")
    max_retry_attempts: int = Field(default=3, description="Max retry attempts")
    retry_backoff_multiplier: int = Field(default=2, description="Retry backoff multiplier")
    retry_max_wait: int = Field(default=300, description="Retry max wait in seconds")

    # Webhooks
    etsy_webhook_secret: str = Field(default="", description="Etsy webhook secret")
    public_base_url: str = Field(
        default="https://your-domain.com", description="Public base URL for webhooks"
    )

    # Storage
    storage_path: str = Field(default="./storage", description="Storage directory path")
    document_retention_days: int = Field(
        default=3650, description="Document retention in days (GoBD: 10 years)"
    )

    # GDPR/Privacy
    mask_customer_data_in_logs: bool = Field(
        default=True, description="Mask customer data in logs"
    )
    hash_customer_emails: bool = Field(default=False, description="Hash customer emails in DB")
    audit_log_retention_days: int = Field(
        default=3650, description="Audit log retention in days (GoBD: 10 years)"
    )

    # Monitoring
    enable_otel: bool = Field(default=False, description="Enable OpenTelemetry")
    otel_exporter_otlp_endpoint: Optional[str] = Field(
        default=None, description="OTEL endpoint"
    )
    sentry_dsn: Optional[str] = Field(default=None, description="Sentry DSN")
    enable_health_check: bool = Field(default=True, description="Enable health check endpoint")

    # API Server
    api_host: str = Field(default="0.0.0.0", description="API server host")
    api_port: int = Field(default=8000, description="API server port")
    api_workers: int = Field(default=4, description="API worker processes")
    enable_api_docs: bool = Field(default=True, description="Enable API documentation")
    api_rate_limit: int = Field(
        default=60, description="API rate limit (requests per minute per IP)"
    )

    # Celery Worker
    celery_worker_concurrency: int = Field(default=4, description="Celery worker concurrency")
    celery_worker_loglevel: str = Field(default="INFO", description="Celery worker log level")
    celery_task_time_limit: int = Field(
        default=600, description="Celery task time limit in seconds"
    )
    celery_task_soft_time_limit: int = Field(
        default=540, description="Celery task soft time limit in seconds"
    )

    # Security
    allowed_origins: str = Field(
        default="http://localhost:3000,http://localhost:8000",
        description="Allowed CORS origins (comma-separated)",
    )
    secret_key: str = Field(
        default="change-me-in-production-min-32-chars",
        description="Secret key for sessions/JWT",
    )
    force_https: bool = Field(default=False, description="Force HTTPS redirect")

    # Backup
    enable_auto_backup: bool = Field(default=True, description="Enable auto backup")
    backup_retention_days: int = Field(default=30, description="Backup retention in days")
    backup_path: str = Field(default="./backups", description="Backup storage path")

    # Testing
    use_vcr_cassettes: bool = Field(default=True, description="Use VCR cassettes for testing")
    test_database_url: str = Field(default="sqlite:///./test.db", description="Test database URL")

    @field_validator("allowed_origins")
    @classmethod
    def parse_allowed_origins(cls, v: str) -> list[str]:
        """Parse comma-separated origins into list."""
        return [origin.strip() for origin in v.split(",") if origin.strip()]

    @field_validator("manual_exchange_rates")
    @classmethod
    def parse_manual_exchange_rates(cls, v: Optional[str]) -> Optional[dict[str, float]]:
        """Parse JSON exchange rates."""
        if v:
            return json.loads(v)
        return None

    def load_account_mapping(self) -> dict[str, Any]:
        """Load account mapping from JSON file."""
        mapping_path = Path(self.account_mapping_path)
        if not mapping_path.exists():
            raise FileNotFoundError(f"Account mapping file not found: {mapping_path}")

        with open(mapping_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def load_tax_rules(self) -> dict[str, Any]:
        """Load tax rules from JSON file."""
        tax_rules_path = Path(self.tax_rules_path)
        if not tax_rules_path.exists():
            raise FileNotFoundError(f"Tax rules file not found: {tax_rules_path}")

        with open(tax_rules_path, "r", encoding="utf-8") as f:
            return json.load(f)

    @property
    def is_production(self) -> bool:
        """Check if running in production."""
        return self.app_env == "production"

    @property
    def is_development(self) -> bool:
        """Check if running in development."""
        return self.app_env == "development"


# Global settings instance
settings = Settings()
