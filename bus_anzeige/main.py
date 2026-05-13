"""Konsolenanzeige: stadteinwärts, stadtauswärts, Fehlerbereich."""

from __future__ import annotations

import signal
import sys
import threading
from datetime import datetime

import requests

from bus_anzeige.config import (
    FEHLER_BEREICH_TITEL,
    OUTPUT_PNG_PATH,
    STADTAUSWAERTS,
    STADTEINWAERTS,
    UPDATE_INTERVAL_SECONDS,
    WEATHER_REFRESH_SECONDS,
)
from bus_anzeige.kvg import fetch_stop_passages
from bus_anzeige.renderer import render_abfahrtsplan_png
from bus_anzeige.weather import WeatherSummary, fetch_weather_summary

_shutdown = threading.Event()
_weather_cache: WeatherSummary | None = None
_weather_fetched_at: datetime | None = None
_last_png_state: object | None = None


def _weather_for_display() -> WeatherSummary:
    """
    Liefert gecachtes Wetter; API nur alle WEATHER_REFRESH_SECONDS erneut.

    Bei vorübergehendem Fehler bleibt die letzte erfolgreiche Anzeige erhalten.
    """
    global _weather_cache, _weather_fetched_at
    now = datetime.now()
    age_s = (
        (now - _weather_fetched_at).total_seconds()
        if _weather_fetched_at is not None
        else float("inf")
    )
    if age_s < WEATHER_REFRESH_SECONDS and _weather_cache is not None:
        return _weather_cache

    fresh = fetch_weather_summary()
    if fresh.ok:
        _weather_cache = fresh
        _weather_fetched_at = now
    elif _weather_cache is None or not _weather_cache.ok:
        _weather_cache = fresh
        _weather_fetched_at = now
    else:
        _weather_fetched_at = now

    if not fresh.ok and fresh.error:
        print(f"Hinweis Wetter: {fresh.error}", file=sys.stderr)

    assert _weather_cache is not None
    return _weather_cache


def _request_shutdown(_signum: int | None = None, _frame: object | None = None) -> None:
    _shutdown.set()


def _minutes(bus: dict) -> int:
    sec = bus.get("actualRelativeTime")
    if sec is None:
        return 0
    try:
        return max(0, round(int(sec) / 60))
    except (TypeError, ValueError):
        return 0


def _format_line(bus: dict) -> str:
    line = str(bus.get("patternText", "?"))
    direction = str(bus.get("direction", ""))
    return f"{line:>3} → {direction:<24} {_minutes(bus):>2} min"


def partition_passages(passages: list[dict]) -> tuple[list[dict], list[dict], list[dict]]:
    """Teilt Abfahrten in stadteinwärts, stadtauswärts und nicht zugeordnet."""
    innen: list[dict] = []
    aussen: list[dict] = []
    fehler: list[dict] = []
    for bus in passages:
        direction = bus.get("direction")
        if not isinstance(direction, str):
            fehler.append(bus)
            continue
        if direction in STADTEINWAERTS:
            innen.append(bus)
        elif direction in STADTAUSWAERTS:
            aussen.append(bus)
        else:
            fehler.append(bus)
    return innen, aussen, fehler


def _png_display_state(innen: list[dict], aussen: list[dict], weather: WeatherSummary) -> tuple:
    """
    Snapshot der Felder, die das PNG beeinflussen (Abfahrten + Wetter).
    Nur bei Änderung wird die Datei neu geschrieben — E-Ink bleibt sonst unangetastet.
    """

    def buses_key(buses: list[dict]) -> tuple:
        return tuple(
            (
                bus.get("patternText"),
                bus.get("direction"),
                bus.get("actualRelativeTime"),
                bus.get("actualTime"),
                bus.get("plannedTime"),
            )
            for bus in buses
        )

    w = (
        weather.ok,
        weather.temperature_c,
        weather.cloud_cover_percent,
        weather.sky_text,
        weather.rain_hint,
        weather.error,
    )
    return (buses_key(innen), buses_key(aussen), w)


def _print_block(title: str, buses: list[dict]) -> None:
    print(f"\n=== {title} ===\n")
    if not buses:
        print("  (keine Abfahrten)")
        return
    for bus in buses:
        print(_format_line(bus))


def _run_once() -> None:
    """Ein Abruf: Konsole + PNG (PNG nur bei geändertem Anzeigeinhalt)."""
    global _last_png_state
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"\n--- Aktualisierung {ts} ---")

    try:
        passages = fetch_stop_passages()
    except (requests.RequestException, ValueError) as exc:
        print(f"Fehler beim API-Abruf: {exc}", file=sys.stderr)
        return

    innen, aussen, fehler = partition_passages(passages)
    _print_block("Richtung Innenstadt", innen)
    _print_block("Richtung Außerhalb", aussen)
    _print_block(FEHLER_BEREICH_TITEL, fehler)

    weather = _weather_for_display()
    state = _png_display_state(innen, aussen, weather)
    if state == _last_png_state:
        print("PNG unverändert — Datei nicht neu geschrieben.")
        return

    try:
        png_path = render_abfahrtsplan_png(innen, aussen, OUTPUT_PNG_PATH, weather=weather)
        _last_png_state = state
        print(f"PNG gespeichert: {png_path.resolve()}")
    except OSError as exc:
        print(f"PNG konnte nicht geschrieben werden: {exc}", file=sys.stderr)


def run() -> int:
    """
    Endlosschleife: alle UPDATE_INTERVAL_SECONDS KVG abfragen; PNG nur bei geänderten Daten.

    Beenden: SIGINT (Strg+C) oder SIGTERM (z. B. ``systemctl stop``) setzen ein internes
    Stop-Event; die Wartezeit bis zur nächsten Runde wird dabei abgebrochen.
    """
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _request_shutdown)
    signal.signal(signal.SIGINT, _request_shutdown)

    print(
        f"Aktualisierung alle {UPDATE_INTERVAL_SECONDS} s (Bus). "
        f"Wetter-Neuabruf alle {WEATHER_REFRESH_SECONDS} s. PNG: {OUTPUT_PNG_PATH.resolve()}"
    )
    print(
        "Beenden: Strg+C im Terminal. Als systemd-Dienst: "
        "sudo systemctl stop bus-abfahrtanzeige.service"
    )

    while not _shutdown.is_set():
        _run_once()
        if _shutdown.wait(timeout=UPDATE_INTERVAL_SECONDS):
            break

    print("\nProgramm beendet.")
    return 0


def main() -> None:
    raise SystemExit(run())
