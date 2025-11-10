#!/usr/bin/env python3
"""
Etsy-SevDesk Sync - Hauptprogramm für CLI-Nutzung

Synchronisiert Etsy-Bestellungen mit sevDesk ohne Server/Docker.

Usage:
    python3 run_sync.py                    # Normal sync
    python3 run_sync.py --dry-run          # Test ohne zu buchen
    python3 run_sync.py --from 2024-01-01  # Custom Datumsbereich
    python3 run_sync.py --fees-only        # Nur Gebühren
"""

import asyncio
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

try:
    import typer
    import yaml
    from rich.console import Console
    from rich.panel import Panel
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
    from rich.table import Table
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import Session
except ImportError:
    print("ERROR: Bitte installiere zuerst die Dependencies:")
    print("  pip install -r requirements-simple.txt")
    sys.exit(1)

# Import app modules
try:
    from app.clients.etsy_client import EtsyClient
    from app.clients.sevdesk_client import SevdeskClient
    from app.core.logging import get_logger
    from app.db.base import Base
    from app.db.models import IntegrationState, Order, Invoice
except ImportError as e:
    print(f"ERROR: Konnte App-Module nicht laden: {e}")
    print("Stelle sicher, dass du im Projektverzeichnis bist.")
    sys.exit(1)

# Initialize CLI and console
app = typer.Typer(help="Etsy-SevDesk Sync - CLI Tool")
console = Console()
logger = get_logger(__name__)


def load_config() -> dict:
    """
    Lädt die lokale Konfiguration aus config/local.yaml.

    Returns:
        Konfiguration als Dictionary

    Raises:
        FileNotFoundError: Wenn config/local.yaml nicht existiert
    """
    config_path = project_root / "config" / "local.yaml"

    if not config_path.exists():
        console.print("[red]ERROR: Konfiguration nicht gefunden![/red]")
        console.print(f"Erwarteter Pfad: {config_path}")
        console.print("\nBitte führe zuerst das Setup aus:")
        console.print("  [cyan]python3 setup.py[/cyan]")
        raise typer.Exit(1)

    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def setup_environment(config: dict) -> None:
    """
    Setzt Umgebungsvariablen aus der Konfiguration.

    Args:
        config: Konfiguration aus local.yaml
    """
    # Map YAML config to environment variables expected by app
    os.environ["ETSY_CLIENT_ID"] = config["etsy"]["client_id"]
    os.environ["ETSY_CLIENT_SECRET"] = config["etsy"]["client_secret"]
    os.environ["ETSY_SHOP_ID"] = config["etsy"]["shop_id"]
    os.environ["ETSY_REFRESH_TOKEN"] = config["etsy"]["refresh_token"]
    os.environ["ETSY_API_BASE_URL"] = config["etsy"].get("api_base_url", "https://openapi.etsy.com/v3")
    os.environ["ETSY_API_TIMEOUT"] = str(config["etsy"].get("api_timeout", 30))
    os.environ["ETSY_RATE_LIMIT"] = str(config["etsy"].get("rate_limit", 10))

    os.environ["SEVDESK_API_TOKEN"] = config["sevdesk"]["api_token"]
    os.environ["SEVDESK_API_BASE_URL"] = config["sevdesk"].get("api_base_url", "https://my.sevdesk.de/api/v1")
    os.environ["SEVDESK_API_TIMEOUT"] = str(config["sevdesk"].get("api_timeout", 30))
    os.environ["SEVDESK_RATE_LIMIT"] = str(config["sevdesk"].get("rate_limit", 5))

    os.environ["KLEINUNTERNEHMER"] = str(config["tax"]["is_small_business"]).lower()
    os.environ["ENABLE_OSS"] = str(config["tax"]["use_oss"]).lower()
    os.environ["ACCOUNT_CHART"] = config["tax"]["account_chart"]
    os.environ["DEFAULT_TAX_RATE_DOMESTIC"] = str(config["tax"].get("default_rate_domestic", 19))

    os.environ["DATABASE_URL"] = config["database"]["url"]
    os.environ["TIMEZONE"] = config["app"].get("timezone", "Europe/Berlin")
    os.environ["BASE_CURRENCY"] = config["app"].get("base_currency", "EUR")
    os.environ["LOG_LEVEL"] = config["app"].get("log_level", "INFO")

    if config["app"].get("dry_run", False):
        os.environ["DRY_RUN"] = "true"

    if config["encryption"].get("key"):
        os.environ["ENCRYPTION_KEY"] = config["encryption"]["key"]

    # Additional settings
    os.environ["INITIAL_SYNC_START_DATE"] = config["sync"].get("initial_sync_start_date", "2024-01-01")
    os.environ["SYNC_BATCH_SIZE"] = str(config["sync"].get("batch_size", 100))
    os.environ["FEATURE_AUTO_PROCESS_REFUNDS"] = str(config["sync"].get("auto_process_refunds", True)).lower()
    os.environ["FEATURE_AUTO_PROCESS_FEES"] = str(config["sync"].get("sync_fees", True)).lower()


