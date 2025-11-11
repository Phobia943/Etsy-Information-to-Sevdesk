# Etsy API Credentials Setup-Anleitung

Diese Anleitung zeigt dir Schritt für Schritt, wie du alle nötigen API-Credentials von Etsy erhältst.

---

## Übersicht: Was du brauchst

Für die Etsy-SevDesk-Synchronisation benötigst du folgende Credentials:

1. **API Key** (Keystring)
2. **Client Secret** (Shared Secret)
3. **Shop ID**
4. **OAuth2 Refresh Token**

---

## Schritt 1: Etsy Developer Account erstellen

### 1.1 Account registrieren

1. Gehe zu: https://www.etsy.com/developers/register
2. Logge dich mit deinem Etsy-Verkäufer-Account ein
3. Akzeptiere die **Etsy API Terms of Service**
4. Klicke auf **Register as a developer**

### 1.2 Wichtige Infos

- Du musst einen **aktiven Etsy-Shop** haben (als Verkäufer)
- Der Developer-Account ist **kostenlos**
- Die Registrierung dauert nur wenige Minuten

---

## Schritt 2: Etsy App erstellen

### 2.1 Neue App anlegen

1. Gehe zu: https://www.etsy.com/developers/your-apps
2. Klicke auf **Create a New App**
3. Fülle das Formular aus:

**App Name:**
```
Etsy-SevDesk-Sync (oder ein eigener Name)
```

**App Description:**
```
Private tool to sync Etsy orders to sevDesk accounting software
```

**Tell us about your App:**
- Wähle: **For personal use only**
- Beschreibe kurz: "Synchronize my Etsy shop orders with my accounting system"

**Will your app use the Etsy API?**
- Wähle: **Yes**

**What Etsy API Scopes do you need?**
Wähle folgende Scopes (Berechtigungen):
- ✅ `transactions_r` - Read access to transactions and listings
- ✅ `shops_r` - Read access to shops and listings
- ✅ `billing_r` - Read access to billing and payment information

4. Klicke auf **Read Terms and Create App**

---

## Schritt 3: API Credentials abrufen

Nach der App-Erstellung siehst du deine Credentials:

### 3.1 API Key (Keystring)

```
Wird angezeigt als: "Keystring"
Format: Beispiel - abcdef1234567890abcdef1234567890
```

**Wichtig:** Dies ist dein **API Key** - speichere ihn sicher!

### 3.2 Client Secret (Shared Secret)

```
Wird angezeigt als: "Shared Secret"
Format: Beispiel - abcdef1234567890
```

**Wichtig:** Dies ist dein **Client Secret** - wird nur einmal angezeigt!

💡 **Tipp:** Wenn du das Shared Secret verlierst, musst du es unter "Regenerate Secret" neu generieren.

---

## Schritt 4: Redirect URI konfigurieren

### 4.1 Callback URL hinzufügen

1. Scrolle in deiner App-Konfiguration zu **OAuth Redirect URIs**
2. Füge folgende URL hinzu:
```
http://localhost:8888/callback
```
3. Klicke auf **Add**
4. Klicke auf **Update** um zu speichern

**Warum?** Das Setup-Script startet einen lokalen Server, um den OAuth-Flow zu ermöglichen.

---

## Schritt 5: Shop ID finden

### 5.1 Methode 1: Über die URL

1. Gehe zu deinem Etsy-Shop
2. Schau dir die URL an:
```
https://www.etsy.com/shop/DeinShopName
```
3. Die **Shop ID** ist NICHT der Shop-Name!

### 5.2 Methode 2: Über die API (empfohlen)

Wir werden die Shop ID später mit dem Setup-Script automatisch abrufen.

Alternativ kannst du sie manuell abrufen:

1. Öffne: https://www.etsy.com/developers/documentation/getting_started/api_basics#section_shops
2. Nutze diesen API-Call (ersetze `{YOUR_API_KEY}` und `{SHOP_NAME}`):
```
https://openapi.etsy.com/v3/application/shops?shop_name={SHOP_NAME}
```

3. Die Response enthält:
```json
{
  "shop_id": 12345678,
  "shop_name": "DeinShopName"
}
```

---

## Schritt 6: OAuth2 Refresh Token erhalten

### 6.1 Automatisch mit Setup-Script (EMPFOHLEN)

Das Setup-Script (`python3 setup.py`) führt dich automatisch durch den OAuth-Flow:

1. Es öffnet deinen Browser
2. Du autorisierst die App auf Etsy
3. Das Script erhält automatisch den **Refresh Token**
4. Der Token wird sicher in der Config gespeichert

### 6.2 Was passiert beim OAuth-Flow?

```
1. Setup-Script startet lokalen Server (Port 8888)
   ↓
2. Browser öffnet Etsy Authorization URL
   ↓
3. Du loggst dich bei Etsy ein und autorisierst die App
   ↓
4. Etsy leitet dich zu http://localhost:8888/callback zurück
   ↓
5. Script empfängt den Authorization Code
   ↓
6. Script tauscht Code gegen Access + Refresh Token
   ↓
7. Refresh Token wird in config.yaml gespeichert
```

### 6.3 Refresh Token Details

- **Access Token:** Gültig für 1 Stunde
- **Refresh Token:** Gültig für 90 Tage
- Das Script erneuert den Access Token automatisch mit dem Refresh Token

---

