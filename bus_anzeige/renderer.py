"""Abfahrtsplan als PNG (hochkontrastig, geeignet für E-Ink)."""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from bus_anzeige.config import (
    DISPLAY_HEIGHT,
    DISPLAY_WIDTH,
    MAX_VERBINDUNGEN_INNEN_AUSSEN,
    STOP_DISPLAY_NAME,
    WEATHER_FOOTER_HEIGHT_PX,
    WEATHER_SHOW_LOCATION,
)
from bus_anzeige.weather import WeatherSummary


def _passage_minutes(bus: dict) -> int:
    sec = bus.get("actualRelativeTime")
    if sec is None:
        return 0
    try:
        return max(0, round(int(sec) / 60))
    except (TypeError, ValueError):
        return 0


def _font_candidates() -> list[str]:
    return [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/Library/Fonts/Arial.ttf",
        r"C:\Windows\Fonts\arial.ttf",
    ]


def _load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    paths = _font_candidates()
    if bold:
        paths = [p for p in paths if "Bold" in p or "bold" in p] + [p for p in paths if "Bold" not in p]
    for path in paths:
        if path.endswith(".ttc"):
            try:
                return ImageFont.truetype(path, size, index=0)
            except OSError:
                continue
        if os.path.isfile(path):
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    return ImageFont.load_default()


def _truncate_to_width(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_width: float) -> str:
    if draw.textlength(text, font=font) <= max_width:
        return text
    ell = "…"
    t = text
    while len(t) > 0:
        t = t[:-1]
        if draw.textlength(t + ell, font=font) <= max_width:
            return t + ell
    return ell


def render_abfahrtsplan_png(
    stadtein: list[dict],
    stadtaus: list[dict],
    output_path: str | Path,
    width: int = DISPLAY_WIDTH,
    height: int = DISPLAY_HEIGHT,
    weather: WeatherSummary | None = None,
) -> Path:
    """
    Erzeugt ein schwarz-weißes PNG mit den Bereichen „Innenstadt“ und „Außerhalb“.

    Nicht zugeordnete Abfahrten werden nur in der Konsole ausgegeben, nicht im Bild.

    Pro Block werden höchstens so viele Abfahrten gezeichnet wie
    ``MAX_VERBINDUNGEN_INNEN_AUSSEN`` in der Konfiguration vorsieht (Standard: 4).

    Args:
        stadtein: Abfahrten stadteinwärts
        stadtaus: Abfahrten stadtauswärts
        output_path: Zieldatei (Verzeichnis wird bei Bedarf angelegt)
        width, height: Bildgröße in Pixeln
        weather: DWD/Bright-Sky-Zusammenfassung für die Fußzeile (optional)

    Returns:
        Pfad zur geschriebenen PNG-Datei
    """
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    white = (255, 255, 255)
    black = (0, 0, 0)
    bar_fill = (0, 0, 0)

    img = Image.new("RGB", (width, height), white)
    draw = ImageDraw.Draw(img)

    font_title = _load_font(32, bold=True)
    font_head = _load_font(22, bold=True)
    font_row = _load_font(24)
    font_small = _load_font(16)
    font_meta = _load_font(14)

    margin_x = 20
    margin_y = 14
    y = margin_y

    title = f"Abfahrten {STOP_DISPLAY_NAME}"
    draw.text((margin_x, y), title, font=font_title, fill=black)
    y += int(draw.textbbox((0, 0), title, font=font_title)[3] - draw.textbbox((0, 0), title, font=font_title)[1]) + 6

    stand = datetime.now().strftime("Stand: %d.%m.%Y %H:%M Uhr")
    draw.text((margin_x, y), stand, font=font_meta, fill=(70, 70, 70))
    y += int(draw.textbbox((0, 0), stand, font=font_meta)[3] - draw.textbbox((0, 0), stand, font=font_meta)[1]) + 12

    line_col_w = 56
    min_col_w = 88
    inner_w = width - 2 * margin_x
    head_max_w = inner_w - 2 * margin_x

    def header_height(text: str, fh: ImageFont.ImageFont) -> int:
        bbox = draw.textbbox((0, 0), text, font=fh)
        return max(34, bbox[3] - bbox[1] + 14)

    if weather is None or not weather.ok:
        weather_main_line = "Wetter: nicht verfügbar"
    else:
        t = weather.temperature_c
        temp_s = f"{t:.0f} °C" if t is not None else "— °C"
        cc = weather.cloud_cover_percent
        parts: list[str] = []
        if WEATHER_SHOW_LOCATION:
            parts.append(weather.location_label)
        parts.extend([temp_s, weather.sky_text])
        if cc is not None:
            parts.append(f"Wolken {cc:.0f} %")
        parts.append(weather.rain_hint)
        weather_main_line = " · ".join(parts)
    weather_line_fit = _truncate_to_width(draw, weather_main_line, font_head, head_max_w)
    footer_bar_h = max(WEATHER_FOOTER_HEIGHT_PX, header_height(weather_line_fit, font_head))
    content_floor = height - footer_bar_h

    def draw_section(title: str, buses: list[dict]) -> None:
        nonlocal y
        bar_h = header_height(title, font_head)
        if y + bar_h > content_floor:
            return
        draw.rectangle((0, y, width, y + bar_h), fill=bar_fill)
        title_fit = _truncate_to_width(draw, title, font_head, head_max_w)
        draw.text((margin_x, y + 7), title_fit, font=font_head, fill=white)
        y += bar_h + 6

        if not buses:
            empty = "(keine Abfahrten)"
            draw.text((margin_x, y), empty, font=font_small, fill=(90, 90, 90))
            y += int(
                draw.textbbox((0, 0), empty, font=font_small)[3]
                - draw.textbbox((0, 0), empty, font=font_small)[1]
            ) + 14
            return

        for bus in buses:
            row_h = int(
                draw.textbbox((0, 0), "Hg", font=font_row)[3] - draw.textbbox((0, 0), "Hg", font=font_row)[1]
            ) + 10
            if y + row_h > content_floor:
                break

            line = str(bus.get("patternText", "?"))
            direction = str(bus.get("direction", ""))
            mins = _passage_minutes(bus)
            min_txt = f"{mins} min"

            x_line_right = margin_x + line_col_w
            draw.text((x_line_right - draw.textlength(line, font=font_row), y + 2), line, font=font_row, fill=black)

            x_dir_left = margin_x + line_col_w + 14
            x_min_left = width - margin_x - min_col_w
            max_dir_w = max(80, x_min_left - x_dir_left - 8)
            direction_fit = _truncate_to_width(draw, direction, font_row, max_dir_w)
            draw.text((x_dir_left, y + 2), direction_fit, font=font_row, fill=black)

            draw.text(
                (width - margin_x - draw.textlength(min_txt, font=font_row), y + 2),
                min_txt,
                font=font_row,
                fill=black,
            )
            y += row_h

        y += 10

    cap = MAX_VERBINDUNGEN_INNEN_AUSSEN
    draw_section("Richtung Innenstadt", stadtein[:cap])
    draw_section("Richtung Außerhalb", stadtaus[:cap])

    footer_top = height - footer_bar_h
    white_f = (255, 255, 255)
    draw.rectangle((0, footer_top, width, height), fill=bar_fill)
    draw.text((margin_x, footer_top + 7), weather_line_fit, font=font_head, fill=white_f)

    img.save(out, format="PNG", optimize=True)
    return out
