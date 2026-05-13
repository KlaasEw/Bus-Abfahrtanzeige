"""Konfiguration: Haltestelle Hanssenstraße und Richtungslisten."""

from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_DIR.parent

STOP_ID = "2191"
STOP_DISPLAY_NAME = "Hanssenstraße"

# Zielauflösung z. B. Waveshare 7,5" (800×480); bei anderem Panel hier anpassen
DISPLAY_WIDTH = 800
DISPLAY_HEIGHT = 480

OUTPUT_PNG_PATH = PROJECT_ROOT / "output" / "abfahrtsplan.png"

# Maximal angezeigte Abfahrten je Block „Innenstadt“ und „Außerhalb“ (PNG / später Display)
MAX_VERBINDUNGEN_INNEN_AUSSEN = 4

# Abstand zwischen API-Abruf und PNG-Aktualisierung (Sekunden)
UPDATE_INTERVAL_SECONDS = 30

KVG_STOP_PASSAGES_URL = (
    "https://kvg-internetservice-proxy.p.networkteam.com/internetservice/"
    "services/passageInfo/stopPassages/stop"
)

# Zielrichtungen Richtung Innenstadt / stadteinwärts
STADTEINWAERTS = frozenset(
    (
        "Dietrichsdorf",
        "Kiel Hbf",
        "Hassee",
    )
)

# Zielrichtungen stadtauswärts (Wik, Strand, Schilksee)
STADTAUSWAERTS = frozenset(
    (
        "Wik Kanal",
        "Strande",
        "Wik",
        "Schilksee",
    )
)

FEHLER_BEREICH_TITEL = "Nicht zugeordnete Richtungen (Fehlerbereich)"

# Wetter (DWD Open Data über Bright Sky, https://api.brightsky.dev/)
# Koordinaten: Umgebung Haltestelle Hanssenstraße / Kiel (bei Bedarf anpassen)
WEATHER_LAT = 54.323
WEATHER_LON = 10.123
WEATHER_LOCATION_LABEL = "Kiel"
# Ort in der Wetter-Fußzeile anzeigen (z. B. „Kiel · …“)
WEATHER_SHOW_LOCATION = False
BRIGHTSKY_BASE_URL = "https://api.brightsky.dev"
# Mindesthöhe Wetterbalken (px); wirkt mit Kopfzeilen-Schrift wie „Richtung Innenstadt“
WEATHER_FOOTER_HEIGHT_PX = 40
WEATHER_HTTP_TIMEOUT_SECONDS = 12.0
# Wetter-API seltener als Busdaten (Bus: UPDATE_INTERVAL_SECONDS)
WEATHER_REFRESH_SECONDS = 600
