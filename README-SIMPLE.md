# Etsy-SevDesk Sync - Quick Start Guide

Ein einfaches CLI-Tool zur Synchronisation von Etsy-Bestellungen mit sevDesk für private Nutzung.

## Überblick

Dieses Tool synchronisiert:
- ✅ Etsy-Bestellungen → sevDesk Rechnungen
- ✅ Automatische Steuerberechnung (Inland, EU, Drittland)
- ✅ OSS (One-Stop-Shop) Support für EU-Verkäufe
- ✅ Kleinunternehmer-Regelung (§19 UStG)
- ✅ Etsy-Gebühren → sevDesk Belege
- ✅ Gutschriften für Rückerstattungen

## Voraussetzungen

- Python 3.11 oder höher
- Etsy Shop mit API-Zugang
- sevDesk Account mit API-Token
- Linux, macOS oder Windows (WSL)

## Installation

### 1. Repository klonen oder herunterladen

```bash
cd /pfad/zu/deinem/projekt
```

### 2. Virtual Environment erstellen (empfohlen)

```bash
python3 -m venv venv
source venv/bin/activate  # Linux/macOS
# oder: venv\Scripts\activate  # Windows
```

### 3. Dependencies installieren

```bash
pip install -r requirements-simple.txt
```

## Erstmalige Einrichtung

### Schritt 1: Etsy API Credentials erstellen

1. Gehe zu: https://www.etsy.com/developers/your-apps
2. Erstelle eine neue App oder wähle eine bestehende
3. Notiere dir:
   - **Keystring** (Client ID)
   - **Shared Secret** (Client Secret)
   - **Shop ID** (numerisch, findest du in deinen Shop-Einstellungen)

#### OAuth2 Refresh Token erhalten

Der Refresh Token ermöglicht dauerhaften API-Zugriff ohne erneute Anmeldung.

**Option A: Über Etsy Developer Tools** (empfohlen)
1. Nutze das Etsy OAuth2 Playground: https://www.etsy.com/developers/documentation/getting_started/oauth
2. Authorisiere deine App mit allen benötigten Scopes:
   - `shops_r` (Shop-Infos lesen)
   - `transactions_r` (Bestellungen lesen)
   - `listings_r` (Artikel lesen)
3. Kopiere den **Refresh Token** (wird nur einmal angezeigt!)

**Option B: Manuell mit curl**
```bash
# 1. Authorization Code erhalten (öffne im Browser):
https://www.etsy.com/oauth/connect?response_type=code&client_id=DEIN_CLIENT_ID&redirect_uri=urn:ietf:wg:oauth:2.0:oob&scope=shops_r%20transactions_r%20listings_r&state=RANDOM_STRING&code_challenge=CHALLENGE&code_challenge_method=S256

# 2. Nach Autorisierung erhältst du einen Code
# 3. Tausche den Code gegen Refresh Token:
curl -X POST https://api.etsy.com/v3/public/oauth/token \
  -d "grant_type=authorization_code" \
  -d "client_id=DEIN_CLIENT_ID" \
  -d "code=DEIN_CODE" \
  -d "code_verifier=VERIFIER" \
  -d "redirect_uri=urn:ietf:wg:oauth:2.0:oob"
```

Mehr Details: https://www.etsy.com/developers/documentation/getting_started/oauth

### Schritt 2: sevDesk API Token erstellen

1. Gehe zu: https://my.sevdesk.de/#/admin/userManagement
2. Klicke auf deinen Benutzer
3. Scrolle zu "API Token"
4. Erstelle einen neuen Token
5. **Wichtig:** Kopiere den Token sofort (wird nur einmal angezeigt!)

### Schritt 3: Interaktives Setup ausführen

```bash
python3 setup.py
```

Das Setup-Tool fragt dich nach:
- ✅ Etsy API Credentials
- ✅ sevDesk API Token
- ✅ Steuer-Einstellungen (Kleinunternehmer, OSS)
- ✅ Sync-Einstellungen
- ✅ Datenbank-Pfad

Die Konfiguration wird in `config/local.yaml` gespeichert (nicht in Git).

## Verwendung

### Option 1: CSV-Export (OHNE sevDesk API)

**Für Nutzer OHNE sevDesk Pro-Tarif (49€/Monat):**

Der CSV-Export erstellt sevDesk-kompatible CSV-Dateien, die du manuell importieren kannst.

```bash
# CSV-Export der letzten 30 Tage
python3 run_sync.py export-csv

# CSV-Export der letzten 60 Tage
python3 run_sync.py export-csv --days 60

# CSV-Export mit Datumsbereich
python3 run_sync.py export-csv --from 2024-01-01 --to 2024-12-31

# Export ohne Gebühren
python3 run_sync.py export-csv --include-fees=false

# Export ohne Bestätigung (für Automatisierung)
python3 run_sync.py export-csv --yes
```

**Was wird exportiert?**

