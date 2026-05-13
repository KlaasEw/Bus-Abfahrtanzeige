"""Abruf der KVG-StopPassages-API."""

from __future__ import annotations

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from bus_anzeige.config import KVG_STOP_PASSAGES_URL, STOP_ID

_DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; BusAbfahrtanzeige/1.0; KVG-StopPassages) "
        "python-requests"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "de-DE,de;q=0.9",
}

_SESSION: requests.Session | None = None


def _session() -> requests.Session:
    """Eine Session mit Retries (u. a. bei Connection reset / kurzzeitigen Serverabbrüchen)."""
    global _SESSION
    if _SESSION is not None:
        return _SESSION

    retry = Retry(
        total=6,
        connect=6,
        read=4,
        backoff_factor=0.8,
        status_forcelist=(502, 503, 504),
        allowed_methods=frozenset({"GET"}),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry, pool_connections=2, pool_maxsize=4)

    session = requests.Session()
    session.headers.update(_DEFAULT_HEADERS)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    _SESSION = session
    return session


def fetch_stop_passages(timeout: float = 20.0) -> list[dict]:
    """
    Liefert die Liste ``actual`` der Abfahrten für die konfigurierte Haltestelle.

    Raises:
        requests.RequestException: Netzwerk- oder HTTP-Fehler
        ValueError: Antwort enthält kein erwartetes JSON-Objekt
    """
    params = {"stop": STOP_ID, "mode": "departure", "language": "de"}
    response = _session().get(KVG_STOP_PASSAGES_URL, params=params, timeout=timeout)
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, dict):
        raise ValueError("API-Antwort ist kein JSON-Objekt")
    actual = data.get("actual")
    if actual is None:
        raise ValueError("API-Antwort enthält kein Feld 'actual'")
    if not isinstance(actual, list):
        raise ValueError("Feld 'actual' ist keine Liste")
    return actual
