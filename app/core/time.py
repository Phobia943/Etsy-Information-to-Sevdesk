"""
Timezone-aware datetime utilities for Europe/Berlin timezone.

Ensures all timestamps are properly handled with GoBD compliance in mind.
"""

from datetime import datetime, timedelta, timezone as dt_timezone
from typing import Optional, Union

import pytz
from babel.dates import format_datetime as babel_format_datetime

from app.core.config import settings


# Get configured timezone
TIMEZONE = pytz.timezone(settings.timezone)


def now() -> datetime:
    """
    Get current datetime in configured timezone.

    Returns:
        Timezone-aware datetime in Europe/Berlin (or configured timezone)
    """
    return datetime.now(TIMEZONE)


def utcnow() -> datetime:
    """
    Get current UTC datetime.

    Returns:
        Timezone-aware datetime in UTC
    """
    return datetime.now(dt_timezone.utc)


def to_timezone(dt: datetime, tz: Optional[pytz.timezone] = None) -> datetime:
    """
    Convert datetime to specified timezone (or default configured timezone).

    Args:
        dt: Input datetime (can be naive or aware)
        tz: Target timezone (defaults to configured timezone)

    Returns:
        Timezone-aware datetime in target timezone
    """
    target_tz = tz or TIMEZONE

    # If naive, assume it's in target timezone
    if dt.tzinfo is None:
        return target_tz.localize(dt)

    # Convert to target timezone
    return dt.astimezone(target_tz)


def to_utc(dt: datetime) -> datetime:
    """
    Convert datetime to UTC.

    Args:
        dt: Input datetime (can be naive or aware)

    Returns:
        Timezone-aware datetime in UTC
    """
    # If naive, assume it's in configured timezone
    if dt.tzinfo is None:
        dt = TIMEZONE.localize(dt)

    return dt.astimezone(dt_timezone.utc)


def parse_iso(dt_str: str) -> datetime:
    """
    Parse ISO 8601 datetime string to timezone-aware datetime.

    Args:
        dt_str: ISO 8601 datetime string

    Returns:
        Timezone-aware datetime

    Examples:
        >>> parse_iso("2025-01-15T10:30:00Z")
        >>> parse_iso("2025-01-15T10:30:00+01:00")
    """
    dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
    return to_timezone(dt)


def format_iso(dt: datetime) -> str:
    """
    Format datetime as ISO 8601 string in UTC.

    Args:
        dt: Datetime to format

    Returns:
        ISO 8601 string (e.g., "2025-01-15T09:30:00Z")
    """
    utc_dt = to_utc(dt)
    return utc_dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def format_datetime(
    dt: datetime,
    format: str = "medium",
    locale: str = "de_DE",
) -> str:
    """
    Format datetime in German locale for invoices/documents.

    Args:
        dt: Datetime to format
        format: Format type (short, medium, long, full)
        locale: Locale string

    Returns:
        Formatted datetime string

    Examples:
        >>> format_datetime(now(), "medium")  # "15.01.2025, 10:30:00"
        >>> format_datetime(now(), "short")   # "15.01.25, 10:30"
    """
    localized_dt = to_timezone(dt)
    return babel_format_datetime(localized_dt, format=format, locale=locale)


def format_date(dt: datetime, locale: str = "de_DE") -> str:
    """
    Format date only (no time) in German format.

    Args:
        dt: Datetime to format
        locale: Locale string

    Returns:
        Formatted date string (e.g., "15.01.2025")
    """
    from babel.dates import format_date as babel_format_date

    localized_dt = to_timezone(dt)
    return babel_format_date(localized_dt, format="medium", locale=locale)


def start_of_day(dt: datetime) -> datetime:
    """
    Get start of day (00:00:00) for given datetime.

    Args:
        dt: Input datetime

    Returns:
        Datetime set to 00:00:00 in configured timezone
    """
    localized = to_timezone(dt)
    return localized.replace(hour=0, minute=0, second=0, microsecond=0)


