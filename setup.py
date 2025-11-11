#!/usr/bin/env python3
"""
Etsy-SevDesk Sync - Interaktives Setup-Tool

Erstellt die lokale Konfigurationsdatei durch interaktive Abfrage aller
benötigten Credentials und Einstellungen.

Usage:
    python3 setup.py
"""

import sys
from pathlib import Path
from typing import Optional

try:
    import yaml
    from cryptography.fernet import Fernet
    from rich.console import Console
    from rich.panel import Panel
    from rich.prompt import Confirm, Prompt
except ImportError:
    print("ERROR: Bitte installiere zuerst die Dependencies:")
    print("  pip install -r requirements-simple.txt")
    sys.exit(1)

console = Console()


def print_header(title: str) -> None:
    """Zeigt einen formatierten Header an."""
    console.print()
    console.print(Panel(f"[bold cyan]{title}[/bold cyan]", expand=False))
    console.print()


def print_info(message: str) -> None:
    """Zeigt eine Info-Nachricht an."""
    console.print(f"[dim]ℹ {message}[/dim]")


def print_success(message: str) -> None:
    """Zeigt eine Erfolgs-Nachricht an."""
    console.print(f"[green]✓ {message}[/green]")


def print_error(message: str) -> None:
    """Zeigt eine Fehler-Nachricht an."""
    console.print(f"[red]✗ {message}[/red]")


def prompt_text(
    question: str, default: str = "", password: bool = False, required: bool = True
) -> str:
    """
    Fragt den Benutzer nach Text-Eingabe.

    Args:
        question: Die Frage
        default: Standard-Wert
        password: Eingabe als Passwort maskieren
        required: Ob die Eingabe erforderlich ist

    Returns:
        Die Benutzereingabe
    """
    while True:
        value = Prompt.ask(question, default=default, password=password)
        if value or not required:
            return value
        print_error("Diese Eingabe ist erforderlich!")


def prompt_bool(question: str, default: bool = False) -> bool:
    """
    Fragt den Benutzer nach Ja/Nein.

    Args:
        question: Die Frage
        default: Standard-Wert

    Returns:
        True für Ja, False für Nein
    """
    return Confirm.ask(question, default=default)


def generate_encryption_key() -> str:
    """
    Generiert einen neuen Verschlüsselungs-Key.

    Returns:
        Base64-kodierter Fernet-Key
    """
    return Fernet.generate_key().decode()


