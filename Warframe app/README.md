# Warframe Companion Blueprint

Ein Python-Prototyp fuer eine Warframe-Desktop-App im Stil von AlecaFrame.
Die aktuelle Version enthaelt jetzt auch eine aus deinen PDF-Notizen abgeleitete Build-Struktur, einen Live-Worldstate-Client, einen SQLite-Cache, einen Import fuer dein Vosfor-Sheet und eine echte `warframe.market`-Anbindung fuer `ingame`-Sell-Orders, Bilder, Whisper-Texte und Closed-Trade-Statistiken.

## Was schon drin ist

- Desktop-UI mit `tkinter`
- Live-Worldstate aus `warframestat.us`
- lokaler SQLite-Cache fuer API- und Importdaten
- Vosfor-Tab mit Import aus `Vosfor Gambling.xlsx`
- Dashboard mit Build-Prioritaeten und Lieferreihenfolge
- Live-Ops-Ansicht fuer Cycles, Fissures, Events und Vendor-Rotationen
- Roadmap-Ansicht mit logisch sortierten Feature-Modulen
- Requirements-Ansicht fuer APIs, Integrationen und Blocker
- Market-Ansicht mit echter Item-/Set-Suche, `ingame`-Sell-Orders, Seller-Namen, Ranks, Item-Bildern und Whisper-Texten
- Relic-Ansicht mit Beispiel-Drops
- Saubere Python-Struktur fuer spaeteren Ausbau

## Projektstruktur

- `app.py`: Einstiegspunkt
- `warframe_app/models.py`: Datenmodelle
- `warframe_app/clients.py`: HTTP-Client fuer Live-Daten
- `warframe_app/storage.py`: SQLite-Storage und Cache
- `warframe_app/services.py`: Datenquelle und App-Logik
- `warframe_app/gui.py`: Desktop-Oberflaeche
- `warframe_companion.db`: lokale SQLite-Datenbank, wird automatisch erzeugt

## Starten

1. Python 3.11 oder neuer installieren
2. Abhaengigkeiten installieren:

```powershell
py -3 -m pip install -r requirements.txt
```

3. Einmal den Browser fuer den Live-Market installieren:

```powershell
py -3 -m playwright install chromium
```

4. Im Projektordner ausfuehren:

```powershell
py -3 app.py
```

Alternativ funktioniert auf vielen Systemen auch:

```powershell
python app.py
```

Falls `python` unter Windows nicht gefunden wird, ist oft nur der Windows-App-Alias aktiv. Auf diesem Rechner ist `py -3` verfuegbar.

## Wichtigste externe Bausteine

- `warframestat.us` fuer Worldstate, Fissures, Rotationen, Events und NPC-Zyklen
- `warframe.market` fuer Live-Orders, Bilder, Closed-Trade-Stats und spaeter eigene Listings
- lokaler Inventarzugriff oder eine Overwolf-aehnliche Loesung fuer Foundry, Mastery und Inventory
- SQLite fuer lokalen Zustand, Caches und Alerts
- spaeter OCR/Overlay-Technik fuer Ingame-Features
- `Vosfor Gambling.xlsx` in deinem `Downloads`-Ordner fuer den Vosfor-Import

## Market-Stand heute

- Der Item-Katalog wird live aus `v2/items` geladen
- Live-Orders kommen aus `v2/orders/item/<slug>`
- Item-Metadaten und Bilder kommen aus `v2/item/<slug>/set`
- Die App zeigt nur sichtbare `sell`-Orders mit Status `ingame`
- Seller-Name, Preis, Rank, Menge, Reputation und Whisper-Text werden direkt in der App angezeigt
- Market-Daten werden lokal in `warframe_companion.db` gecacht
- Auto-Refresh fuer den aktuell offenen Market-Eintrag ist eingebaut

## Naechste sinnvolle Schritte

- Preisalarme und Watchlist auf Basis der Live-Orders und Trade-Statistiken
- lokale Notifications fuer Fissures, Events und Resets
- Entscheidung zur Inventar-Synchronisation
- danach Foundry, Mastery Helper und Inventory aus echtem Account-Zustand bauen
