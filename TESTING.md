# Testing Guide - Etsy-SevDesk Sync CLI

Diese Anleitung hilft dir, das CLI-Tool zu testen, bevor du es produktiv nutzt.

## Quick Test (5 Minuten)

### 1. Dependencies installieren

```bash
cd "/home/daniel/Claude/Grizzly Simgineering/Etsy-SevDesk-Sync"

# Virtual Environment (empfohlen)
python3 -m venv venv
source venv/bin/activate

# Dependencies
pip install -r requirements-simple.txt
```

### 2. Setup testen

```bash
# Interaktives Setup starten
python3 setup.py
```

**Was getestet wird:**
- ✅ Alle Dependencies vorhanden
- ✅ YAML-Parsing funktioniert
- ✅ Rich Terminal-Output funktioniert
- ✅ Konfigurationsdatei wird erstellt

**Erwartetes Ergebnis:**
- Datei `config/local.yaml` wird erstellt
- Verzeichnis `data/` wird erstellt
- Keine Python-Fehler

**Test-Credentials:** Du kannst beim Setup dummy-Werte eingeben zum Testen:
- Etsy Client ID: `test123`
- Etsy Client Secret: `secret123`
- Shop ID: `12345678`
- Refresh Token: `refresh_test`
- sevDesk Token: `sevdesk_test`

### 3. Config-Datei prüfen

```bash
cat config/local.yaml
```

**Prüfe:**
- ✅ Alle eingegebenen Werte sind vorhanden
- ✅ YAML-Struktur ist korrekt
- ✅ Encryption Key wurde generiert

### 4. CLI testen (ohne API-Calls)

```bash
# Hilfe anzeigen
python3 run_sync.py --help

# Status-Command (nutzt nur Datenbank)
python3 run_sync.py status
```

**Erwartetes Ergebnis:**
```
Sync Status
━━━━━━━━━━━━━━

Noch kein Sync durchgeführt

Bestellungen in DB: 0
Rechnungen erstellt: 0
```

**Was getestet wird:**
- ✅ CLI startet ohne Fehler
- ✅ Config wird geladen
- ✅ SQLite DB wird erstellt
- ✅ Typer/Rich funktioniert

## Unit-Tests

### Test 1: Config Loading

```bash
python3 -c "
import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))

from run_sync import load_config
config = load_config()
print('✓ Config geladen')
print(f'  Etsy Shop ID: {config[\"etsy\"][\"shop_id\"]}')
print(f'  Database: {config[\"database\"][\"url\"]}')
"
```

### Test 2: Database Initialization

```bash
python3 -c "
import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))

from run_sync import load_config, init_database
config = load_config()
init_database(config['database']['url'])
print('✓ Datenbank initialisiert')

# Check if tables exist
from sqlalchemy import create_engine, inspect
engine = create_engine(config['database']['url'])
inspector = inspect(engine)
tables = inspector.get_table_names()
print(f'  Tabellen: {len(tables)}')
print(f'  {tables}')
"
```

**Erwartete Tabellen:**
- `integration_state`
- `orders`
- `invoices`
- `refunds`
- `payouts`
- `fees`
- `customers`
- `audit_log`

### Test 3: Environment Setup

```bash
python3 -c "
import sys
import os
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))

from run_sync import load_config, setup_environment
config = load_config()
setup_environment(config)

print('✓ Environment-Variablen gesetzt')
print(f'  ETSY_CLIENT_ID: {os.environ.get(\"ETSY_CLIENT_ID\", \"NICHT GESETZT\")}')
print(f'  SEVDESK_API_TOKEN: {os.environ.get(\"SEVDESK_API_TOKEN\", \"NICHT GESETZT\")}')
print(f'  DATABASE_URL: {os.environ.get(\"DATABASE_URL\", \"NICHT GESETZT\")}')
"
```

## Integration Tests (erfordert echte Credentials)

### Test 4: Etsy API Connection

**Voraussetzung:** Echte Etsy Credentials in `config/local.yaml`

```bash
python3 -c "
import sys
import asyncio
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))

from run_sync import load_config, setup_environment
from app.clients.etsy_client import EtsyClient

config = load_config()
setup_environment(config)

async def test():
    client = EtsyClient()
    try:
        shop = await client.get_shop()
        print('✓ Etsy API Verbindung erfolgreich')
        print(f'  Shop: {shop}')
    except Exception as e:
        print(f'✗ Etsy API Fehler: {e}')

asyncio.run(test())
"
```

### Test 5: sevDesk API Connection

**Voraussetzung:** Echter sevDesk Token in `config/local.yaml`

```bash
python3 -c "
import sys
import asyncio
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))

from run_sync import load_config, setup_environment
from app.clients.sevdesk_client import SevdeskClient

config = load_config()
setup_environment(config)

async def test():
    client = SevdeskClient()
    try:
        # Test API call - get contacts
        response = await client.get('/Contact', params={'limit': 1})
        print('✓ sevDesk API Verbindung erfolgreich')
        print(f'  Response: {response}')
    except Exception as e:
        print(f'✗ sevDesk API Fehler: {e}')

asyncio.run(test())
"
```

### Test 6: Dry-Run Sync

**Voraussetzung:** Echte Credentials

```bash
python3 run_sync.py --dry-run --from 2024-11-01
```

