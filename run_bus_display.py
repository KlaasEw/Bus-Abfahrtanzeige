#!/usr/bin/env python3
"""
Startet Bus-Polling inkl. PNG (`run.py`) und E-Ink-Anzeige (`show_eink.py`) gemeinsam.

Gedacht für **einen** systemd-Dienst: ein Prozess, zwei Kindprozesse. Beendet sich ein
Kind oder kommt SIGINT/SIGTERM, werden beide beendet.

Nur Busdaten ohne Display: weiterhin direkt `python3 run.py`.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PY = sys.executable
_procs: list[subprocess.Popen] = []


def _terminate_children() -> None:
    for p in _procs:
        if p.poll() is None:
            p.terminate()
    deadline = time.monotonic() + 15.0
    for p in _procs:
        while p.poll() is None and time.monotonic() < deadline:
            time.sleep(0.05)
        if p.poll() is None:
            p.kill()


def _request_shutdown(_signum: int | None = None, _frame: object | None = None) -> None:
    _terminate_children()
    sys.exit(0)


def main() -> int:
    global _procs
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _request_shutdown)
    signal.signal(signal.SIGINT, _request_shutdown)

    run_script = ROOT / "run.py"
    show_script = ROOT / "show_eink.py"
    if not run_script.is_file() or not show_script.is_file():
        print("run.py oder show_eink.py fehlt im Projektverzeichnis.", file=sys.stderr)
        return 1

    env = os.environ.copy()
    _procs = [
        subprocess.Popen([PY, str(run_script)], cwd=str(ROOT), env=env),
        subprocess.Popen([PY, str(show_script)], cwd=str(ROOT), env=env),
    ]

    try:
        while True:
            for p in _procs:
                code = p.poll()
                if code is not None:
                    print(f"Kindprozess beendet (Code {code}), beende den anderen …", file=sys.stderr)
                    _terminate_children()
                    return 1
            time.sleep(0.25)
    except KeyboardInterrupt:
        _terminate_children()
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