Der Export erstellt ein Verzeichnis `exports/YYYY-MM-DD_HH-MM/` mit:
- `rechnungen.csv` - Alle Bestellungen als Rechnungen
- `gutschriften.csv` - Rückerstattungen als Gutschriften
- `gebuehren.csv` - Etsy-Gebühren als Ausgabenbelege
- `import_anleitung.md` - Schritt-für-Schritt Import-Anleitung
- `summary.txt` - Zusammenfassung der exportierten Daten

**Import in sevDesk:**
1. Öffne die Datei `import_anleitung.md` im Export-Verzeichnis
2. Folge den detaillierten Schritten
3. Importiere die CSV-Dateien über sevDesk UI

**CSV-Format:**
- UTF-8 mit BOM (Excel-kompatibel)
- Semikolon-Separator (`;`)
- Deutsches Zahlenformat (Komma als Dezimaltrenner)
- Deutsches Datumsformat (DD.MM.YYYY)

---

### Option 2: Automatische Synchronisation (MIT sevDesk API)

**Für Nutzer MIT sevDesk Pro-Tarif:**

#### Erster Sync (Dry-Run)

Teste erst ohne echte Buchungen:

```bash
python3 run_sync.py --dry-run
```

Das zeigt dir, was synchronisiert würde, ohne tatsächlich in sevDesk zu buchen.

#### Produktiv-Sync starten

```bash
python3 run_sync.py
```

Synchronisiert alle neuen Bestellungen seit dem letzten Sync.

#### Weitere Optionen

```bash
# Nur Gebühren synchronisieren
python3 run_sync.py --fees-only

# Bestellungen ab einem bestimmten Datum
python3 run_sync.py --from 2024-01-01

# Letzte 30 Tage neu synchronisieren
python3 run_sync.py --days 30

# Status des letzten Syncs anzeigen
python3 run_sync.py status

# Hilfe anzeigen
python3 run_sync.py --help
```

### Regelmäßiger Sync

Für automatischen Sync kannst du einen Cronjob einrichten:

```bash
# Crontab bearbeiten
crontab -e

# Jeden Tag um 8:00 Uhr synchronisieren
0 8 * * * cd /pfad/zum/projekt && /pfad/zum/venv/bin/python3 run_sync.py >> logs/cron.log 2>&1
```

## Konfiguration anpassen

Die Konfiguration findest du in `config/local.yaml`. Du kannst sie jederzeit manuell bearbeiten:

```bash
nano config/local.yaml
# oder
vim config/local.yaml
```

### Wichtige Einstellungen

```yaml
# Kleinunternehmer (keine USt ausweisen)
tax:
  is_small_business: false  # true = Kleinunternehmer
  use_oss: true             # OSS für EU-Verkäufe

# Sync-Verhalten
sync:
  auto_create_invoices: true      # Rechnungen automatisch erstellen
  sync_fees: true                 # Gebühren synchronisieren
  auto_process_refunds: true      # Gutschriften für Rückerstattungen

# Dry-Run Modus (global)
app:
  dry_run: false  # true = nur simulieren
```

## Steuer-Hinweise

### Kleinunternehmer (§19 UStG)

Wenn du Kleinunternehmer bist:
- Setze `tax.is_small_business: true`
- Keine Umsatzsteuer wird auf Rechnungen ausgewiesen
- Hinweis nach §19 UStG wird automatisch hinzugefügt

### One-Stop-Shop (OSS)

Wenn du OSS nutzt:
- Setze `tax.use_oss: true`
- EU-Verkäufe werden mit der Steuer des Bestimmungslandes berechnet
- Keine Reverse-Charge für B2C-Verkäufe innerhalb der EU

### Kontenrahmen

Das Tool unterstützt:
- **SKR03** (Standard für die meisten Unternehmen)
- **SKR04** (Alternative)

## Datenbank

Standardmäßig wird SQLite verwendet (`./data/etsy_sevdesk.db`).

**Vorteile:**
- ✅ Keine Installation nötig
- ✅ Datei-basiert, einfach zu sichern
- ✅ Ausreichend für persönliche Nutzung

**Backup erstellen:**
```bash
cp data/etsy_sevdesk.db data/backup_$(date +%Y%m%d).db
```

## Logs

Logs werden gespeichert in:
- Konsole (während der Ausführung)
- `logs/sync_YYYY-MM-DD.log` (optional, konfigurierbar)

Bei Fehlern findest du hier detaillierte Informationen.

## Fehlerbehandlung

### "Konfiguration nicht gefunden"
→ Führe `python3 setup.py` aus

### "Etsy API Authentication Failed"
→ Prüfe deine Etsy Credentials in `config/local.yaml`
→ Refresh Token könnte abgelaufen sein (neu generieren)

### "sevDesk API Error 401"
→ Prüfe deinen sevDesk API Token
→ Token könnte abgelaufen oder ungültig sein

