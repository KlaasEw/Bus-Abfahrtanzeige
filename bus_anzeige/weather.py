"""Wetterzusammenfassung aus DWD Open Data (Bright-Sky-Gateway)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

import requests

from bus_anzeige.config import (
    BRIGHTSKY_BASE_URL,
    WEATHER_HTTP_TIMEOUT_SECONDS,
    WEATHER_LAT,
    WEATHER_LON,
    WEATHER_LOCATION_LABEL,
)

_ICON_DE: dict[str, str] = {
    "clear-day": "klar",
    "clear-night": "klar",
    "partly-cloudy-day": "teils bewölkt",
    "partly-cloudy-night": "teils bewölkt",
    "cloudy": "bewölkt",
    "fog": "Nebel",
    "wind": "windig",
    "rain": "Regen",
    "sleet": "Schneeregen",
    "snow": "Schnee",
    "hail": "Hagel",
    "thunderstorm": "Gewitter",
}

_CONDITION_DE: dict[str, str] = {
    "dry": "trocken",
    "fog": "Nebel",
    "rain": "Regen",
    "sleet": "Schneeregen",
    "snow": "Schnee",
    "hail": "Hagel",
    "thunderstorm": "Gewitter",
}


@dataclass(frozen=True)
class WeatherSummary:
    """Kompakte Darstellung für die PNG-Fußzeile."""

    ok: bool
    location_label: str
    temperature_c: float | None
    cloud_cover_percent: float | None
    sky_text: str
    rain_hint: str
    error: str | None = None


def _num(v: Any) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _intish(v: Any) -> int | None:
    if v is None:
        return None
    try:
        return int(round(float(v)))
    except (TypeError, ValueError):
        return None


def _parse_ts(s: str) -> datetime | None:
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def _sky_de(icon: str | None, condition: str | None) -> str:
    if icon and icon in _ICON_DE:
        return _ICON_DE[icon]
    if condition and condition in _CONDITION_DE:
        return _CONDITION_DE[condition]
    return "—"


def _rain_hint_window(records: list[dict], now_utc: datetime, hours: int = 6) -> str:
    end = now_utc + timedelta(hours=hours)
    max_prob = 0
    sum_precip = 0.0
    for rec in records:
        ts = _parse_ts(str(rec.get("timestamp", "")))
        if ts is None or ts < now_utc or ts > end:
            continue
        p = _intish(rec.get("precipitation_probability"))
        if p is not None:
            max_prob = max(max_prob, p)
        pr = _num(rec.get("precipitation"))
        if pr is not None:
            sum_precip += max(0.0, pr)

    if sum_precip >= 2.0 or max_prob >= 75:
        return "Regen wahrscheinlich"
    if sum_precip >= 0.3 or max_prob >= 45:
        return "Regen möglich"
    if max_prob >= 22:
        return "Niesel möglich"
    return "Regen gering"


def fetch_weather_summary(
    lat: float = WEATHER_LAT,
    lon: float = WEATHER_LON,
    location_label: str = WEATHER_LOCATION_LABEL,
    timeout: float = WEATHER_HTTP_TIMEOUT_SECONDS,
) -> WeatherSummary:
    """
    Holt aktuelles Wetter und eine grobe Regen-/Niederschlagsaussicht (nächste Stunden).

    Netzwerk- und Parsefehler werden als ``WeatherSummary(ok=False)`` zurückgegeben.
    """
    base = BRIGHTSKY_BASE_URL.rstrip("/")

    try:
        r_cur = requests.get(
            f"{base}/current_weather",
            params={"lat": lat, "lon": lon},
            timeout=timeout,
            headers={"Accept": "application/json"},
        )
        r_cur.raise_for_status()
        cur_body = r_cur.json()
    except (requests.RequestException, ValueError) as exc:
        return WeatherSummary(
            ok=False,
            location_label=location_label,
            temperature_c=None,
            cloud_cover_percent=None,
            sky_text="",
            rain_hint="",
            error=str(exc),
        )

    if not isinstance(cur_body, dict):
        return WeatherSummary(
            ok=False,
            location_label=location_label,
            temperature_c=None,
            cloud_cover_percent=None,
            sky_text="",
            rain_hint="",
            error="Ungültige API-Antwort",
        )

    w = cur_body.get("weather")
    if not isinstance(w, dict):
        return WeatherSummary(
            ok=False,
            location_label=location_label,
            temperature_c=None,
            cloud_cover_percent=None,
            sky_text="",
            rain_hint="",
            error="Kein Wetterobjekt in der Antwort",
        )

    temp = _num(w.get("temperature"))
    cloud = _num(w.get("cloud_cover"))
    icon = w.get("icon") if isinstance(w.get("icon"), str) else None
    cond = w.get("condition") if isinstance(w.get("condition"), str) else None
    sky = _sky_de(icon, cond)

    local_date = datetime.now(ZoneInfo("Europe/Berlin")).date()
    rain_hint = "Regen gering"
    try:
        r_day = requests.get(
            f"{base}/weather",
            params={"lat": lat, "lon": lon, "date": local_date.isoformat()},
            timeout=timeout,
            headers={"Accept": "application/json"},
        )
        r_day.raise_for_status()
        day_body = r_day.json()
        if isinstance(day_body, dict):
            hourly = day_body.get("weather")
            if isinstance(hourly, list):
                rain_hint = _rain_hint_window(hourly, datetime.now(timezone.utc))
    except (requests.RequestException, ValueError):
        pass

    return WeatherSummary(
        ok=True,
        location_label=location_label,
        temperature_c=temp,
        cloud_cover_percent=cloud,
        sky_text=sky,
        rain_hint=rain_hint,
        error=None,
    )
