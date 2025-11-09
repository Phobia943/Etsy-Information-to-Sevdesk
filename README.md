# Etsy-sevDesk Synchronization Tool

[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

**Produktionsreife Automatisierung für die Synchronisation von Etsy-Bestellungen, -Gebühren und -Auszahlungen nach sevDesk**

Dieses selbstgehostete Tool automatisiert die Buchhaltung für Etsy-Händler in Deutschland mit vollständiger GoBD-Konformität und OSS-Unterstützung.

---

## Inhaltsverzeichnis

- [Features](#features)
- [Voraussetzungen](#voraussetzungen)
- [Quick Start](#quick-start)
- [Installation](#installation)
- [Konfiguration](#konfiguration)
  - [Etsy API Setup](#etsy-api-setup)
  - [sevDesk API Setup](#sevdesk-api-setup)
  - [Steuer-Konfiguration](#steuer-konfiguration)
  - [Konten-Mapping](#konten-mapping)
- [Betrieb](#betrieb)
  - [Erste Synchronisation](#erste-synchronisation)
  - [Automatisierte Syncs (Cron)](#automatisierte-syncs-cron)
  - [CLI-Befehle](#cli-befehle)
- [Architektur](#architektur)
- [Entwicklung](#entwicklung)
- [Sicherheit & DSGVO](#sicherheit--dsgvo)
- [Troubleshooting](#troubleshooting)
- [FAQ](#faq)
- [Lizenz](#lizenz)

---

## Features

### Kernfunktionalität

- **Automatische Rechnungserstellung** für Etsy-Bestellungen in sevDesk
  - Korrekte Steuerberechnung (DE Inland 19%/7%, EU OSS, Drittland-Export)
  - Positionsgenaue Rundung und Währungsumrechnung
  - Kleinunternehmer-Unterstützung (§19 UStG)

- **Gebühren-Verwaltung**
  - Etsy-Gebühren (Transaction Fees, Listing Fees, Offsite Ads) als Ausgabenbelege
  - Monatliche Gebührenabrechnungen mit PDF/CSV-Dokumenten
  - Automatische Vorsteuer-Abbildung

- **Payout-Abgleich**
  - Option A: Nur Rechnungserstellung (Zahlungen über sevDesk-Bankimport)
  - Option B: Automatische Zahlungsverbuchung via API

- **Rückerstattungen**
  - Automatische Gutschriften/Stornorechnungen
  - GoBD-konforme Korrekturen

### Technische Features

- **Idempotenz**: Sichere Wiederholbarkeit aller Operationen
- **Retry & Resilience**: Exponentielles Backoff, Circuit Breaker
- **Strukturierte Logs**: JSON-Logging mit PII-Maskierung
- **Audit Trail**: Vollständige Nachvollziehbarkeit aller Buchungen
- **Rate Limiting**: Automatische Behandlung von API-Limits
- **Webhooks**: Optional für Echtzeit-Updates (Etsy)
- **Docker-Ready**: Production-grade Container mit Health Checks

### Compliance

- **GoBD-konform**: Unveränderliche Buchungen, 10-jährige Aufbewahrung
- **DSGVO-freundlich**: PII-Minimierung, Maskierung, Export/Lösch-Routinen
- **OSS-Unterstützung**: One-Stop-Shop für EU-Fernverkäufe

---

## Voraussetzungen

### System

- **Docker & Docker Compose** (empfohlen) oder
- **Python 3.12+** für manuelle Installation
- **PostgreSQL 14+** (oder SQLite für Development)
- **Redis 6+** für Celery Task Queue

### API-Zugang

- **Etsy Developer Account**
  - OAuth2 App mit Client ID/Secret
  - Refresh Token für Shop-Zugriff
  - Benötigte Scopes: `shops_r`, `transactions_r`, `listings_r`, `billing_r`

- **sevDesk Account**
  - API-Token aus den Einstellungen
  - Berechtigung zur Rechnungs-/Belegverwaltung

### Fachliche Voraussetzungen

- **Steuerberatung**: Alle Steuereinstellungen (OSS-Sätze, Konten-Mapping) müssen mit Ihrem Steuerberater abgestimmt werden
- **Kontenrahmen**: SKR03 oder SKR04 Kontenplan
- **Buchhaltungswissen**: Grundverständnis der deutschen Finanzbuchhaltung

---

## Quick Start

```bash
# 1. Repository klonen oder entpacken
cd /pfad/zum/projekt

# 2. Umgebungsvariablen konfigurieren
cp .env.example .env
nano .env  # Etsy/sevDesk API-Credentials eintragen

# 3. Mit Docker starten
make up

# 4. Datenbank initialisieren
make migrate

# 5. Erste Synchronisation
make sync-orders since=2024-01-01

# 6. API-Dokumentation öffnen
open http://localhost:8000/docs
```

---

## Installation

### Option 1: Docker (Empfohlen)

```bash
# Services starten
docker-compose up -d

# Logs verfolgen
docker-compose logs -f
```

### Option 2: Manuelle Installation

```bash
# Python-Umgebung einrichten
python3.12 -m venv venv
source venv/bin/activate

# Dependencies installieren
pip install -r requirements.txt

# Development-Dependencies (optional)
pip install -r requirements-dev.txt

# Datenbank migrieren
alembic upgrade head

# API-Server starten
uvicorn app.api.main:app --reload
```

### Option 3: Systemd Service

```bash
# Systemd-Service erstellen (siehe docs/systemd-service.example)
sudo cp docs/systemd-service.example /etc/systemd/system/etsy-sevdesk.service
sudo systemctl daemon-reload
sudo systemctl enable etsy-sevdesk
sudo systemctl start etsy-sevdesk
```

---

## Konfiguration

### Etsy API Setup

1. **Developer App erstellen**
   - Gehe zu https://www.etsy.com/developers/your-apps
   - Erstelle neue App "Mein Buchhaltungs-Tool"
   - Notiere Client ID und Client Secret

2. **OAuth2-Flow durchführen**
   ```bash
   # TODO: Implementiere OAuth2-Helper-Script
   python scripts/etsy_oauth.py
   ```
   - Folge dem Link zur Autorisierung
   - Kopiere Refresh Token in `.env`

3. **Shop-ID ermitteln**
   ```bash
   # Shop-ID aus Etsy-URL (z.B. /shop/12345678)
   # Oder via API
   curl -H "x-api-key: YOUR_CLIENT_ID" \
        -H "Authorization: Bearer YOUR_TOKEN" \
        https://openapi.etsy.com/v3/application/users/me/shops
   ```

**Wichtig:** Refresh Tokens laufen nicht ab - sicher aufbewahren!

### sevDesk API Setup

1. **API-Token generieren**
   - Einloggen bei sevDesk
   - Einstellungen → Benutzerverwaltung → API-Token
   - Token kopieren und in `.env` eintragen

2. **Berechtigungen prüfen**
   - Token benötigt Zugriff auf Rechnungen, Belege, Kontakte
   - Test: `curl -H "Authorization: YOUR_TOKEN" https://my.sevdesk.de/api/v1/Contact?limit=1`

### Steuer-Konfiguration

Die Datei `config/tax_rules.json` enthält alle Steuersätze:

```json
{
  "domestic": {
    "country": "DE",
    "rules": [
      {"name": "Regelsteuersatz", "rate": 19.0, "code": "19"},
      {"name": "Ermäßigter Steuersatz", "rate": 7.0, "code": "7"}
    ]
  },
  "oss": {
    "enabled": true,
    "countries": {
      "AT": {"rate": 20.0},
      "FR": {"rate": 20.0},
      ...
    }
  }
}
```

**TODO-Schritte:**

1. sevDesk Tax IDs ermitteln:
   ```bash
   curl -H "Authorization: YOUR_TOKEN" \
        https://my.sevdesk.de/api/v1/Tax
   ```

2. IDs in `tax_rules.json` eintragen bei `sevdesk_tax_id`

3. OSS-Schwellenwert prüfen (10.000 € pro Jahr)

4. **Mit Steuerberater abstimmen!** Diese Konfiguration ist KEIN Ersatz für steuerliche Beratung.

### Konten-Mapping

Wähle deinen Kontenrahmen:

```bash
# SKR03 (Standard)
cp config/account_mapping_skr03.json config/account_mapping.json

# Oder SKR04
cp config/account_mapping_skr04.json config/account_mapping.json
```

Passe Konten an deine Buchungslogik an:

```json
{
  "revenue_accounts": {
    "domestic_19": {"account": "8400", "name": "Erlöse 19% USt"},
    "oss_eu": {"account": "8125", "name": "Erlöse EU OSS"}
  },
  "expense_accounts": {
    "etsy_transaction_fee": {"account": "4980", "name": "Nebenkosten Geldverkehr"}
  }
}
```

**Wichtig:** Kontenzuordnung mit Steuerberater prüfen!

---

## Betrieb

### Erste Synchronisation

```bash
# Alle Bestellungen ab 1. Januar 2024 synchronisieren
make sync-orders since=2024-01-01

# Nur trockenlaufen (kein sevDesk-Schreibzugriff)
DRY_RUN=true make sync-orders since=2024-01-01

# Gebühren für November 2024
make sync-fees period=2024-11

# Payouts
make sync-payouts since=2024-01-01

# Kompletter Backfill
make backfill
```

### Automatisierte Syncs (Cron)

**Systemd Timer (empfohlen):**

```bash
# Timer erstellen
sudo cp docs/systemd-timer.example /etc/systemd/system/etsy-sevdesk-sync.timer
sudo systemctl enable etsy-sevdesk-sync.timer
sudo systemctl start etsy-sevdesk-sync.timer

# Status prüfen
systemctl status etsy-sevdesk-sync.timer
```

**Crontab:**

```cron
# Alle 15 Minuten neue Bestellungen
*/15 * * * * cd /opt/etsy-sevdesk && make sync-orders

# Täglich um 2 Uhr: Refunds und Payouts
0 2 * * * cd /opt/etsy-sevdesk && make sync-refunds && make sync-payouts

# Monatlich am 1. um 3 Uhr: Vormonats-Gebühren
0 3 1 * * cd /opt/etsy-sevdesk && make sync-fees period=$(date -d "last month" +%Y-%m)
```

**Celery Beat (in Docker bereits aktiv):**

Konfiguriere Schedules in `app/jobs/celery_app.py`:

```python
app.conf.beat_schedule = {
    'sync-orders-every-15-min': {
        'task': 'app.jobs.tasks.sync_orders',
        'schedule': crontab(minute='*/15'),
    },
}
```

### CLI-Befehle

```bash
# Synchronisations-Befehle
etsy-sync sync:orders --since 2024-01-01
etsy-sync sync:refunds --since 2024-01-01
etsy-sync sync:fees --period 2024-11
etsy-sync sync:payouts --since 2024-01-01

# Backfill
etsy-sync backfill:all

# GDPR
etsy-sync gdpr:export --email customer@example.com
etsy-sync gdpr:delete --email customer@example.com --confirm

# Wartung
etsy-sync maintenance:cleanup  # Alte Logs, abgelaufene Keys
etsy-sync maintenance:validate-config  # Konfiguration prüfen
```

---

## Architektur

```
┌─────────────┐         ┌─────────────┐
│  Etsy API   │◄────────┤ EtsyClient  │
└─────────────┘         └─────────────┘
                               │
                               ▼
                        ┌──────────────┐
                        │ Domain Layer │
                        │ - Tax Logic  │
                        │ - Invoice    │
                        │ - Refunds    │
                        └──────────────┘
                               │
                               ▼
                        ┌──────────────┐
                        │SevdeskClient │
                        └──────────────┘
                               │
                               ▼
                        ┌─────────────┐
                        │ sevDesk API │
                        └─────────────┘

         ┌────────────────────────────┐
         │     PostgreSQL DB          │
         │ - Orders, Invoices         │
         │ - Refunds, Payouts, Fees   │
         │ - Audit Log, Customers     │
         └────────────────────────────┘

         ┌────────────────────────────┐
         │     Redis                  │
         │ - Celery Broker            │
         │ - Idempotency Cache        │
         └────────────────────────────┘
```

### Komponenten

- **API Clients** (`app/clients/`): HTTP-Wrapper für Etsy & sevDesk mit Retry-Logik
- **Domain Services** (`app/domain/`): Geschäftslogik (Steuerberechnung, Invoice-Bau)
- **Jobs** (`app/jobs/`): Celery-Tasks und CLI-Commands
- **Database Models** (`app/db/`): SQLAlchemy 2.0 Models mit Alembic-Migrations
- **Core Utilities** (`app/core/`): Config, Logging, Time, Currency, Idempotency

---

## Entwicklung

### Setup

```bash
# Development-Dependencies
make install-dev

# Pre-commit Hooks
pre-commit install

# Tests ausführen
make test

# Code formatieren
make format

# Linter
make lint
```

### Tests

```bash
# Alle Tests
pytest

# Nur Unit-Tests
pytest app/tests/unit -v

# Mit Coverage
make test-cov
```

### Neue Migration erstellen

```bash
# Nach Änderungen an Models
make migration message="add payouts table"

# Migration anwenden
make migrate
```

### Development-Server

```bash
# API mit Hot-Reload
uvicorn app.api.main:app --reload --port 8000

# Celery Worker
celery -A app.jobs.celery_app worker --loglevel=INFO

# Flower (Celery Monitoring)
docker-compose --profile dev up flower
# → http://localhost:5555
```

---

## Sicherheit & DSGVO

### Secrets Management

- **Niemals** Credentials in Code oder Git committen
- Nutze `.env` mit restriktiven Permissions: `chmod 600 .env`
- Optional: Nutze externe Secret-Stores (HashiCorp Vault, AWS Secrets Manager)

### Verschlüsselung

Sensitive Daten in DB (Tokens) können verschlüsselt werden:

```bash
# Encryption Key generieren
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# In .env eintragen
ENCRYPTION_KEY=<generated_key>
```

### DSGVO-Compliance

- **PII-Minimierung**: Nur notwendige Kundendaten speichern
- **Maskierung**: E-Mails in Logs werden maskiert (wenn `MASK_CUSTOMER_DATA_IN_LOGS=true`)
- **Export**: `etsy-sync gdpr:export --email customer@example.com`
- **Löschung**: `etsy-sync gdpr:delete --email customer@example.com --confirm`

### GoBD-Compliance

- **Unveränderlichkeit**: Rechnungen werden in sevDesk erstellt und nicht mehr geändert
- **Aufbewahrungspflicht**: 10 Jahre (konfiguriert via `DOCUMENT_RETENTION_DAYS=3650`)
- **Vollständigkeit**: Audit-Log für alle Operationen
- **Nachvollziehbarkeit**: Jede Rechnung hat Verknüpfung zu Etsy-Bestellung

---

## Troubleshooting

### Problem: "Etsy API returns 401 Unauthorized"

**Lösung:**
```bash
# Refresh Token abgelaufen oder ungültig
# Neuen Token generieren:
python scripts/etsy_oauth.py
```

### Problem: "sevDesk Invoice creation fails with tax error"

**Lösung:**
- sevDesk Tax IDs in `config/tax_rules.json` prüfen
- `curl -H "Authorization: $SEVDESK_API_TOKEN" https://my.sevdesk.de/api/v1/Tax` → IDs abgleichen

### Problem: "Currency conversion fails"

**Lösung:**
```bash
# ECB-API prüfbar unter:
curl https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml

# Fallback: Manuelle Kurse
EXCHANGE_RATE_PROVIDER=manual
MANUAL_EXCHANGE_RATES='{"USD": 1.08, "GBP": 0.86}'
```

### Problem: "Duplicate invoices created"

**Lösung:**
- Idempotency funktioniert via In-Memory-Store
- Bei Worker-Restart gehen Idempotency-Keys verloren
- **Abhilfe**: Mapping-Tabelle in DB prüft `etsy_order_id → sevdesk_invoice_id`
- Doppelte werden automatisch erkannt und übersprungen

### Logs analysieren

```bash
# Docker Logs
docker-compose logs -f api
docker-compose logs -f worker

# Strukturierte JSON-Logs filtern
docker-compose logs api | jq 'select(.level == "ERROR")'

# Audit-Trail für bestimmte Order
grep "order_id=12345" /var/log/etsy-sevdesk/audit.log
```

---

## FAQ

**F: Unterstützt das Tool mehrere Etsy-Shops?**
A: Aktuell ein Shop pro Instanz. Für mehrere Shops: Separate Docker-Container mit eigenen `.env`-Dateien.

**F: Was passiert bei Teilrückerstattungen?**
A: Gutschriften werden proportional zur Rückerstattung erstellt. sevDesk bucht automatisch gegen die Original-Rechnung.

**F: Kann ich die Tool-generierte Rechnungsnummer ändern?**
A: Nein. sevDesk generiert die finale Rechnungsnummer beim "Buchen" (booking). Dies sichert GoBD-Konformität.

**F: Wie funktioniert OSS-Abrechnung?**
A: Tool erfasst OSS-Umsatzsteuer pro Land in sevDesk. Quartalsweise Abführung über OSS-Portal (BZSt) bleibt manuelle Aufgabe.

**F: Werden Etsy-Gebühren mit Vorsteuer abgebildet?**
A: Ja, wenn `KLEINUNTERNEHMER=false`. Gebühren enthalten 19% USt (oder länderspezifisch), die als Vorsteuer abziehbar ist.

**F: Kann ich das Tool testen ohne echte Rechnungen zu erstellen?**
A: Ja! Setze `DRY_RUN=true` in `.env` → Alle sevDesk-Schreiboperationen werden simuliert.

---

## Grenzen & Manuelle Eingriffe

Folgende Fälle erfordern **manuelle Bearbeitung**:

1. **B2B innerhalb EU mit USt-ID**
   - Etsy-Verkäufe sind primär B2C
   - Bei B2B: USt-ID prüfen, Reverse Charge anwenden
   - Manuelle Rechnungskorrektur in sevDesk

2. **Sonderkonstellationen**
   - Differenzbesteuerung (§25a UStG für Wiederverkäufer)
   - Kunstgegenstände
   - Grenzüberschreitende Dienstleistungen

3. **Stornierungen/Anpassungen**
   - Nachträgliche Rabatte
   - Teillieferungen mit Abschlagsrechnungen

4. **OSS-Schwellenwert-Überschreitung**
   - Bei Überschreitung 10.000 € muss OSS aktiviert werden
   - Tool prüft dies NICHT automatisch
   - Manuell in Tax-Config anpassen

---

## Weiterführende Dokumentation

- [MIGRATION_GUIDE.md](MIGRATION_GUIDE.md) - Datenbankänderungen und Upgrades
- [DEVELOPMENT.md](docs/DEVELOPMENT.md) - Architektur-Details
- [API.md](docs/API.md) - FastAPI-Endpoints Dokumentation
- [SECURITY.md](docs/SECURITY.md) - Security Best Practices

---

## Lizenz

MIT License - siehe [LICENSE](LICENSE)

---

## Support

Bei Fragen oder Problemen:

1. Prüfe [Troubleshooting](#troubleshooting) und [FAQ](#faq)
2. Logs analysieren (siehe oben)
3. GitHub Issues erstellen mit:
   - Logs (PII entfernt!)
   - Konfiguration (Secrets entfernt!)
   - Schritte zur Reproduktion

**WICHTIG:** Teile niemals API-Tokens, Refresh-Tokens oder Kundendaten öffentlich!

---

## Credits

Entwickelt von **Grizzly Simgineering** für deutsche E-Commerce-Händler mit Fokus auf Compliance und Zuverlässigkeit.

**Hinweis:** Dieses Tool ist KEIN Ersatz für professionelle Steuerberatung. Alle steuerlichen Einstellungen müssen mit einem Steuerberater abgestimmt werden.

---

**Version:** 1.0.0
**Letzte Aktualisierung:** 2025-11-09