def end_of_day(dt: datetime) -> datetime:
    """
    Get end of day (23:59:59.999999) for given datetime.

    Args:
        dt: Input datetime

    Returns:
        Datetime set to 23:59:59.999999 in configured timezone
    """
    localized = to_timezone(dt)
    return localized.replace(hour=23, minute=59, second=59, microsecond=999999)


def start_of_month(dt: datetime) -> datetime:
    """
    Get first day of month at 00:00:00.

    Args:
        dt: Input datetime

    Returns:
        First day of month at 00:00:00
    """
    localized = to_timezone(dt)
    return localized.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def end_of_month(dt: datetime) -> datetime:
    """
    Get last day of month at 23:59:59.999999.

    Args:
        dt: Input datetime

    Returns:
        Last day of month at 23:59:59.999999
    """
    localized = to_timezone(dt)

    # Get first day of next month, then subtract one microsecond
    if localized.month == 12:
        next_month = localized.replace(year=localized.year + 1, month=1, day=1)
    else:
        next_month = localized.replace(month=localized.month + 1, day=1)

    next_month = next_month.replace(hour=0, minute=0, second=0, microsecond=0)
    return next_month - timedelta(microseconds=1)


def days_ago(days: int) -> datetime:
    """
    Get datetime N days ago from now.

    Args:
        days: Number of days to subtract

    Returns:
        Datetime N days ago
    """
    return now() - timedelta(days=days)


def days_from_now(days: int) -> datetime:
    """
    Get datetime N days from now.

    Args:
        days: Number of days to add

    Returns:
        Datetime N days from now
    """
    return now() + timedelta(days=days)


def parse_date_or_days_back(
    date_str: Optional[str] = None,
    days_back: Optional[int] = None,
) -> datetime:
    """
    Parse date string or calculate from days_back parameter.

    Used for sync operations to determine start date.

    Args:
        date_str: ISO date string (e.g., "2024-01-01")
        days_back: Number of days to go back from now

    Returns:
        Start datetime for sync operations

    Raises:
        ValueError: If neither parameter is provided
    """
    if date_str:
        # Parse ISO date string
        if "T" in date_str:
            return parse_iso(date_str)
        else:
            # Date only, assume start of day
            dt = datetime.fromisoformat(date_str)
            return start_of_day(TIMEZONE.localize(dt))

    if days_back is not None:
        return days_ago(days_back)

    raise ValueError("Either date_str or days_back must be provided")


def get_month_period(year: int, month: int) -> tuple[datetime, datetime]:
    """
    Get start and end datetime for a specific month.

    Args:
        year: Year
        month: Month (1-12)

    Returns:
        Tuple of (start_of_month, end_of_month)
    """
    dt = TIMEZONE.localize(datetime(year, month, 1))
    return start_of_month(dt), end_of_month(dt)


def is_same_day(dt1: datetime, dt2: datetime) -> bool:
    """
    Check if two datetimes are on the same day (ignoring time).

    Args:
        dt1: First datetime
        dt2: Second datetime

    Returns:
        True if same day, False otherwise
    """
    localized1 = to_timezone(dt1)
    localized2 = to_timezone(dt2)

    return (
        localized1.year == localized2.year
        and localized1.month == localized2.month
        and localized1.day == localized2.day
    )


def timestamp_to_datetime(timestamp: Union[int, float]) -> datetime:
    """
    Convert Unix timestamp to timezone-aware datetime.

    Args:
        timestamp: Unix timestamp (seconds since epoch)

    Returns:
        Timezone-aware datetime in configured timezone
    """
    utc_dt = datetime.fromtimestamp(timestamp, tz=dt_timezone.utc)
    return to_timezone(utc_dt)


def datetime_to_timestamp(dt: datetime) -> int:
    """
    Convert datetime to Unix timestamp.

    Args:
        dt: Datetime to convert

    Returns:
        Unix timestamp (seconds since epoch)
    """
    if dt.tzinfo is None:
        dt = TIMEZONE.localize(dt)

    return int(dt.timestamp())
