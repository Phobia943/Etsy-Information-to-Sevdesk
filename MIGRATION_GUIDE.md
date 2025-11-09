# Migration Guide

Leitfaden für Datenbank-Migrationen und Version-Upgrades.

---

## Datenbank-Migrationen mit Alembic

### Neue Migration erstellen

Nach Änderungen an SQLAlchemy-Models:

```bash
# Automatische Migration generieren
make migration message="add new field to invoices"

# Oder direkt mit Alembic
alembic revision --autogenerate -m "add new field to invoices"
```

**Wichtig:** Prüfe die generierte Migration in `alembic/versions/` und passe sie ggf. an!

### Migration anwenden

```bash
# Alle pending Migrations
make migrate

# Oder mit Alembic
alembic upgrade head

# Zu spezifischer Revision
alembic upgrade <revision_id>
```

### Migration rückgängig machen

```bash
# Eine Revision zurück
make downgrade

# Oder mit Alembic
alembic downgrade -1

# Zu spezifischer Revision
alembic downgrade <revision_id>

# Alles zurücksetzen (ACHTUNG: Datenverlust!)
alembic downgrade base
```

### Aktuelle Version anzeigen

```bash
alembic current
alembic history
```

---

## Geplante Schema-Änderungen

### Version 1.1.0 (geplant)

**Neue Features:**
- Multi-Shop-Support
- Erweiterte Webhook-Integration
- Performance-Optimierungen

**Schema-Änderungen:**

```sql
-- Neue Tabelle: shops
CREATE TABLE shops (
    id SERIAL PRIMARY KEY,
    etsy_shop_id VARCHAR(100) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Orders-Tabelle erweitern
ALTER TABLE orders ADD COLUMN shop_id INTEGER REFERENCES shops(id);

-- Index für Performance
CREATE INDEX idx_orders_shop_created ON orders(shop_id, created_at);
```

**Migration erstellen:**

```bash
alembic revision -m "add multi shop support"
```

**Upgrade-Path:**

1. Backup erstellen: `make backup`
2. Migration anwenden: `make migrate`
3. Default-Shop anlegen: `python scripts/create_default_shop.py`
4. Bestehende Orders zuordnen: `UPDATE orders SET shop_id = 1 WHERE shop_id IS NULL;`

---

## Version-Upgrades

### Von 1.0.0 zu 1.1.0

#### Vorbereitung

```bash
# 1. Backup erstellen
make backup

# 2. Docker-Container stoppen
docker-compose down

# 3. Code aktualisieren
git pull
# oder: neues Release-Archive entpacken
```

#### Durchführung

```bash
# 1. Dependencies aktualisieren
pip install -r requirements.txt

# oder mit Docker:
docker-compose build --no-cache

# 2. Datenbank migrieren
make migrate

# 3. Services neu starten
docker-compose up -d

# 4. Logs prüfen
docker-compose logs -f
```

#### Rollback (falls Probleme auftreten)

```bash
# 1. Services stoppen
docker-compose down

# 2. Code zurück zur alten Version
git checkout v1.0.0

# 3. Datenbank zurück migrieren
alembic downgrade <previous_revision>

# 4. Backup wiederherstellen (falls nötig)
make restore file=backup_<timestamp>.sql

# 5. Services starten
docker-compose up -d
```

---

## Datenbank-Backup & Restore

### Backup erstellen

```bash
# Via Makefile (empfohlen)
make backup

# Manuell mit pg_dump
docker-compose exec postgres pg_dump -U etsy_sync etsy_sevdesk > backups/manual_backup.sql

# Mit Zeitstempel
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
docker-compose exec postgres pg_dump -U etsy_sync etsy_sevdesk > backups/backup_${TIMESTAMP}.sql
```

### Backup wiederherstellen

```bash
# Via Makefile
make restore file=backup_20250109_120000.sql

# Manuell
docker-compose exec -T postgres psql -U etsy_sync etsy_sevdesk < backups/backup_20250109_120000.sql
```

### Automatisches Backup

