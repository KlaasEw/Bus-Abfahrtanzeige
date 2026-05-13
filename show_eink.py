#!/usr/bin/env python3
"""
Zeigt das gerenderte PNG (Standard: output/abfahrtsplan.png) auf einem
Waveshare 7,5\" E-Ink V2 (800×480, epd7in5_V2) an.

- Zwischen den vollen Aktualisierungen: Partial-Modus (``init_part`` +
  ``display_Partial``) — deutlich kürzer als ein kompletter Refresh.
- Mindestens alle 30 Minuten (konfigurierbar): voller Refresh (``init`` +
  ``display``) gegen Ghosting.

Voraussetzung auf dem Raspberry Pi: Waveshare-Python-Library im PYTHONPATH,
z. B. Repo https://github.com/waveshare/e-Paper klonen und setzen::

    export WSEPD_LIB=/home/pi/e-Paper/RaspberryPi_JetsonNano/python/lib

Siehe README Abschnitt E-Ink-Anzeige.
"""

from __future__ import annotations

import argparse
import logging
import os
import signal
import sys
import time
from pathlib import Path

_shutdown = False


def _request_shutdown(_signum: int | None = None, _frame: object | None = None) -> None:
    global _shutdown
    _shutdown = True


def _prepend_waveshare_lib(explicit: str | None) -> None:
    """Fügt das Verzeichnis hinzu, das das Paket ``waveshare_epd`` enthält."""
    candidates: list[str] = []
    if explicit:
        candidates.append(os.path.abspath(explicit))
    env = os.environ.get("WSEPD_LIB")
    if env:
        candidates.append(os.path.abspath(env.strip()))
    here = Path(__file__).resolve().parent
    candidates.append(str(here / "e-Paper" / "RaspberryPi_JetsonNano" / "python" / "lib"))
    for p in candidates:
        if p and os.path.isdir(os.path.join(p, "waveshare_epd")):
            if p not in sys.path:
                sys.path.insert(0, p)
            return
    raise ImportError(
        "Paket waveshare_epd nicht gefunden. Klone https://github.com/waveshare/e-Paper "
        "und setze WSEPD_LIB auf …/RaspberryPi_JetsonNano/python/lib "
        "oder lege den Ordner als ./e-Paper/.../lib ins Projekt."
    )


def _load_epd_module(libdir: str | None):
    _prepend_waveshare_lib(libdir)
    from waveshare_epd import epd7in5_V2  # type: ignore  # noqa: PLC0415

    return epd7in5_V2


def main() -> int:
    parser = argparse.ArgumentParser(description="PNG auf Waveshare 7,5″ E-Ink (V2) ausgeben.")
    parser.add_argument(
        "--image",
        type=Path,
        default=None,
        help="PNG-Datei (Standard: OUTPUT_PNG_PATH aus bus_anzeige.config)",
    )
    parser.add_argument(
        "--waveshare-lib",
        type=str,
        default=None,
        help="Pfad zu …/RaspberryPi_JetsonNano/python/lib (alternativ Umgebung WSEPD_LIB)",
    )
    parser.add_argument(
        "--full-interval",
        type=float,
        default=1800.0,
        metavar="SEC",
        help="Mindestabstand für vollen Refresh in Sekunden (Standard: 1800 = 30 min)",
    )
    parser.add_argument(
        "--poll",
        type=float,
        default=1.0,
        metavar="SEC",
        help="Prüfintervall, ob die Bilddatei neu geschrieben wurde (Standard: 1)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Debug-Logging (waveshare / PIL)",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(message)s",
    )
    log = logging.getLogger("show_eink")

    if args.verbose:
        logging.getLogger("PIL").setLevel(logging.INFO)

    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _request_shutdown)
    signal.signal(signal.SIGINT, _request_shutdown)

    try:
        from bus_anzeige.config import OUTPUT_PNG_PATH  # noqa: PLC0415
    except ImportError:
        log.error("bus_anzeige nicht importierbar — Skript im Projektroot ausführen.")
        return 1

    image_path = Path(args.image) if args.image is not None else Path(OUTPUT_PNG_PATH)
    full_interval = max(60.0, float(args.full_interval))
    poll_sec = max(0.2, float(args.poll))

    try:
        epd7in5_V2 = _load_epd_module(args.waveshare_lib)
    except ImportError as exc:
        log.error("%s", exc)
        return 1

    from PIL import Image  # noqa: PLC0415

    epd = epd7in5_V2.EPD()
    last_full_mono = 0.0
    partial_ready = False
    last_mtime: float | None = None

    log.info(
        "E-Ink: %s×%s, Bild %s, voller Refresh alle %.0f s, Partial dazwischen.",
        epd.width,
        epd.height,
        image_path.resolve(),
        full_interval,
    )

    while not _shutdown:
        try:
            st = image_path.stat()
        except FileNotFoundError:
            log.debug("Warte auf %s …", image_path)
            time.sleep(poll_sec)
            continue

        mtime = st.st_mtime
        if last_mtime is not None and mtime == last_mtime:
            time.sleep(poll_sec)
            continue
        last_mtime = mtime

        try:
            img = Image.open(image_path)
        except OSError as exc:
            log.warning("PNG konnte nicht gelesen werden: %s", exc)
            time.sleep(poll_sec)
            continue

        if img.size != (epd.width, epd.height):
            log.error(
                "Bildgröße %s passt nicht zum Panel %s×%s.",
                img.size,
                epd.width,
                epd.height,
            )
            time.sleep(poll_sec)
            continue

        if img.mode not in ("RGB", "L", "1"):
            img = img.convert("RGB")

        buf = epd.getbuffer(img)
        now = time.monotonic()
        need_full = (now - last_full_mono) >= full_interval or last_full_mono == 0.0

        try:
            if need_full:
                log.info("Voller Display-Refresh")
                if epd.init() != 0:
                    log.error("epd.init() fehlgeschlagen")
                    time.sleep(poll_sec)
                    continue
                epd.display(buf)
                last_full_mono = now
                partial_ready = False
            else:
                if not partial_ready:
                    log.debug("Partial-Modus (init_part)")
                    if epd.init_part() != 0:
                        log.error("epd.init_part() fehlgeschlagen")
                        time.sleep(poll_sec)
                        continue
                    partial_ready = True
                epd.display_Partial(buf, 0, 0, epd.width, epd.height)
        except OSError as exc:
            log.exception("Display-Update fehlgeschlagen: %s", exc)
            partial_ready = False
            time.sleep(5.0)
            continue

        time.sleep(poll_sec)

    log.info("Beenden — Display in Ruhezustand …")
    try:
        epd.init()
        epd.sleep()
    except OSError as exc:
        log.warning("sleep() fehlgeschlagen: %s", exc)
    try:
        epd7in5_V2.epdconfig.module_exit(cleanup=True)  # type: ignore[attr-defined]
    except (OSError, AttributeError):
        pass

    log.info("Fertig.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