def init_database(db_url: str) -> None:
    """
    Initialisiert die Datenbank und erstellt Tabellen.

    Args:
        db_url: SQLAlchemy Database URL
    """
    console.print("[dim]Initialisiere Datenbank...[/dim]")

    # Create data directory if using SQLite
    if db_url.startswith("sqlite"):
        db_path = db_url.replace("sqlite:///", "")
        db_file = Path(db_path)
        db_file.parent.mkdir(parents=True, exist_ok=True)

    # Create engine and tables
    engine = create_engine(db_url, echo=False)
    Base.metadata.create_all(engine)

    console.print("[green]✓[/green] Datenbank bereit")


def get_last_sync_time(db_session: Session) -> Optional[datetime]:
    """
    Holt den Zeitstempel des letzten erfolgreichen Syncs.

    Args:
        db_session: SQLAlchemy Session

    Returns:
        Zeitstempel des letzten Syncs oder None
    """
    stmt = select(IntegrationState).where(IntegrationState.key == "last_order_sync")
    result = db_session.execute(stmt).scalar_one_or_none()

    if result and result.value:
        return datetime.fromisoformat(result.value.get("timestamp"))

    return None


def update_last_sync_time(db_session: Session, timestamp: datetime) -> None:
    """
    Aktualisiert den Zeitstempel des letzten Syncs.

    Args:
        db_session: SQLAlchemy Session
        timestamp: Neuer Zeitstempel
    """
    stmt = select(IntegrationState).where(IntegrationState.key == "last_order_sync")
    state = db_session.execute(stmt).scalar_one_or_none()

    if state:
        state.value = {"timestamp": timestamp.isoformat()}
        state.updated_at = datetime.now()
    else:
        state = IntegrationState(
            key="last_order_sync",
            value={"timestamp": timestamp.isoformat()},
            updated_at=datetime.now()
        )
        db_session.add(state)

    db_session.commit()


async def sync_orders(
    etsy_client: EtsyClient,
    sevdesk_client: SevdeskClient,
    db_session: Session,
    from_date: Optional[datetime] = None,
    dry_run: bool = False
) -> dict:
    """
    Synchronisiert Etsy-Bestellungen mit sevDesk.

    Args:
        etsy_client: Etsy API Client
        sevdesk_client: sevDesk API Client
        db_session: Database Session
        from_date: Start-Datum für Sync
        dry_run: Nur simulieren, nichts buchen

    Returns:
        Statistiken über den Sync
    """
    stats = {
        "orders_fetched": 0,
        "orders_new": 0,
        "invoices_created": 0,
        "errors": 0
    }

    # Determine start date
    if from_date is None:
        from_date = get_last_sync_time(db_session)
        if from_date is None:
            # First sync - use config default
            from_date_str = os.environ.get("INITIAL_SYNC_START_DATE", "2024-01-01")
            from_date = datetime.fromisoformat(from_date_str)

    console.print(f"[dim]Synchronisiere Bestellungen ab {from_date.date()}...[/dim]")

    try:
        # Fetch orders from Etsy
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console
        ) as progress:
            task = progress.add_task("Hole Etsy-Bestellungen...", total=None)

            # TODO: Implement actual API calls
            # For now, this is a placeholder structure
            # orders = await etsy_client.get_orders(min_created=from_date)
            # stats["orders_fetched"] = len(orders)

            progress.update(task, completed=100, total=100)

        # Process each order
        # TODO: Implement order processing logic
        # - Check if order already exists in DB
        # - Calculate taxes
        # - Create/update customer in sevDesk
        # - Create invoice in sevDesk
        # - Store mapping in DB

        if not dry_run:
            update_last_sync_time(db_session, datetime.now())

    except Exception as e:
        logger.error(f"Fehler beim Sync: {e}")
        stats["errors"] += 1
        raise

    return stats


async def sync_fees(
    etsy_client: EtsyClient,
    sevdesk_client: SevdeskClient,
    db_session: Session,
    dry_run: bool = False
) -> dict:
    """
    Synchronisiert Etsy-Gebühren mit sevDesk.

    Args:
        etsy_client: Etsy API Client
        sevdesk_client: sevDesk API Client
        db_session: Database Session
        dry_run: Nur simulieren, nichts buchen

    Returns:
        Statistiken über den Sync
    """
    stats = {
        "fee_periods": 0,
        "vouchers_created": 0,
        "errors": 0
    }

    console.print("[dim]Synchronisiere Gebühren...[/dim]")

    try:
        # TODO: Implement fee sync logic
        # - Fetch fee data from Etsy
        # - Group by month
        # - Create vouchers in sevDesk
        # - Store in DB
        pass

    except Exception as e:
        logger.error(f"Fehler beim Gebühren-Sync: {e}")
        stats["errors"] += 1
        raise

    return stats