**Crontab einrichten:**

```cron
# Täglich um 3 Uhr
0 3 * * * cd /opt/etsy-sevdesk && make backup

# Alte Backups löschen (älter als 30 Tage)
0 4 * * * find /opt/etsy-sevdesk/backups -name "*.sql" -mtime +30 -delete
```

---

## Daten-Migration zwischen Umgebungen

### Von Development zu Production

```bash
# 1. Dev-Daten exportieren
pg_dump -U dev_user dev_db > dev_export.sql

# 2. Sensitive Daten anonymisieren (optional)
sed -i 's/real@email.com/anonymized@example.com/g' dev_export.sql

# 3. In Production importieren
psql -U prod_user prod_db < dev_export.sql
```

### Partielle Migration (nur bestimmte Tabellen)

```bash
# Nur configuration-Tabellen
pg_dump -U user -t integration_state -t customers etsy_sevdesk > config_export.sql

# Importieren
psql -U user etsy_sevdesk < config_export.sql
```

---

## Breaking Changes

Dokumentation von Breaking Changes zwischen Versionen.

### Version 1.0.0

**Initiales Release** - keine Breaking Changes.

### Version 1.1.0 (geplant)

**Breaking Changes:**
- Environment-Variable `ETSY_SHOP_ID` wird zu `ETSY_DEFAULT_SHOP_ID`
- API-Endpoint `/api/sync` wird zu `/api/v1/sync`

**Migration:**
```bash
# .env anpassen
sed -i 's/ETSY_SHOP_ID/ETSY_DEFAULT_SHOP_ID/g' .env

# API-Clients aktualisieren (falls external)
# /api/sync → /api/v1/sync
```

---

## Troubleshooting Migrations

### Problem: "Multiple heads detected"

**Ursache:** Mehrere parallele Migrations ohne gemeinsamen Parent.

**Lösung:**
```bash
# Heads anzeigen
alembic heads

# Merge-Migration erstellen
alembic merge -m "merge multiple heads" <rev1> <rev2>

# Anwenden
alembic upgrade head
```

### Problem: "Can't locate revision"

**Ursache:** Migration-File fehlt oder beschädigt.

**Lösung:**
```bash
# Alembic-Versionen-Tabelle prüfen
psql -U etsy_sync -d etsy_sevdesk -c "SELECT * FROM alembic_version;"

# Ggf. manuell korrigieren
psql -U etsy_sync -d etsy_sevdesk -c "UPDATE alembic_version SET version_num='<correct_revision>';"
```

### Problem: "Foreign key constraint violation"

**Ursache:** Abhängigkeiten zwischen Tabellen nicht berücksichtigt.

**Lösung:**
```bash
# Migration anpassen: Reihenfolge der Operationen
# Zuerst: Constraints entfernen
op.drop_constraint('fk_name', 'table_name')

# Dann: Tabelle ändern
op.alter_column(...)

# Zuletzt: Constraint wieder hinzufügen
op.create_foreign_key('fk_name', ...)
```

---

## Checkliste für Production-Migration

- [ ] **Backup erstellt** (`make backup`)
- [ ] **Wartungsfenster kommuniziert** (Downtime ca. 5-15 Min)
- [ ] **Services gestoppt** (`docker-compose down`)
- [ ] **Code aktualisiert** (Git Pull / Release-Archive)
- [ ] **Dependencies installiert** (`pip install -r requirements.txt`)
- [ ] **Migration getestet** (in Staging-Umgebung)
- [ ] **Migration angewendet** (`make migrate`)
- [ ] **Logs geprüft** (keine Fehler)
- [ ] **Services gestartet** (`docker-compose up -d`)
- [ ] **Health-Check** (`curl http://localhost:8000/health`)
- [ ] **Funktionstest** (Sync-Job probeweise ausführen)
- [ ] **Monitoring prüfen** (Celery, API-Logs)
- [ ] **Rollback-Plan bereit** (Backup, alte Version)

---

## Kontakt

Bei Fragen zu Migrationen: Siehe README.md → Support.
