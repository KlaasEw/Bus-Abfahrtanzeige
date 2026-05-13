# Bus-Abfahrtsanzeige für den Flur

Architektur, Softwaredesign und Elektronik.

## Projektziel

Im Flur soll ein stromsparendes E-Ink-Display die nächsten Busabfahrten der Haltestelle **Hanssenstraße** in Kiel anzeigen.

Die Anzeige soll:

- dauerhaft sichtbar sein
- automatisch aktualisiert werden
- möglichst wartungsarm laufen
- optisch wie eine echte DFI-Anzeige wirken
- später erweiterbar sein

Die Daten stammen direkt von der öffentlichen Echtzeit-API der KVG Kiel.

## Projektstruktur (lokal und auf dem Raspberry Pi)

Alle Dateien sind so angelegt, dass du den **gesamten Projektordner** per USB, `scp` oder `rsync` auf den Raspberry Pi kopieren kannst. Auf dem Pi legst du ihn z. B. als `/home/pi/bus-abfahrtanzeige` ab.

```text
bus-abfahrtanzeige/          (Name auf dem Pi frei wählbar)
├── README.md
├── requirements.txt
├── run.py                   Nur Bus + PNG (ohne E-Ink)
├── run_bus_display.py       Bus + PNG **und** E-Ink (für einen systemd-Dienst)
├── show_eink.py             PNG auf Waveshare 7,5″ E-Ink (wird von run_bus_display gestartet)
├── bus_anzeige/             Python-Paket
│   ├── __init__.py
│   ├── __main__.py          Alternativ: python3 -m bus_anzeige
│   ├── config.py            Haltestelle, URLs, Richtungslisten, Wetter, Fehlerbereich-Titel
│   ├── kvg.py               API-Abruf Busdaten
│   ├── weather.py           Wetter (Bright Sky / DWD Open Data)
│   ├── renderer.py          PNG-Abfahrtsplan
│   └── main.py              Gruppierung, Abrufe, Konsolenausgabe, PNG nur bei Änderung
├── deploy/
│   └── bus-abfahrtanzeige.service   Startet run_bus_display.py (setzt WSEPD_LIB)
└── examples/
    └── kvg_stop_passages_beispiel.json   Beispielantwort der API (Stand: Entwicklung)
```

## Datenquelle

### API-Endpoint

`https://kvg-internetservice-proxy.p.networkteam.com/internetservice/services/passageInfo/stopPassages/stop?stop=2191&mode=departure&language=de`

- Haltestelle: **`2191`** (= Hanssenstraße)

### API-Aufbau

Die relevanten Daten befinden sich im Feld `actual[]`.

Wichtige Felder:

| Feld | Bedeutung |
|------|-----------|
| `patternText` | Liniennummer |
| `direction` | Fahrtrichtung |
| `actualRelativeTime` | Sekunden bis Abfahrt |
| `actualTime` | Echtzeit-Abfahrtszeit |
| `plannedTime` | Planmäßige Abfahrtszeit |
| `status` | Echtzeitstatus |

### Wetter (Fußzeile im PNG)