@app.command()
def main(
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Nur simulieren, nichts in sevDesk buchen"
    ),
    from_date: Optional[str] = typer.Option(
        None,
        "--from",
        help="Start-Datum für Sync (YYYY-MM-DD)"
    ),
    days: Optional[int] = typer.Option(
        None,
        "--days",
        help="Letzte N Tage synchronisieren"
    ),
    fees_only: bool = typer.Option(
        False,
        "--fees-only",
        help="Nur Gebühren synchronisieren"
    ),
) -> None:
    """
    Startet die Synchronisation zwischen Etsy und sevDesk.
    """
    # Print header
    console.print()
    console.print(Panel.fit(
        "[bold cyan]Etsy-SevDesk Sync[/bold cyan]\n"
        f"{'[yellow]DRY RUN Modus[/yellow]' if dry_run else 'Produktiv-Modus'}",
        border_style="cyan"
    ))
    console.print()

    try:
        # Load configuration
        config = load_config()
        console.print("[green]✓[/green] Konfiguration geladen")

        # Setup environment
        setup_environment(config)

        # Override dry_run from CLI
        if dry_run:
            os.environ["DRY_RUN"] = "true"

        # Initialize database
        db_url = config["database"]["url"]
        init_database(db_url)

        # Create database session
        engine = create_engine(db_url, echo=False)
        db_session = Session(engine)

        # Determine from_date
        sync_from_date = None
        if from_date:
            sync_from_date = datetime.fromisoformat(from_date)
        elif days:
            sync_from_date = datetime.now() - timedelta(days=days)

        # Initialize clients
        console.print("[dim]Initialisiere API-Clients...[/dim]")
        etsy_client = EtsyClient()
        sevdesk_client = SevdeskClient()
        console.print("[green]✓[/green] API-Clients bereit")

        console.print()
        console.print("[bold]Starte Synchronisation...[/bold]")
        console.print()

        # Run sync
        if fees_only:
            # Only sync fees
            stats = asyncio.run(sync_fees(
                etsy_client,
                sevdesk_client,
                db_session,
                dry_run=dry_run
            ))

            # Show results
            table = Table(title="Gebühren-Sync Ergebnisse")
            table.add_column("Metrik", style="cyan")
            table.add_column("Wert", style="green")
            table.add_row("Perioden verarbeitet", str(stats["fee_periods"]))
            table.add_row("Belege erstellt", str(stats["vouchers_created"]))
            table.add_row("Fehler", str(stats["errors"]))

        else:
            # Sync orders
            stats = asyncio.run(sync_orders(
                etsy_client,
                sevdesk_client,
                db_session,
                from_date=sync_from_date,
                dry_run=dry_run
            ))

            # Show results
            table = Table(title="Sync Ergebnisse")
            table.add_column("Metrik", style="cyan")
            table.add_column("Wert", style="green")
            table.add_row("Bestellungen abgerufen", str(stats["orders_fetched"]))
            table.add_row("Neue Bestellungen", str(stats["orders_new"]))
            table.add_row("Rechnungen erstellt", str(stats["invoices_created"]))
            table.add_row("Fehler", str(stats["errors"]))

        console.print()
        console.print(table)
        console.print()

        if dry_run:
            console.print("[yellow]DRY RUN: Keine Änderungen wurden in sevDesk vorgenommen[/yellow]")
        else:
            console.print("[green]✓ Synchronisation erfolgreich abgeschlossen[/green]")

        # Close database session
        db_session.close()

    except KeyboardInterrupt:
        console.print()
        console.print("[yellow]Sync durch Benutzer abgebrochen[/yellow]")
        raise typer.Exit(0)

    except Exception as e:
        console.print()
        console.print(f"[red]FEHLER: {e}[/red]")
        logger.exception("Sync failed")
        raise typer.Exit(1)


@app.command()
def status() -> None:
    """Zeigt den Status des letzten Syncs."""
    try:
        config = load_config()
        db_url = config["database"]["url"]
        engine = create_engine(db_url, echo=False)
        db_session = Session(engine)

        last_sync = get_last_sync_time(db_session)

        console.print()
        console.print(Panel.fit("[bold cyan]Sync Status[/bold cyan]", border_style="cyan"))
        console.print()

        if last_sync:
            console.print(f"Letzter Sync: [green]{last_sync.strftime('%Y-%m-%d %H:%M:%S')}[/green]")
            delta = datetime.now() - last_sync
            console.print(f"Vor: [dim]{delta.days} Tagen, {delta.seconds // 3600} Stunden[/dim]")
        else:
            console.print("[yellow]Noch kein Sync durchgeführt[/yellow]")

        # Show some stats
        stmt = select(Order)
        order_count = len(db_session.execute(stmt).scalars().all())
        console.print(f"\nBestellungen in DB: [cyan]{order_count}[/cyan]")

        stmt = select(Invoice)
        invoice_count = len(db_session.execute(stmt).scalars().all())
        console.print(f"Rechnungen erstellt: [cyan]{invoice_count}[/cyan]")

        db_session.close()

    except Exception as e:
        console.print(f"[red]Fehler: {e}[/red]")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