## Schritt 7: Setup-Script ausführen

### 7.1 Vorbereitung

Stelle sicher, dass du hast:
- ✅ API Key (Keystring)
- ✅ Client Secret (Shared Secret)
- ✅ Shop Name (für Shop ID Lookup)

### 7.2 Setup starten

```bash
cd "/home/daniel/Claude/Grizzly Simgineering/Etsy-SevDesk-Sync"
source venv/bin/activate
python3 setup.py
```

### 7.3 Setup-Wizard

Der Wizard fragt dich nacheinander:

**1. Etsy API Keystring:**
```
Gib hier deinen API Key ein (aus Schritt 3.1)
```

**2. Etsy Shared Secret:**
```
Gib hier dein Client Secret ein (aus Schritt 3.2)
```

**3. Etsy Shop Name:**
```
Gib deinen Shop-Namen ein (z.B. "MeinShop")
Das Script ruft automatisch die Shop ID ab
```

**4. OAuth Authorization:**
```
- Browser öffnet sich automatisch
- Logge dich bei Etsy ein
- Klicke auf "Allow Access"
- Browser zeigt "Authorization successful!" → Kannst schließen
```

**5. Datenbank konfigurieren:**
```
Wähle: SQLite (empfohlen für private Nutzung)
```

**6. Logging-Level:**
```
Wähle: INFO (empfohlen)
```

### 7.4 Fertig!

Nach dem Setup:
- ✅ `config/config.yaml` wurde erstellt
- ✅ OAuth Refresh Token wurde gespeichert
- ✅ Datenbank wurde initialisiert

---

## Schritt 8: Erste Synchronisation testen

### 8.1 CSV Export durchführen

```bash
python3 run_sync.py export-csv --days 30
```

**Was passiert:**
- Lädt Bestellungen der letzten 30 Tage von Etsy
- Erstellt sevDesk-kompatible CSV-Dateien
- Speichert in `exports/` Verzeichnis

### 8.2 Export überprüfen

```bash
ls -lh exports/
```

Du solltest sehen:
- `rechnungen.csv` - Etsy-Bestellungen
- `gutschriften.csv` - Rückerstattungen
- `gebuehren.csv` - Etsy-Gebühren
- `import_anleitung.md` - Import-Anleitung für sevDesk
- `summary.txt` - Zusammenfassung

---

## Troubleshooting

### Problem: "Invalid API Key"

**Lösung:**
- Prüfe, ob du den **Keystring** (nicht Shared Secret) verwendet hast
- Stelle sicher, dass keine Leerzeichen am Anfang/Ende sind
- Regeneriere die Credentials in deiner Etsy App

### Problem: "OAuth authorization failed"

**Lösung:**
- Prüfe, ob die Redirect URI `http://localhost:8888/callback` in deiner App konfiguriert ist
- Stelle sicher, dass Port 8888 nicht von einer anderen App belegt ist
- Firewall könnte den lokalen Server blockieren

### Problem: "Shop not found"

**Lösung:**
- Prüfe die Schreibweise deines Shop-Namens
- Der Shop muss aktiv sein
- Nutze den exakten Shop-Namen (Case-sensitive)

### Problem: "Insufficient scope"

**Lösung:**
- Gehe zurück zu deiner Etsy App
- Füge die fehlenden Scopes hinzu:
  - `transactions_r`
  - `shops_r`
  - `billing_r`
- Führe den OAuth-Flow erneut aus (`python3 setup.py`)

---

## Sicherheitshinweise

### ⚠️ Credentials geheim halten!

**NIEMALS committen:**
```
config/config.yaml          ← Enthält API Keys und Tokens
.env                         ← Enthält Secrets
```

**Bereits in .gitignore:**
```gitignore
config/config.yaml
config/*.yaml
.env
*.log
```

### 🔒 Refresh Token erneuern

Der Refresh Token läuft nach 90 Tagen ab. Wenn das passiert:

1. Führe `python3 setup.py` erneut aus
2. Durchlaufe den OAuth-Flow erneut
3. Neuer Refresh Token wird gespeichert

**Tipp:** Nutze die App regelmäßig (mindestens alle 2 Monate), dann wird der Token automatisch erneuert.

---

## Zusammenfassung: Alle Credentials

| Credential | Wo finden? | Beispiel |
|------------|-----------|----------|
| **API Key** | Etsy App → Keystring | `abcd1234...` (32 Zeichen) |
| **Client Secret** | Etsy App → Shared Secret | `abcd1234...` (16 Zeichen) |
| **Shop ID** | Auto via API | `12345678` |
| **Refresh Token** | Auto via OAuth | `ey...` (JWT Token) |

---

## Weiterführende Links

- **Etsy Developer Portal:** https://www.etsy.com/developers
- **Etsy API Documentation:** https://developers.etsy.com/documentation
- **OAuth 2.0 Guide:** https://developers.etsy.com/documentation/essentials/authentication
- **API Scopes:** https://developers.etsy.com/documentation/essentials/authentication#scopes

---

## Support

Bei Problemen:

1. Prüfe `logs/` Verzeichnis für detaillierte Fehlermeldungen
2. Konsultiere die Etsy API Dokumentation
3. Erstelle ein Issue auf GitHub: https://github.com/Phobia943/Etsy-Information-to-Sevdesk/issues

---

**Viel Erfolg mit der Einrichtung! 🚀**