Die Wetterzeile (Temperatur, Wolken, Regen-Hinweis) bezieht sich auf Daten des **Deutschen Wetterdienstes (DWD)**, bereitgestellt als Open Data auf [opendata.dwd.de](https://opendata.dwd.de/). Abgefragt wird sie über die kostenlose Community-API **[Bright Sky](https://brightsky.dev/)** (`https://api.brightsky.dev/`), die diese DWD-Daten als JSON zugänglich macht.

Für die Nutzung gelten die **Nutzungsbedingungen des DWD** sowie die Lizenz **Creative Commons BY 4.0 (CC BY 4.0)** — Details bei [DWD — Legal Notice](https://www.dwd.de/EN/service/legal_notice/legal_notice.html) und in der Bright-Sky-Dokumentation. Im laufenden Programm wird keine Quellenzeile auf dem Display gezeigt; die Zuordnung ist hier im README für deine private Dokumentation festgehalten.

Konfiguration: Koordinaten, Anzeige des Ortsnamens, Fußzeilenhöhe und das Intervall für Wetter-Neuabrufe (`WEATHER_REFRESH_SECONDS`, unabhängig vom Bus-Intervall `UPDATE_INTERVAL_SECONDS`) in `bus_anzeige/config.py`.

## Richtungslogik

Die Anzeige wird nach Straßenseite bzw. Zielrichtung gruppiert. Die Zuordnung erfolgt in `bus_anzeige/config.py` über exakte Übereinstimmung des API-Feldes `direction`.

### Richtung Innenstadt (stadteinwärts)

- Dietrichsdorf
- Kiel Hbf
- Hassee

### Richtung Außerhalb (stadtauswärts)

- Wik Kanal
- Strande
- Wik
- Schilksee

### Fehlerbereich

Alle Abfahrten, deren `direction` **weder** in der stadteinwärts- noch in der stadtauswärts-Liste steht, erscheinen im Bereich **„Nicht zugeordnete Richtungen (Fehlerbereich)“** — **in der Konsole** (`main.py`). Im **PNG** werden absichtlich nur die beiden Blöcke *Innenstadt* und *Außerhalb* gezeichnet (DFI-ähnlich); der Fehlerbereich dient der Wartung am Log.

## Zielarchitektur

```text
┌──────────────────────────────┐
│        KVG Echtzeit API      │
└──────────────┬───────────────┘
               │ HTTPS JSON
               ▼
┌──────────────────────────────┐
│       Raspberry Pi Zero      │
│                              │
│  run.py / main.py            │
│  requests, JSON, Pillow       │
│  show_eink.py (SPI)         │
└──────────────┬───────────────┘
               │ SPI
               ▼
┌──────────────────────────────┐
│       Waveshare E Ink        │
│         7.5 Zoll             │
└──────────────────────────────┘
```

Im Dauerbetrieb startet [`run_bus_display.py`](run_bus_display.py) beide Skripte als getrennte Prozesse; nur Bus/PNG ohne Panel: `python3 run.py`.

## Hardwareempfehlung

### Rechner

- Empfohlen: Raspberry Pi Zero 2 W
- Vorteile:
  - WLAN integriert
  - geringer Stromverbrauch
  - Python-Unterstützung
  - stabiler Dauerbetrieb
  - gute Community

### Display

- Empfohlen: Waveshare 7.5" E-Ink-Display
- Varianten:
  - Schwarz-Weiß
  - Schwarz-Weiß-Rot
- Empfehlung: Schwarz-Weiß
- Vorteile:
  - schnellere Updates
  - besserer Kontrast
  - weniger Ghosting

## Elektrisches Design

### Spannungsversorgung

```text
USB-C Netzteil
        │
        ▼
Raspberry Pi Zero 2 W
        │
        ▼
SPI Verbindung zum E Ink Display
```

### Verbindung Raspberry Pi ↔ E-Ink

Typische SPI-Pins:

| Raspberry Pi | E Ink |
|--------------|-------|
| `3.3V` | `VCC` |
| `GND` | `GND` |
| `GPIO10` | `DIN` |
| `GPIO11` | `CLK` |

## Softwarearchitektur

### Umgesetzte Komponenten

| Datei | Rolle |
|-------|--------|
| `run.py` | Start: KVG-Polling, Konsole, PNG (ohne E-Ink-Prozess) |
| `run_bus_display.py` | Start: `run.py` und `show_eink.py` gemeinsam (für **einen** systemd-Dienst) |
| `show_eink.py` | Waveshare **7,5″ V2** (800×480): Datei beobachten, Partial-/Vollrefresh |
| `bus_anzeige/config.py` | Haltestelle, URLs, Richtungslisten, Wetter, Ausgabe-Pfad |
| `bus_anzeige/kvg.py` | HTTP-Abruf KVG, JSON-Prüfung |
| `bus_anzeige/main.py` | Aufteilung Innen/Außen/Fehler (Konsole), Wettercache, **PNG nur bei geändertem Anzeigeinhalt** |
| `bus_anzeige/weather.py` | Bright Sky / DWD-Zusammenfassung |
| `bus_anzeige/renderer.py` | PNG mit Pillow (Titel, zwei Blöcke, Wetterzeile) |

Hinweis: Es gibt **kein** `bus_anzeige/display.py`; die Ansteuerung liegt in `show_eink.py` am Projektroot.

## Displaylayout (PNG)

Das erzeugte Bild enthält: Titel und Standzeit, zwei Balken **Richtung Innenstadt** und **Richtung Außerhalb** mit je bis zu vier Abfahrten, unten eine **Wetterzeile** (DWD/Bright Sky). Ein separater Fehlerbereich ist **nicht** im PNG — nur in der Konsole.

## Aktualisierungsstrategie (Ist)

### API-Polling

Standard: alle **30 Sekunden** (`UPDATE_INTERVAL_SECONDS` in `config.py`) neue KVG-Daten.

### Änderungsprüfung (PNG und E-Ink)

`main.py` vergleicht einen **Snapshot** der für das PNG relevanten Felder (Abfahrten + Wetteranzeige). Die Datei `output/abfahrtsplan.png` wird **nur neu geschrieben**, wenn sich dieser Inhalt geändert hat. `show_eink.py` reagiert auf die **Datei-Änderungszeit** — ohne neues Schreiben bleibt das E-Ink unangetastet.

Vorteile: weniger Ghosting, weniger SPI-Last, längere Panel-Lebensdauer.

## Refresh-Strategie (E-Ink)

### Partial-Update (Waveshare)

`show_eink.py` nutzt den **Partial-Modus** des Treibers (`init_part` + `display_Partial`). Dabei wird das **gesamte** 800×480-Bild mit der schnelleren Partial-Welle aktualisiert — **kein** pixelgenaues Diff einzelner Kacheln (das unterstützt der 7,5″-Treiber praktisch nicht zuverlässig).

### Vollrefresh

Standard alle **30 Minuten** (`--full-interval 1800` in `show_eink.py`) ein **voller** Refresh (`init` + `display`) gegen Ghosting.

## Softwareablauf (Ist)

```text
run.py (main):
  while True:
    1. KVG API abrufen
    2. Innen / Außen / Fehler (Konsole)
    3. Wetter (Cache)
    4. Bei geändertem Snapshot: PNG schreiben
    5. Warten (UPDATE_INTERVAL_SECONDS)

show_eink.py (parallel):
  while True:
    1. PNG-Datei prüfen (mtime)
    2. Bei Änderung: Partial oder (zeitgesteuert) Vollrefresh
```

Für den Pi mit Display: **[`run_bus_display.py`](run_bus_display.py)** startet beide Schleifen als getrennte Prozesse; siehe systemd-Vorlage.

## Python-Bibliotheken

```bash
pip install -r requirements.txt
```

Enthält u. a. **requests**, **Pillow** (Rendering und Lesen der PNG fürs Display).

Optional Waveshare-Treiber (Version je nach Display-Modul beachten) — auf PyPI oft **nicht** als fertiges Wheel; üblich ist das **Git-Repository**:

```bash
git clone https://github.com/waveshare/e-Paper.git ~/e-Paper
export WSEPD_LIB="$HOME/e-Paper/RaspberryPi_JetsonNano/python/lib"
```

### E-Ink (`show_eink.py` / `run_bus_display.py`)

Auf dem Raspberry Pi (nach SPI-/GPIO-Anschluss laut Waveshare-Anleitung):

1. Waveshare-Library klonen und `WSEPD_LIB` setzen (oder `e-Paper/.../lib` ins Projekt legen).
2. **Mit Display:** `python3 run_bus_display.py` — startet `run.py` und `show_eink.py` nebeneinander.
3. **Ohne Display:** nur `python3 run.py`.

`show_eink.py` beobachtet die PNG und aktualisiert das **7,5″ V2**-Panel (800×480):

```bash
cd /home/pi/bus-abfahrtanzeige
source venv/bin/activate   # falls genutzt
export WSEPD_LIB="$HOME/e-Paper/RaspberryPi_JetsonNano/python/lib"
python3 run_bus_display.py
```

- **Partial:** schneller Modus, **gesamtes** Bild (kein Regional-Diff).
- **Voll:** Standard alle **30 Minuten** (`--full-interval 1800`).

```bash
python3 show_eink.py --full-interval 1800 --poll 1
python3 show_eink.py --image /tmp/test.png --verbose
```

### systemd (ein Dienst)

Vorlage: [`deploy/bus-abfahrtanzeige.service`](deploy/bus-abfahrtanzeige.service) startet **`run_bus_display.py`**. Dort `WSEPD_LIB` auf deinen geklonten `e-Paper`-Pfad setzen. Zwei getrennte Units für Bus und E-Ink sind **nicht** mehr nötig.

## Lokal oder auf dem Raspberry Pi testen

Im Projektverzeichnis:

```bash
python3 run.py
```

Alternative:

```bash
python3 -m bus_anzeige
```

## Raspberry Pi: Umsetzung und Kopieren

Ziel: Ordner auf den Pi kopieren, virtuelle Umgebung anlegen, Dienst starten. Die Beispielpfade setzen `WorkingDirectory` und den Service auf **`/home/pi/bus-abfahrtanzeige`**. Wenn dein Ordner anders heißt, passe `WorkingDirectory` und `ExecStart` in der Service-Datei entsprechend an.

### 1. Projekt auf den Pi kopieren

Auf deinem Entwicklungsrechner (Beispiel mit `scp`):

```bash
scp -r "/Pfad/zum/Projektordner/Bus Abfahrtanzeige Flur" pi@raspberrypi.local:/home/pi/bus-abfahrtanzeige
```

Oder den Inhalt in einen bereits angelegten Ordner `bus-abfahrtanzeige` kopieren (USB-Stick, `rsync`, grafischer Dateimanager).

### 2. Raspberry Pi OS und Python

- Raspberry Pi OS Lite (64-bit empfohlen) oder Desktop-Variante
- Python 3 ist vorinstalliert; bei Bedarf: `sudo apt update && sudo apt install -y python3-venv python3-pip`

### 3. Virtuelle Umgebung und Abhängigkeiten

Auf dem Pi, im Projektverzeichnis:

```bash
cd /home/pi/bus-abfahrtanzeige
python3 -m venv venv
./venv/bin/pip install --upgrade pip
./venv/bin/pip install -r requirements.txt
```

Test:

```bash
./venv/bin/python3 run.py
```

### 4. Autostart mit systemd (empfohlen)

Service-Vorlage: [`deploy/bus-abfahrtanzeige.service`](deploy/bus-abfahrtanzeige.service). Sie startet **`run_bus_display.py`** (Bus + PNG + E-Ink) und erwartet:

- Projekt unter `/home/pi/bus-abfahrtanzeige`
- virtuelle Umgebung unter `/home/pi/bus-abfahrtanzeige/venv`
- Benutzer `pi`
- **`WSEPD_LIB`** in der Unit auf den Ordner `…/RaspberryPi_JetsonNano/python/lib` gesetzt

Installation auf dem Pi:

```bash
sudo cp /home/pi/bus-abfahrtanzeige/deploy/bus-abfahrtanzeige.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable bus-abfahrtanzeige.service
sudo systemctl start bus-abfahrtanzeige.service
```

Status und Logs:

```bash
sudo systemctl status bus-abfahrtanzeige.service
journalctl -u bus-abfahrtanzeige.service -f
```

Nur Daten und PNG **ohne** E-Ink-Hardware: `ExecStart` in der Service-Datei auf `run.py` umstellen (oder lokal `python3 run.py`).

Wenn dein Linux-Benutzer nicht `pi` heißt, in der Service-Datei `User=` und `Group=` anpassen.

### 5. WLAN und Zeit

- WLAN vor dem Dauerbetrieb zuverlässig einrichten.
- NTP/Zeitzone korrekt setzen (`sudo raspi-config` → Localisation), damit geplante und echte Zeiten zur Anzeige passen.

## Beispiel für API-Abruf (Hanssenstraße)

```python
import requests

url = (
    "https://kvg-internetservice-proxy.p.networkteam.com/internetservice/"
    "services/passageInfo/stopPassages/stop"
)
params = {"stop": "2191", "mode": "departure", "language": "de"}
data = requests.get(url, params=params, timeout=15).json()

for bus in data["actual"]:
    print(bus["patternText"], bus["direction"])
```

Eine gespeicherte Beispielantwort liegt unter `examples/kvg_stop_passages_beispiel.json`.

## Bildrendering

Umsetzung in **`bus_anzeige/renderer.py`** mit **Pillow** (`Image`, `ImageDraw`, `ImageFont`): schwarz-weißes PNG 800×480, Ausgabe nach `output/abfahrtsplan.png` (Pfad in `config.py`). `show_eink.py` liest dieselbe Datei und überträgt sie per Waveshare-Treiber auf das Panel.

## Gehäuseideen

Möglichkeiten:

- Bilderrahmen-Umbau
- 3D-Druck
- Holzrahmen
- Unterputzrahmen

## Erweiterungsmöglichkeiten

Wetter (Fußzeile im PNG) ist **bereits** umgesetzt. Sonst später denkbar:

- Uhrzeit (zusätzlich im Layout)
- Bahnabfahrten
- Fähren
- Home-Assistant-Integration
- MQTT
- Touchbedienung
- Nachtmodus
- Helligkeitssensor
- Anwesenheitserkennung

## Empfohlene Entwicklungsreihenfolge

### Phase 1 (erledigt)

- API verstehen
- Konsolenanzeige mit Richtungslogik und Fehlerbereich (`bus_anzeige/`)

### Phase 2 (erledigt)

- PNG-Rendering mit Pillow, Layout, Wetter-Fußzeile
- PNG nur bei inhaltlicher Änderung

### Phase 3 (erledigt)

- E-Ink (`show_eink.py`), KVG-Polling, Partial-/Vollrefresh, gemeinsamer Start (`run_bus_display.py`)

### Phase 4 (Hardware / Betrieb)

- Gehäuse bauen (manuell)
- Dauerbetrieb und systemd-Feinschliff

## Empfehlung für den Dauerbetrieb

### Betriebssystem

- Raspberry Pi OS Lite

### Autostart

- Empfohlen: `systemd`-Service (siehe Abschnitt „Raspberry Pi“)
- Vorteile: automatischer Neustart bei Fehlern, Logging, stabiler Betrieb

## Langfristige Vorteile dieser Architektur

- unabhängig von Cloudsystemen
- leicht wartbar
- modular erweiterbar
- geringe Betriebskosten
- professioneller Aufbau
- nahezu lautlos
- sehr geringer Stromverbrauch
