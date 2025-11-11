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
def export_csv(
    output_dir: Path = typer.Option(
        "exports",
        help="Output-Verzeichnis für CSV-Dateien"
    ),
    days: int = typer.Option(
        30,
        help="Letzte N Tage exportieren"
    ),
    from_date: Optional[str] = typer.Option(
        None,
        "--from",
        help="Start-Datum (YYYY-MM-DD)"
    ),
    to_date: Optional[str] = typer.Option(
        None,
        "--to",
        help="End-Datum (YYYY-MM-DD)"
    ),
    include_fees: bool = typer.Option(
        True,
        help="Gebühren exportieren"
    ),
    skip_confirmation: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="Bestätigung überspringen"
    ),
) -> None:
    """
    Exportiert Etsy-Daten als CSV-Dateien (sevDesk-kompatibel).

    Keine sevDesk API nötig - CSVs können manuell importiert werden!

    Die CSV-Dateien werden im deutschen Format erstellt:
    - Semikolon-Separator (;)
    - Komma als Dezimaltrenner
    - Datum: DD.MM.YYYY
    - UTF-8 mit BOM (Excel-kompatibel)
    """
    from decimal import Decimal
    from app.export.csv_exporter import SevDeskCSVExporter
    from app.db.models import Order, Refund, Fee

    # Print header
    console.print()
    console.print(Panel.fit(
        "[bold green]CSV-Export Modus[/bold green]\n"
        "Exportiert Daten OHNE sevDesk API",
        border_style="green"
    ))
    console.print()

    try:
        # Load configuration
        config = load_config()
        console.print("[green]✓[/green] Konfiguration geladen")

        # Initialize database
        db_url = config["database"]["url"]
        init_database(db_url)

        # Create database session
        engine = create_engine(db_url, echo=False)
        db_session = Session(engine)

        # Determine date range
        if from_date:
            start_date = datetime.fromisoformat(from_date)
        else:
            start_date = datetime.now() - timedelta(days=days)

        if to_date:
            end_date = datetime.fromisoformat(to_date)
        else:
            end_date = datetime.now()

        console.print(f"[dim]Zeitraum: {start_date.date()} bis {end_date.date()}[/dim]")
        console.print()

        # Fetch data from database
        console.print("[bold]Lade Daten aus Datenbank...[/bold]")

        # Fetch orders
        stmt = select(Order).where(
            Order.etsy_created_at >= start_date,
            Order.etsy_created_at <= end_date
        )
        orders = db_session.execute(stmt).scalars().all()

        # Fetch refunds
        stmt = select(Refund)
        refunds = db_session.execute(stmt).scalars().all()

        # Fetch fees
        fees = []
        if include_fees:
            stmt = select(Fee)
            fees = db_session.execute(stmt).scalars().all()

        # Convert to dictionaries
        orders_data = []
        for order in orders:
            orders_data.append({
                "etsy_order_id": order.etsy_order_id,
                "raw_data": order.raw_data,
                "buyer_country": order.buyer_country,
                "currency": order.currency,
                "total_amount": order.total_amount,
                "tax_amount": order.tax_amount,
                "etsy_created_at": order.etsy_created_at,
            })

        refunds_data = []
        for refund in refunds:
            refunds_data.append({
                "etsy_refund_id": refund.etsy_refund_id,
                "etsy_order_id": refund.etsy_order_id,
                "raw_data": refund.raw_data,
                "amount": refund.amount,
                "currency": refund.currency,
                "created_at": refund.created_at,
            })

        fees_data = []
        for fee in fees:
            fees_data.append({
                "id": fee.id,
                "period": fee.period,
                "fee_type": fee.fee_type,
                "amount": fee.amount,
                "currency": fee.currency,
            })

        # Show preview
        console.print()
        console.print("[bold]Daten gefunden:[/bold]")
        table = Table()
        table.add_column("Typ", style="cyan")
        table.add_column("Anzahl", style="green")
        table.add_row("Bestellungen", str(len(orders_data)))
        table.add_row("Gutschriften", str(len(refunds_data)))
        if include_fees:
            table.add_row("Gebühren", str(len(fees_data)))
        console.print(table)
        console.print()

        # Show preview of first orders
        if orders_data and len(orders_data) > 0:
            console.print("[bold]Preview (erste 5 Bestellungen):[/bold]")
            preview_table = Table()
            preview_table.add_column("Bestell-ID")
            preview_table.add_column("Datum")
            preview_table.add_column("Brutto")
            preview_table.add_column("Land")

            for order in orders_data[:5]:
                order_date = order["etsy_created_at"]
                if isinstance(order_date, datetime):
                    date_str = order_date.strftime("%d.%m.%Y")
                else:
                    date_str = str(order_date)

                preview_table.add_row(
                    str(order["etsy_order_id"]),
                    date_str,
                    f"{order['total_amount']:.2f} {order['currency']}",
                    order["buyer_country"]
                )

            console.print(preview_table)
            console.print()

        # Confirm export
        if not skip_confirmation:
            if not typer.confirm("CSV-Dateien jetzt exportieren?"):
                console.print("[yellow]Export abgebrochen[/yellow]")
                raise typer.Exit(0)

        # Create output directory with timestamp
        timestamp = datetime.now()
        export_dir = Path(output_dir) / timestamp.strftime("%Y-%m-%d_%H-%M")
        export_dir.mkdir(parents=True, exist_ok=True)

        console.print()
        console.print(f"[bold]Exportiere nach:[/bold] {export_dir.absolute()}")
        console.print()

        # Initialize exporter
        exporter = SevDeskCSVExporter(export_dir)

        # Calculate statistics
        stats = {
            "invoices_count": len(orders_data),
            "invoices_total": sum(Decimal(str(o["total_amount"])) for o in orders_data),
            "credit_notes_count": len(refunds_data),
            "credit_notes_total": sum(Decimal(str(r["amount"])) for r in refunds_data),
            "fees_count": len(fees_data),
            "fees_total": sum(Decimal(str(f["amount"])) for f in fees_data) if fees_data else Decimal("0"),
        }

        # Export invoices
        if orders_data:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console
            ) as progress:
                task = progress.add_task("Exportiere Rechnungen...", total=None)
                invoices_path = exporter.export_invoices(orders_data)
                progress.update(task, completed=100, total=100)
            console.print(f"[green]✓[/green] Rechnungen exportiert: {invoices_path.name}")

        # Export credit notes
        if refunds_data:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console
            ) as progress:
                task = progress.add_task("Exportiere Gutschriften...", total=None)
                credits_path = exporter.export_credit_notes(refunds_data)
                progress.update(task, completed=100, total=100)
            console.print(f"[green]✓[/green] Gutschriften exportiert: {credits_path.name}")

        # Export fees
        if fees_data:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console
            ) as progress:
                task = progress.add_task("Exportiere Gebühren...", total=None)
                fees_path = exporter.export_fees(fees_data)
                progress.update(task, completed=100, total=100)
            console.print(f"[green]✓[/green] Gebühren exportiert: {fees_path.name}")

        # Create import guide
        console.print()
        console.print("[dim]Erstelle Import-Anleitung...[/dim]")
        guide_path = exporter.create_import_guide(stats, timestamp)
        console.print(f"[green]✓[/green] Import-Anleitung: {guide_path.name}")

        # Create summary
        summary_path = exporter.create_summary(stats, timestamp)
        console.print(f"[green]✓[/green] Zusammenfassung: {summary_path.name}")

        # Show final statistics
        console.print()
        console.print("[bold green]Export erfolgreich abgeschlossen![/bold green]")
        console.print()

        result_table = Table(title="Export Statistik")
        result_table.add_column("Kategorie", style="cyan")
        result_table.add_column("Anzahl", style="green")
        result_table.add_column("Summe", style="yellow")

        result_table.add_row(
            "Rechnungen",
            str(stats["invoices_count"]),
            f"{stats['invoices_total']:.2f} EUR"
        )

        if stats["credit_notes_count"] > 0:
            result_table.add_row(
                "Gutschriften",
                str(stats["credit_notes_count"]),
                f"{stats['credit_notes_total']:.2f} EUR"
            )

        if stats["fees_count"] > 0:
            result_table.add_row(
                "Gebühren",
                str(stats["fees_count"]),
                f"{stats['fees_total']:.2f} EUR"
            )

        console.print(result_table)
        console.print()
        console.print(f"[bold]Export-Verzeichnis:[/bold] [cyan]{export_dir.absolute()}[/cyan]")
        console.print()
        console.print("[yellow]Nächste Schritte:[/yellow]")
        console.print("  1. Öffne die Datei [cyan]import_anleitung.md[/cyan]")
        console.print("  2. Folge den Schritten zum Import in sevDesk")
        console.print("  3. Prüfe die importierten Daten")
        console.print()

        db_session.close()

    except KeyboardInterrupt:
        console.print()
        console.print("[yellow]Export abgebrochen[/yellow]")
        raise typer.Exit(0)

    except Exception as e:
        console.print()
        console.print(f"[red]FEHLER beim Export: {e}[/red]")
        logger.exception("CSV export failed")
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