### "Database Locked"
→ Stelle sicher, dass nicht mehrere Sync-Prozesse gleichzeitig laufen
→ Bei SQLite: nur ein Schreibzugriff gleichzeitig möglich

## Verzeichnisstruktur

```
etsy-sevdesk-sync/
├── run_sync.py              # Haupt-Script (CLI)
├── setup.py                 # Interaktives Setup
├── requirements-simple.txt  # Dependencies
├── config/
│   ├── config.yaml          # Template (committed)
│   └── local.yaml           # Deine Konfiguration (gitignored)
├── data/
│   └── etsy_sevdesk.db     # SQLite Datenbank
├── logs/                    # Log-Dateien
├── storage/                 # Dokumente (Gebühren-PDFs)
└── app/                     # Backend-Code
    ├── clients/             # API-Clients (Etsy, sevDesk)
    ├── core/                # Core-Funktionen
    ├── db/                  # Datenbank-Models
    └── ...
```

## Sicherheit

### Credentials schützen

- ⚠️ **NIEMALS** `config/local.yaml` zu Git committen!
- ⚠️ API Tokens sind sensibel wie Passwörter
- ✅ Nutze die Encryption (wird automatisch eingerichtet)
- ✅ Sichere regelmäßig die Datenbank

### Empfohlene Berechtigungen

```bash
chmod 600 config/local.yaml  # Nur Owner kann lesen/schreiben
chmod 700 data/              # Nur Owner kann zugreifen
```

## Upgrade auf Full-Version

Wenn du später auf die Full-Version mit Server/Docker wechseln möchtest:

1. Installiere die vollständigen Dependencies: `pip install -r requirements.txt`
2. Richte Docker/PostgreSQL ein: `docker-compose up -d`
3. Migriere die Daten: Die SQLite-DB kann zu PostgreSQL migriert werden
4. Nutze die FastAPI-Server-Version

Siehe: `README.md` für Details

## Support & Dokumentation

- **Vollständige Dokumentation:** Siehe `README.md`
- **Migrations-Guide:** Siehe `MIGRATION_GUIDE.md`
- **Etsy API Docs:** https://developers.etsy.com/documentation
- **sevDesk API Docs:** https://api.sevdesk.de/

## Lizenz

Siehe `LICENSE` Datei.

## Troubleshooting

### Import-Fehler

```bash
# Stelle sicher, dass du im richtigen Verzeichnis bist
cd /pfad/zum/Etsy-SevDesk-Sync

# Virtual Environment aktivieren
source venv/bin/activate

# Dependencies neu installieren
pip install --upgrade -r requirements-simple.txt
```

### Datenbank-Fehler

```bash
# Datenbank neu initialisieren (ACHTUNG: Löscht alle Daten!)
rm data/etsy_sevdesk.db
python3 run_sync.py  # Erstellt DB neu
```

### Performance-Probleme

Bei vielen Bestellungen:
- Sync in kleineren Zeitfenstern: `--days 7` statt ganzer Historie
- Batch-Größe anpassen in `config/local.yaml`: `sync.batch_size: 50`
- Für große Datenmengen: Upgrade zu PostgreSQL

## Häufige Fragen (FAQ)

**Q: Brauche ich den sevDesk Pro-Tarif?**
A: Nein! Nutze den CSV-Export (`export-csv` Command), um Daten manuell zu importieren. Die API-basierte Sync benötigt Pro.

**Q: Was ist der Unterschied zwischen CSV-Export und automatischem Sync?**
A:
- **CSV-Export:** Keine sevDesk API nötig, manueller Import über sevDesk UI, kostenlos nutzbar
- **Automatischer Sync:** sevDesk Pro API erforderlich (49€/Monat), vollautomatisch, keine manuelle Arbeit

**Q: Kann ich mehrere Etsy-Shops synchronisieren?**
A: Aktuell nur ein Shop pro Konfiguration. Für mehrere Shops: Separates Verzeichnis mit eigener Config.

**Q: Werden bestehende Rechnungen aktualisiert?**
A: Nein, einmal erstellte Rechnungen werden nicht geändert (GoBD-konform).

**Q: Was passiert bei Rückerstattungen?**
A: Automatisch werden Gutschriften erstellt (wenn aktiviert) bzw. im CSV-Export als `gutschriften.csv` bereitgestellt.

**Q: Kann ich den Sync rückgängig machen?**
A: Nein - teste immer erst mit `--dry-run`! In sevDesk musst du Rechnungen manuell löschen. Beim CSV-Export: Prüfe die Daten vor dem Import.

**Q: Kostet das Tool etwas?**
A: Nein, das Tool ist kostenlos. Du brauchst nur Etsy + sevDesk Accounts.

---

**Viel Erfolg mit der Synchronisation!** 🚀

Bei Fragen oder Problemen: Siehe Issues im Repository oder erweitere das Tool selbst.