def load_template_config() -> dict:
    """
    Lädt die Template-Konfiguration.

    Returns:
        Template-Konfiguration als Dictionary
    """
    template_path = Path(__file__).parent / "config" / "config.yaml"
    if not template_path.exists():
        print_error(f"Template-Datei nicht gefunden: {template_path}")
        sys.exit(1)

    with open(template_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def save_config(config: dict, output_path: Path) -> None:
    """
    Speichert die Konfiguration in eine YAML-Datei.

    Args:
        config: Konfiguration als Dictionary
        output_path: Zielpfad für die Datei
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)


def setup_etsy_config(config: dict) -> None:
    """Konfiguriert Etsy API Settings."""
    print_header("Etsy API Konfiguration")

    has_credentials = prompt_bool(
        "Hast du bereits Etsy API Credentials?", default=False
    )

    if not has_credentials:
        print_info("Erstelle Etsy API Credentials:")
        print_info("1. Gehe zu: https://www.etsy.com/developers/your-apps")
        print_info("2. Erstelle eine neue App oder wähle eine bestehende aus")
        print_info("3. Notiere dir die 'Keystring' (Client ID) und 'Shared Secret'")
        console.print()
        if not prompt_bool("Fortfahren wenn du die Credentials hast?", default=True):
            print_error("Setup abgebrochen.")
            sys.exit(0)

    # API Credentials
    config["etsy"]["client_id"] = prompt_text(
        "Etsy API Key (Keystring/Client ID):",
        default=config["etsy"]["client_id"]
    )

    config["etsy"]["client_secret"] = prompt_text(
        "Etsy Client Secret (Shared Secret):",
        default=config["etsy"]["client_secret"],
        password=True
    )

    # Shop ID
    config["etsy"]["shop_id"] = prompt_text(
        "Etsy Shop ID (numerisch, z.B. 12345678):",
        default=config["etsy"]["shop_id"]
    )

    # Refresh Token
    print_info("OAuth2 Refresh Token benötigt für automatischen Zugriff")
    print_info("Falls du noch keinen hast, siehe: README-SIMPLE.md")

    config["etsy"]["refresh_token"] = prompt_text(
        "Etsy Refresh Token:",
        default=config["etsy"]["refresh_token"],
        password=True
    )

    print_success("Etsy API konfiguriert!")


def setup_sevdesk_config(config: dict) -> bool:
    """Konfiguriert sevDesk API Settings (optional)."""
    print_header("sevDesk API Konfiguration (Optional)")

    print_info("💡 Hinweis: sevDesk API ist NUR mit Buchhaltung Pro verfügbar (49€/Monat)")
    print_info("💡 Alternative: CSV-Export (kein API Token nötig)")
    console.print()

    use_api = prompt_bool(
        "Möchtest du sevDesk API nutzen? (Nur mit Pro-Tarif)", default=False
    )

    if not use_api:
        print_info("✅ Kein Problem! Du kannst CSV-Export nutzen:")
        print_info("   python3 run_sync.py export-csv --days 30")
        config["sevdesk"]["api_token"] = ""
        return False

    has_token = prompt_bool(
        "Hast du bereits einen sevDesk API Token?", default=False
    )

    if not has_token:
        print_info("Erstelle sevDesk API Token:")
        print_info("1. Gehe zu: https://my.sevdesk.de/#/admin/userManagement")
        print_info("2. Klicke auf deinen Benutzer")
        print_info("3. Erstelle einen neuen API Token")
        print_info("4. Kopiere den Token (er wird nur einmal angezeigt!)")
        console.print()
        if not prompt_bool("Fortfahren wenn du den Token hast?", default=True):
            print_error("Setup abgebrochen.")
            sys.exit(0)

    config["sevdesk"]["api_token"] = prompt_text(
        "sevDesk API Token:",
        default=config["sevdesk"]["api_token"],
        password=True
    )

    print_success("sevDesk API konfiguriert!")
    return True


def setup_tax_config(config: dict) -> None:
    """Konfiguriert Steuer-Einstellungen."""
    print_header("Steuer-Einstellungen")

    # Kleinunternehmer
    print_info("§19 UStG Kleinunternehmer-Regelung:")
    print_info("- Umsatz < 22.000€ im Vorjahr")
    print_info("- Keine Umsatzsteuer auf Rechnungen")
    is_small_business = prompt_bool(
        "Bist du Kleinunternehmer (§19 UStG)?",
        default=config["tax"]["is_small_business"]
    )
    config["tax"]["is_small_business"] = is_small_business

    if not is_small_business:
        # OSS
        print_info("\nOne-Stop-Shop (OSS) für EU-Verkäufe:")
        print_info("- Vereinfachte USt-Abwicklung für EU-Verkäufe")
        print_info("- Meldung über ELSTER Portal")
        config["tax"]["use_oss"] = prompt_bool(
            "Nutzt du OSS für EU-Verkäufe?",
            default=config["tax"]["use_oss"]
        )

        # VAT ID
        vat_id = prompt_text(
            "Umsatzsteuer-ID (optional, z.B. DE123456789):",
            default=config["tax"]["vat_id"],
            required=False
        )
        if vat_id:
            config["tax"]["vat_id"] = vat_id

        # Kontenrahmen
        print_info("\nKontenrahmen für Buchhaltung:")
        account_chart = Prompt.ask(
            "Kontenrahmen",
            choices=["SKR03", "SKR04"],
            default=config["tax"]["account_chart"]
        )
        config["tax"]["account_chart"] = account_chart
    else:
        # Kleinunternehmer hat keine USt
        config["tax"]["use_oss"] = False
        config["tax"]["vat_id"] = ""

    print_success("Steuer-Einstellungen konfiguriert!")


def setup_sync_config(config: dict) -> None:
    """Konfiguriert Sync-Einstellungen."""
    print_header("Sync-Einstellungen")

    # Auto-Create Invoices
    config["sync"]["auto_create_invoices"] = prompt_bool(
        "Automatisch Rechnungen in sevDesk erstellen?",
        default=config["sync"]["auto_create_invoices"]
    )

    # Sync Fees
    config["sync"]["sync_fees"] = prompt_bool(
        "Etsy-Gebühren synchronisieren?",
        default=config["sync"]["sync_fees"]
    )

    # Auto-Process Refunds
    config["sync"]["auto_process_refunds"] = prompt_bool(
        "Automatisch Gutschriften für Rückerstattungen erstellen?",
        default=config["sync"]["auto_process_refunds"]
    )

    # Initial Sync Date
    print_info("\nStartdatum für ersten Sync (YYYY-MM-DD):")
    sync_date = prompt_text(
        "Start-Datum",
        default=config["sync"]["initial_sync_start_date"]
    )
    config["sync"]["initial_sync_start_date"] = sync_date

    print_success("Sync-Einstellungen konfiguriert!")


def setup_database_config(config: dict) -> None:
    """Konfiguriert Datenbank-Einstellungen."""
    print_header("Datenbank-Einstellungen")

    print_info("Für lokale Nutzung wird SQLite empfohlen (keine Installation nötig)")

    use_sqlite = prompt_bool(
        "SQLite Datenbank verwenden?",
        default=True
    )

    if use_sqlite:
        db_path = prompt_text(
            "Datenbank-Pfad",
            default="./data/etsy_sevdesk.db"
        )
        config["database"]["url"] = f"sqlite:///{db_path}"
    else:
        db_url = prompt_text(
            "PostgreSQL URL (z.B. postgresql://user:pass@localhost/dbname):",
            default=config["database"]["url"]
        )
        config["database"]["url"] = db_url

    print_success("Datenbank konfiguriert!")


def setup_encryption_config(config: dict) -> None:
    """Konfiguriert Verschlüsselung."""
    print_header("Verschlüsselung")

    print_info("Ein Encryption Key wird für die sichere Speicherung von Tokens benötigt")

    if not config["encryption"]["key"]:
        generate_key = prompt_bool(
            "Neuen Encryption Key generieren?",
            default=True
        )

        if generate_key:
            config["encryption"]["key"] = generate_encryption_key()
            print_success("Neuer Encryption Key generiert!")
        else:
            config["encryption"]["key"] = prompt_text(
                "Encryption Key (Base64):",
                password=True
            )
    else:
        print_info("Bestehender Key wird beibehalten")

    print_success("Verschlüsselung konfiguriert!")


def main() -> None:
    """Hauptfunktion des Setup-Tools."""
    console.print()
    console.print(Panel.fit(
        "[bold green]Etsy-SevDesk Sync - Setup[/bold green]\n"
        "Dieses Tool hilft dir, die Konfiguration einzurichten.",
        border_style="green"
    ))

    # Check if local.yaml already exists
    config_dir = Path(__file__).parent / "config"
    output_path = config_dir / "local.yaml"

    if output_path.exists():
        print_info(f"Konfiguration existiert bereits: {output_path}")
        if not prompt_bool("Möchtest du sie überschreiben?", default=False):
            print_error("Setup abgebrochen.")
            sys.exit(0)

    # Load template
    try:
        config = load_template_config()
    except Exception as e:
        print_error(f"Fehler beim Laden der Template-Konfiguration: {e}")
        sys.exit(1)

    # Run setup steps
    try:
        setup_etsy_config(config)
        use_sevdesk_api = setup_sevdesk_config(config)
        setup_tax_config(config)

        # Only configure sync settings if using sevDesk API
        if use_sevdesk_api:
            setup_sync_config(config)
        else:
            # Disable auto-sync for CSV-only mode
            config["sync"]["auto_create_invoices"] = False
            print_info("ℹ️  Sync-Einstellungen übersprungen (CSV-Export Modus)")

        setup_database_config(config)
        setup_encryption_config(config)

        # Save configuration
        print_header("Konfiguration speichern")
        save_config(config, output_path)
        print_success(f"Konfiguration gespeichert: {output_path}")

        # Create data directory
        data_dir = Path(__file__).parent / "data"
        data_dir.mkdir(exist_ok=True)
        print_success(f"Datenverzeichnis erstellt: {data_dir}")

        # Final success message
        console.print()
        console.print(Panel.fit(
            "[bold green]Setup erfolgreich abgeschlossen![/bold green]\n\n"
            f"Konfiguration: {output_path}\n\n"
            "Nächste Schritte:\n"
            "1. Teste die Konfiguration: [cyan]python3 run_sync.py --dry-run[/cyan]\n"
            "2. Starte ersten Sync: [cyan]python3 run_sync.py[/cyan]\n\n"
            "Hilfe: [cyan]python3 run_sync.py --help[/cyan]",
            border_style="green"
        ))

    except KeyboardInterrupt:
        console.print()
        print_error("Setup durch Benutzer abgebrochen.")
        sys.exit(0)
    except Exception as e:
        console.print()
        print_error(f"Fehler während des Setups: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