**Was passiert:**
- Etsy API wird abgefragt
- Bestellungen werden abgerufen
- Steuern werden berechnet
- **ABER:** Keine Rechnungen in sevDesk erstellt
- Keine Datenbank-Änderungen (außer Log)

**Erwartetes Ergebnis:**
```
Etsy-SevDesk Sync
DRY RUN Modus
━━━━━━━━━━━━━━━━━━━

✓ Konfiguration geladen
Initialisiere Datenbank...
✓ Datenbank bereit
Initialisiere API-Clients...
✓ API-Clients bereit

Starte Synchronisation...

Synchronisiere Bestellungen ab 2024-11-01...
Hole Etsy-Bestellungen... ━━━━━━━━━━━━━ 100%

Sync Ergebnisse
┏━━━━━━━━━━━━━━━━━━━━┳━━━━━━┓
┃ Metrik              ┃ Wert ┃
┡━━━━━━━━━━━━━━━━━━━━╇━━━━━━┩
│ Bestellungen        │ 42   │
│ Neue Bestellungen   │ 15   │
│ Rechnungen erstellt │ 0    │
│ Fehler              │ 0    │
└─────────────────────┴──────┘

DRY RUN: Keine Änderungen wurden in sevDesk vorgenommen
```

## Fehlerbehandlung testen

### Test 7: Fehlende Config

```bash
# Config umbenennen
mv config/local.yaml config/local.yaml.backup

# CLI ausführen
python3 run_sync.py

# Erwartete Fehlermeldung:
# ERROR: Konfiguration nicht gefunden!
# Erwarteter Pfad: /pfad/zu/config/local.yaml
#
# Bitte führe zuerst das Setup aus:
#   python3 setup.py

# Config wiederherstellen
mv config/local.yaml.backup config/local.yaml
```

### Test 8: Ungültige Credentials

```bash
# Temporär ungültige Credentials setzen
python3 -c "
import yaml
with open('config/local.yaml', 'r') as f:
    config = yaml.safe_load(f)

config['etsy']['client_id'] = 'INVALID'

with open('config/local.yaml.test', 'w') as f:
    yaml.dump(config, f)
"

# Test mit ungültigen Credentials
# (Hinweis: Funktioniert nur wenn du die Config-Datei manuell änderst)
```

## Performance Tests

### Test 9: Batch Processing

```bash
# Test mit vielen Bestellungen (letzte 90 Tage)
time python3 run_sync.py --dry-run --days 90
```

**Beobachte:**
- Laufzeit
- Speicherverbrauch
- Fehlerrate

### Test 10: Database Performance

```bash
# Fülle DB mit Test-Daten
python3 -c "
import sys
from pathlib import Path
from datetime import datetime, timedelta
from decimal import Decimal
sys.path.insert(0, str(Path.cwd()))

from run_sync import load_config
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app.db.models import Order

config = load_config()
engine = create_engine(config['database']['url'])
session = Session(engine)

# 1000 Test-Bestellungen
for i in range(1000):
    order = Order(
        etsy_order_id=f'test_{i}',
        raw_data={},
        status='paid',
        buyer_country='DE',
        buyer_email=f'test{i}@example.com',
        currency='EUR',
        total_amount=Decimal('99.99'),
        tax_amount=Decimal('19.00'),
        etsy_created_at=datetime.now() - timedelta(days=i),
        etsy_updated_at=datetime.now()
    )
    session.add(order)

session.commit()
print('✓ 1000 Test-Bestellungen erstellt')
"

# Query-Performance testen
python3 run_sync.py status
```

## Cleanup

Nach dem Testen:

```bash
# Test-Datenbank löschen
rm data/etsy_sevdesk.db

# Test-Config löschen (falls mit Test-Daten erstellt)
rm config/local.yaml

# Virtual Environment deaktivieren
deactivate
```

## Checklist für produktiven Einsatz

Bevor du das Tool produktiv nutzt:

- [ ] Setup erfolgreich durchgeführt
- [ ] Echte Etsy Credentials eingetragen
- [ ] Etsy Refresh Token generiert und getestet
- [ ] sevDesk API Token eingetragen und getestet
- [ ] Steuer-Einstellungen korrekt (Kleinunternehmer, OSS)
- [ ] Kontenrahmen korrekt (SKR03/SKR04)
- [ ] Dry-Run erfolgreich durchgeführt
- [ ] Erste Rechnung manuell in sevDesk geprüft
- [ ] Backup-Strategie für Datenbank festgelegt
- [ ] `config/local.yaml` ist in `.gitignore` (nicht committen!)
- [ ] Log-Dateien funktionieren
- [ ] Fehlerbehandlung getestet

## Nächste Schritte

Nach erfolgreichem Testing:

1. **Erster produktiver Sync:**
   ```bash
   python3 run_sync.py --from 2024-11-01
   ```

2. **Rechnungen in sevDesk prüfen:**
   - Sind alle Positionen korrekt?
   - Stimmen die Steuern?
   - Ist der Kunde korrekt angelegt?

3. **Regelmäßigen Sync einrichten:**
   ```bash
   crontab -e
   # 0 8 * * * cd /pfad/zum/projekt && venv/bin/python3 run_sync.py
   ```

4. **Monitoring einrichten:**
   - Log-Dateien regelmäßig prüfen
   - Backup der Datenbank
   - Fehler-Benachrichtigungen

---

**Viel Erfolg beim Testing!** 🧪

Bei Fragen oder Problemen: Siehe README-SIMPLE.md oder README.md
